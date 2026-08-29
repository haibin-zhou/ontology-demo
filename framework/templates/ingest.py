#!/usr/bin/env python3
"""自然语言录入：用 LLM 把业务描述拆解为本体实例数据，校验后入库。

架构（LLM 只做"提议"，校验权在确定性代码）：

  自然语言 → [LLM 抽取] → 中间态 JSON（实体/属性/关系）
           → [闸门1 本体校验] 类/属性存在？domain/range 匹配？类型正确？
           → [闸门2 SHACL]   硬规则（沿用项目 shapes.ttl）
           → [闸门3 幽灵检查] 不写本体没声明的谓语
           → 追加进 data/catalog.ttl

用法：
  python3 ingest.py "新上了一款跑鞋：闪电二代，StrideMax 出品，售价599……"
  python3 ingest.py "……" --dry-run   # 只打印抽取结果和校验，不入库
"""
import json
import re
import sys
import datetime as dt
from pathlib import Path

import requests
from rdflib import Graph, Namespace, RDF, OWL, RDFS, XSD
from rdflib.collection import Collection
from pyshacl import validate

BASE = Path(__file__).resolve().parent
# 向上找到仓库根目录的 llm_config.py（凭证与模型配置，各层级深度不同）
for _up in (BASE, *BASE.parents):
    if (_up / "llm_config.py").exists():
        sys.path.insert(0, str(_up))
        break
import llm_config as config                     # noqa: E402

SESSION = requests.Session()
SESSION.trust_env = False

# --- 项目定位：优先 project.yml，没有就从本体文件的 @prefix 推断（兼容引导期项目）
_proj_yml = BASE / "project.yml"
PROJ = {}
if _proj_yml.exists():
    PROJ = {l.split(":", 1)[0].strip(): l.split(":", 1)[1].strip().strip('"').strip("'")
            for l in _proj_yml.read_text(encoding="utf-8").splitlines()
            if ":" in l and not l.startswith("#")}

_ont_dir = BASE / "ontology"
if (BASE / "ontology" / "domain.ttl").exists():
    ONT_FILE = BASE / "ontology" / "domain.ttl"
else:  # 取 ontology/ 下第一个非 shapes 的 .ttl
    ONT_FILE = next(f for f in sorted(_ont_dir.glob("*.ttl")) if f.name != "shapes.ttl")

if "base_iri" in PROJ:
    BASE_IRI = PROJ["base_iri"]
else:
    m = re.search(r"@prefix\s*:\s*<([^>]+)>", ONT_FILE.read_text(encoding="utf-8"))
    BASE_IRI = m.group(1)
NS = Namespace(BASE_IRI)


# ---------------------------------------------------------------- 本体 schema
SH = Namespace("http://www.w3.org/ns/shacl#")


def load_required():
    """从 shapes.ttl 提取每个类的必填字段（sh:minCount>=1）及枚举，供 LLM 参考。"""
    shapes_file = BASE / "ontology" / "shapes.ttl"
    if not shapes_file.exists():
        return {}
    sg = Graph().parse(str(shapes_file), format="turtle")
    required = {}
    for shape in sg.subjects(RDF.type, SH.NodeShape):
        for tc in sg.objects(shape, SH.targetClass):
            cls = str(tc).split("#")[-1]
            for pnode in sg.objects(shape, SH.property):
                path = sg.value(pnode, SH.path)
                if path is None or not str(path).startswith(BASE_IRI):
                    continue  # inversePath 等复合路径跳过
                minc = sg.value(pnode, SH.minCount)
                if minc and int(minc) >= 1:
                    in_head = sg.value(pnode, SH["in"])
                    vals = ([str(v) for v in Collection(sg, in_head)]
                            if in_head is not None else [])
                    required.setdefault(cls, []).append(
                        (str(path).split("#")[-1], vals))
    return required


def load_schema():
    ont = Graph().parse(str(ONT_FILE), format="turtle")
    classes, obj_props, data_props = {}, {}, {}
    for c in ont.subjects(RDF.type, OWL.Class):
        if str(c).startswith(BASE_IRI):
            classes[str(c).split("#")[-1]] = str(ont.value(c, RDFS.label) or "")
    for p in ont.subjects(RDF.type, OWL.ObjectProperty):
        if str(p).startswith(BASE_IRI):
            name = str(p).split("#")[-1]
            dom = ont.value(p, RDFS.domain)
            rng = ont.value(p, RDFS.range)
            obj_props[name] = {
                "label": str(ont.value(p, RDFS.label) or ""),
                "domain": str(dom).split("#")[-1] if dom else None,
                "range": str(rng).split("#")[-1] if rng else None}
    for p in ont.subjects(RDF.type, OWL.DatatypeProperty):
        if str(p).startswith(BASE_IRI):
            name = str(p).split("#")[-1]
            rng = ont.value(p, RDFS.range)
            data_props[name] = {
                "label": str(ont.value(p, RDFS.label) or ""),
                "domain": str(rng_owner(ont, p)) if rng_owner(ont, p) else None,
                "range": str(rng).split("#")[-1] if rng else "string"}
    return ont, classes, obj_props, data_props


def rng_owner(ont, p):
    dom = ont.value(p, RDFS.domain)
    return str(dom).split("#")[-1] if dom else None


# ---------------------------------------------------------------- LLM 抽取
EXTRACT_PROMPT = """你是本体数据录入员。把用户的业务描述拆解为结构化实例数据，输出严格 JSON。

【本体的类】（只能用这些）
%s

【对象属性（关系）】（domain → 属性 → range）
%s

【数据属性（字段）】（domain . 属性 : 类型）
%s

【必填字段】（这些类的这些字段必须给出，枚举值只能从中选）
%s

【输出格式】
{
  "entities": [
    {"id": "有意义的英文id", "class": "类名",
     "properties": {"数据属性名": 值},
     "relations": {"对象属性名": "目标实体id"}}
  ],
  "unsure": ["无法确定/本体中找不到对应概念的信息点"]
}

规则：
1. 类和属性只能用上面列出的，找不到对应概念就放 unsure，禁止编造；
2. id 用简短英文/拼音，引用已存在的实体直接用其 id；
3. 日期格式 YYYY-MM-DD，小数不带单位；
4. 必填字段必须给值：描述里有就用描述的值，没有就给最合理的默认值并在 unsure 里注明；
5. 只输出 JSON。"""


def llm_extract(text, classes, obj_props, data_props, required):
    c_lines = "\n".join("- %s（%s）" % (k, v) for k, v in classes.items())
    o_lines = "\n".join("- %s → %s → %s（%s）" % (v["domain"] or "?", k, v["range"] or "?", v["label"])
                        for k, v in obj_props.items())
    d_lines = "\n".join("- %s . %s : %s（%s）" % (v["domain"] or "?", k, v["range"], v["label"])
                        for k, v in data_props.items())
    r_lines = "\n".join("- %s 必填：%s" % (
        cls, "、".join("%s%s" % (p, "（枚举：%s）" % "/".join(vals) if vals else "")
                       for p, vals in fields)) or "（无）"
        for cls, fields in required.items()) or "（无）"
    payload = {
        "model": config.KIMI_MODEL,
        "messages": [
            {"role": "system", "content": EXTRACT_PROMPT % (c_lines, o_lines, d_lines, r_lines)},
            {"role": "user", "content": text}],
        "temperature": 1.0,
        "response_format": {"type": "json_object"},
    }
    resp = SESSION.post(config.KIMI_BASE_URL + "/chat/completions",
                        headers={"Authorization": "Bearer " + config.require("KIMI_API_KEY")},
                        json=payload, timeout=120)
    if resp.status_code in (400, 404):
        payload["model"] = config.KIMI_FALLBACK_MODEL
        resp = SESSION.post(config.KIMI_BASE_URL + "/chat/completions",
                            headers={"Authorization": "Bearer " + config.require("KIMI_API_KEY")},
                            json=payload, timeout=120)
    resp.raise_for_status()
    content = resp.json()["choices"][0]["message"]["content"]
    return json.loads(content)


# ---------------------------------------------------------------- 闸门1：本体校验
def check_against_ontology(extraction, classes, obj_props, data_props, existing_ids):
    """返回 (errors, warnings)。errors 阻断入库。"""
    errors, warnings = [], []
    ids = {e["id"] for e in extraction.get("entities", [])} | existing_ids
    for e in extraction.get("entities", []):
        eid, cls = e.get("id"), e.get("class")
        if not eid or not re.match(r"^[A-Za-z][\w-]*$", eid or ""):
            errors.append("实体 id 不合法：%r" % eid)
            continue
        if cls not in classes:
            errors.append("实体 %s 的类 %r 不在本体中" % (eid, cls))
            continue
        if eid in existing_ids:
            warnings.append("实体 %s 的 id 已存在，新属性将合并到既有实体上" % eid)
        for prop, val in (e.get("properties") or {}).items():
            if prop not in data_props:
                errors.append("%s.%s：属性不在本体中" % (eid, prop))
                continue
            meta = data_props[prop]
            if meta["domain"] and meta["domain"] != cls:
                warnings.append("%s.%s：本体里该属性的 domain 是 %s（当前类 %s）"
                                % (eid, prop, meta["domain"], cls))
            if not _type_ok(val, meta["range"]):
                errors.append("%s.%s：值 %r 不是 %s 类型" % (eid, prop, val, meta["range"]))
        for prop, target in (e.get("relations") or {}).items():
            if prop not in obj_props:
                errors.append("%s -[%s]-> %s：关系不在本体中" % (eid, prop, target))
                continue
            if target not in ids:
                warnings.append("%s -[%s]-> %s：目标实体不在本次抽取和已有数据中"
                                % (eid, prop, target))
    return errors, warnings


def _type_ok(val, rng):
    if rng in ("integer",):
        return isinstance(val, int) and not isinstance(val, bool)
    if rng in ("decimal",):
        return isinstance(val, (int, float)) and not isinstance(val, bool)
    if rng in ("date",):
        return isinstance(val, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", val)
    return True


# ---------------------------------------------------------------- 生成三元组
def to_turtle(extraction, data_props):
    lines = ["", "# ---- NL 录入 %s ----" % dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
             "@prefix : <%s> ." % BASE_IRI,
             "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> ."]
    for e in extraction.get("entities", []):
        eid, cls = e["id"], e["class"]
        triples = [":%s a :%s" % (eid, cls)]
        for prop, val in (e.get("properties") or {}).items():
            rng = data_props[prop]["range"]
            lit = '"%s"^^xsd:%s' % (val, rng) if rng == "date" else (
                '"%s"' % val if rng == "string" else str(val))
            triples.append(":%s %s" % (prop, lit))
        for prop, target in (e.get("relations") or {}).items():
            triples.append(":%s :%s" % (prop, target))
        lines.append("    ".join([triples[0]] + ["; " + t for t in triples[1:]]) + " .")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------- 主流程
def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry_run = "--dry-run" in sys.argv
    if not args:
        print(__doc__)
        return 1
    text = " ".join(args)

    ont, classes, obj_props, data_props = load_schema()

    data_file = BASE / "data" / "catalog.ttl"
    data = Graph()
    if data_file.exists():
        data.parse(str(data_file), format="turtle")
    existing_ids = {str(s).split("#")[-1] for s in set(data.subjects())}
    # 已有 id 也含关系目标里出现的
    existing_ids |= {str(o).split("#")[-1] for o in set(data.objects())}

    print("① LLM 抽取中（模型 %s）…" % config.KIMI_MODEL)
    extraction = llm_extract(text, classes, obj_props, data_props, load_required())
    n = len(extraction.get("entities", []))
    print("   抽到 %d 个实体" % n)
    for e in extraction.get("entities", []):
        print("   · %s（%s）属性 %d 个、关系 %d 条" % (
            e.get("id"), e.get("class"),
            len(e.get("properties") or {}), len(e.get("relations") or {})))
    for u in extraction.get("unsure") or []:
        print("   ⚠️ LLM 无法归类的信息：%s" % u)

    print("\n② 闸门1：本体校验")
    errors, warnings = check_against_ontology(extraction, classes, obj_props,
                                              data_props, existing_ids)
    for w in warnings:
        print("   ⚠️ %s" % w)
    if errors:
        for e in errors:
            print("   ❌ %s" % e)
        print("\n⛔ 校验未过，未入库。本体不认识的东西绝不硬写。")
        return 2
    print("   ✅ 类/属性/类型/domain-range 全部通过")

    turtle = to_turtle(extraction, data_props)

    print("\n③ 闸门2+3：写入后 SHACL 校验（只管本次新实体；存量违规只提示、不阻断）")
    new_ids = {e["id"] for e in extraction.get("entities", [])}
    new_data = Graph()
    new_data.parse(str(data_file), format="turtle") if data_file.exists() else None
    new_data.parse(data=turtle, format="turtle")
    shapes = Graph().parse(str(BASE / "ontology" / "shapes.ttl"), format="turtle")
    conforms, report, _ = validate(new_data, shacl_graph=shapes, advanced=True)
    if not conforms:
        SH = Namespace("http://www.w3.org/ns/shacl#")
        mine, legacy = [], []
        for r in report.subjects(RDF.type, SH.ValidationResult):
            focus = str(report.value(r, SH.focusNode)).split("#")[-1]
            item = "%s —— %s" % (focus, str(report.value(r, SH.resultMessage)))
            (mine if focus in new_ids else legacy).append(item)
        for v in legacy:
            print("   ⚠️ 存量违规（非本次引入，属业务发现）：%s" % v)
        if mine:
            for v in mine:
                print("   ❌ %s" % v)
            print("\n⛔ 本次录入的数据违反 SHACL，已回滚，未入库。")
            return 2
    print("   ✅ 本次新实体的 SHACL 校验全过")

    print("\n④ 拟写入的三元组：")
    print(turtle)
    if dry_run:
        print("（dry-run，未入库）")
        return 0

    with open(data_file, "a", encoding="utf-8") as f:
        f.write(turtle)   # turtle 自带 @prefix 声明，物化产物缺前缀也能安全追加
    print("✅ 已追加到 %s（当前共 %d 条三元组）"
          % (data_file.name, len(Graph().parse(str(data_file), format="turtle"))))
    print("建议接着跑：python3 run_cq.py  &&  bash ci.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
