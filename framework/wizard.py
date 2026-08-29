#!/usr/bin/env python3
"""本体建设向导：把 S1-S9 九站流程变成一步一步的交互式配置。

用法：
  python3 wizard.py projects/<name>     # 进入/继续某项目的引导
  状态存在 <project>/.wizard_state.json，随时 Ctrl+C，下次接着走。

每站：解释 → 收集输入 → 生成文件 → 立即校验（语法/推理可见）。
"""
import json
import re
import subprocess
import sys
from pathlib import Path

FRAMEWORK_DIR = Path(__file__).resolve().parent

# rdflib 在框架 venv 里；不在 venv 中启动时自动切换过去
# （判断用 sys.prefix：venv 的 python 是指向系统 python 的符号链接，比 realpath 会被骗）
try:
    import rdflib  # noqa: F401
except ImportError:
    import os
    _venv_py = FRAMEWORK_DIR.parent / ".venv" / "bin" / "python"
    if sys.prefix == sys.base_prefix and _venv_py.exists():
        os.execv(str(_venv_py), [str(_venv_py), str(Path(__file__).resolve())] + sys.argv[1:])
    raise


# ---------------------------------------------------------------- 基础工具
def ask(prompt, default=None):
    hint = " [%s]" % default if default else ""
    ans = input("？ %s%s：" % (prompt, hint)).strip()
    return ans or default


def ask_lines(prompt, hint):
    print("？ %s" % prompt)
    print("  格式：%s（空行结束）" % hint)
    lines = []
    while True:
        ln = input("  > ").strip()
        if not ln:
            break
        lines.append(ln)
    return lines


def ask_yes(prompt, default=True):
    ans = ask(prompt, "Y/n" if default else "y/N")
    return not ans.lower().startswith("n")


def banner(station, title):
    print("\n" + "=" * 64)
    print("  【%s】%s" % (station, title))
    print("=" * 64)


def load_state(proj):
    f = proj / ".wizard_state.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"done": []}


def save_state(proj, state):
    (proj / ".wizard_state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(proj):
    meta = {}
    for line in (proj / "project.yml").read_text(encoding="utf-8").splitlines():
        if ":" in line and not line.startswith("#"):
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    return meta


def validate_ttl(path):
    from rdflib import Graph
    g = Graph()
    g.parse(str(path), format="turtle")
    return len(g)


def append_ontology(proj, text):
    ont = proj / "ontology" / "domain.ttl"
    with open(ont, "a", encoding="utf-8") as f:
        f.write(text)
    n = validate_ttl(ont)   # 立即校验，写坏了立刻知道
    print("  ✔ 已写入 %s（当前 %d 条三元组，语法校验通过）" % (ont.name, n))


# ---------------------------------------------------------------- S1 场景
def s1(proj, state):
    banner("S1", "定场景——如果只能先做对一类决策，是哪一类？")
    print("原则：小切口。别建全公司本体，只建能支撑这个决策的最小集。")
    scenario = ask("用一句话描述场景（如：618 大促选品决策）")
    decision = ask("最关键的那个决策/问题是什么")
    state["scenario"] = scenario
    state["decision"] = decision
    with open(proj / "project.yml", "a", encoding="utf-8") as f:
        f.write('scenario: "%s"\ndecision: "%s"\n' % (scenario, decision))
    print("  ✔ 场景已记入 project.yml")


# ---------------------------------------------------------------- S2 CQ
def s2(proj, state):
    banner("S2", "胜任力问题——本体建成后必须能回答的业务问题")
    print("写法：业务语言、可判定、有明确答案形态。建议 5-8 个。")
    cqs = ask_lines("逐条输入 CQ", "CQ 问题文本")
    if not cqs:
        print("  跳过（未输入）")
        return
    lines = ["# 胜任力问题清单（S2 定稿）\n"]
    for i, q in enumerate(cqs, 1):
        lines.append("- CQ%d %s" % (i, q))
    (proj / "cq" / "competency_questions.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    state["cqs"] = cqs
    print("  ✔ %d 个 CQ 已写入 cq/competency_questions.md" % len(cqs))


# ---------------------------------------------------------------- S3 术语
def s3(proj, state):
    banner("S3", "术语表——裁决口径歧义")
    print("重点不是罗列术语，而是【裁决】：比如「销售额」到底是哪个口径。")
    terms = ask_lines("逐条输入术语", "术语 | IRI名(camelCase/PascalCase) | 定义")
    if not terms:
        print("  跳过")
        return
    rows = ["# 术语表（S3 裁决）\n", "| 术语 | IRI 名 | 定义 |", "|---|---|---|"]
    for t in terms:
        parts = [p.strip() for p in t.split("|")]
        rows.append("| %s | %s | %s |" % (parts[0], parts[1] if len(parts) > 1 else "",
                                          parts[2] if len(parts) > 2 else ""))
    (proj / "glossary.md").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print("  ✔ %d 个术语已写入 glossary.md" % len(terms))


# ---------------------------------------------------------------- S4 类
def s4(proj, state):
    banner("S4", "类与层级——本体里的「名词」")
    print("提示：5-8 个核心类起步；推导类（如「滞销品」）只占语义位，不进数据。")
    classes = ask_lines("逐条输入类", "类名 中文标签 [父类]")
    if not classes:
        return
    buf = ["\n# ---- S4 类骨架（向导生成） ----"]
    for c in classes:
        parts = c.split()
        name, label = parts[0], parts[1] if len(parts) > 1 else ""
        parent = parts[2] if len(parts) > 2 else None
        line = ":%s a owl:Class " % name
        if parent:
            line += "; rdfs:subClassOf :%s " % parent
        line += '; rdfs:label "%s" .' % label
        buf.append(line)
    append_ontology(proj, "\n".join(buf) + "\n")


# ---------------------------------------------------------------- S5 属性
def s5(proj, state):
    banner("S5", "属性与关系——本体里的「动词和字段」")
    print("对象属性（宾语是资源）：如 madeBy SPU→品牌")
    objs = ask_lines("逐条输入对象属性", "属性名 主语类 宾语类 中文标签")
    buf = ["\n# ---- S5 对象属性（向导生成） ----"]
    for p in objs:
        parts = p.split()
        if len(parts) < 3:
            continue
        label = parts[3] if len(parts) > 3 else ""
        buf.append(':%s a owl:ObjectProperty ; rdfs:domain :%s ; rdfs:range :%s ; rdfs:label "%s" .'
                   % (parts[0], parts[1], parts[2], label))
    print("数据属性（宾语是值）：如 price SKU→小数")
    datas = ask_lines("逐条输入数据属性", "属性名 主语类 类型(string/integer/decimal/date) 中文标签")
    buf.append("\n# ---- S5 数据属性（向导生成） ----")
    for p in datas:
        parts = p.split()
        if len(parts) < 3:
            continue
        label = parts[3] if len(parts) > 3 else ""
        buf.append(':%s a owl:DatatypeProperty ; rdfs:domain :%s ; rdfs:range xsd:%s ; rdfs:label "%s" .'
                   % (parts[0], parts[1], parts[2], label))
    if len(buf) > 2:
        append_ontology(proj, "\n".join(buf) + "\n")


# ---------------------------------------------------------------- S6 公理
def s6(proj, state):
    banner("S6", "规则公理——让推理机替你干活")
    buf = ["\n# ---- S6 规则公理（向导生成） ----"]
    if ask_yes("有树形结构吗（类目/组织/地区）？加传递性"):
        prop = ask("哪个属性表达父子关系（如 subCategoryOf）")
        if prop and re.match(r"^[A-Za-z]\w*$", prop):
            buf.append(':%s a owl:TransitiveProperty .' % prop)
            print("  → 查任意上层节点将自动含全部下层实例")
        else:
            print("  ⚠️ 属性名不合法，跳过")
    if ask_yes("有需要双向查询的关系吗？加互逆"):
        pair = ask("正向属性名 反向属性名（空格分隔）")
        if pair and len(pair.split()) == 2:
            a, b = pair.split()
            buf.append(":%s a owl:ObjectProperty ." % b)
            buf.append(":%s owl:inverseOf :%s ." % (a, b))
    if ask_yes("有需要「穿过中间实体」的直达查询吗（如 SKU→SPU→品牌）？加属性链"):
        while True:
            chain = ask("链：属性1 属性2 目标属性名（空格分隔，空行结束）")
            if not chain:
                break
            parts = chain.split()
            if len(parts) == 3 and all(re.match(r"^[A-Za-z]\w*$", x) for x in parts):
                buf.append(':%s a owl:ObjectProperty ; owl:propertyChainAxiom ( :%s :%s ) .'
                           % (parts[2], parts[0], parts[1]))
                print("  → :%s 链已声明" % parts[2])
            else:
                print("  ⚠️ 格式不对，应为：属性1 属性2 目标属性名（三个合法标识符）")
    if ask_yes("有互斥的类吗（如在售 vs 已下架）？加互斥"):
        pair = ask("两个互斥类名（空格分隔）")
        if pair and len(pair.split()) == 2:
            buf.append(":%s owl:disjointWith :%s ." % (pair.split()[0], pair.split()[1]))
    if len(buf) > 1:
        append_ontology(proj, "\n".join(buf) + "\n")
    else:
        print("  未添加公理（可后续直接在 domain.ttl 里补）")


# ---------------------------------------------------------------- S7 数据
def s7(proj, state):
    banner("S7", "数据接入——给本体填实例")
    print("四种方式：")
    print("  1) 手写样例数据（最快验证，推荐先做）")
    print("  2) 接数据库（Ontop 映射，参考 tutorial/L8_ontop/）")
    print("  3) 自然语言录入（ingest.py：LLM 抽取 → 三道闸门 → 入库）")
    print("  4) 跳过，之后自己补 data/catalog.ttl")
    choice = ask("选择", "1")
    if choice == "1":
        base_iri = read_meta(proj)["base_iri"]
        sample = ("@prefix : <%s> .\n@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .\n\n"
                  "# TODO: 按本体类写实例，如：\n# :inst1 a :EntityA ; :sampleMetric 0.5 .\n"
                  % base_iri)
        (proj / "data" / "catalog.ttl").write_text(sample, encoding="utf-8")
        print("  ✔ 已生成 data/catalog.ttl 模板，请填入实例数据后回来继续")
    elif choice == "2":
        print("  参考教程 tutorial/L8_ontop/lesson.md：")
        print("  ① ontop bootstrap 生成骨架  ② 写 mapping/*.obda  ③ ontop materialize 到 data/")
    elif choice == "3":
        print("   scaffold 已把 ingest.py 放进项目根目录。用法：")
        print("    python3 ingest.py \"用大白话描述一条业务事实\" [--dry-run]")
        print("  LLM 只产中间态 JSON，入库前必过：本体校验 → SHACL（违规回滚）→ 幽灵检查。")
        print("  建议先用 --dry-run 跑两条，确认抽取质量符合预期后再正式入库。")


# ---------------------------------------------------------------- S8 SHACL
def s8(proj, state):
    banner("S8", "SHACL 硬规则——封闭世界的质检员")
    print("OWL 管推理（没写≠违规），SHACL 管拦截（没写=违规）。")
    rules = ask_lines("逐条输入硬规则", "目标类 | 属性 | 约束(min1/max1/正数/枚举a,b) | 提示语")
    if not rules:
        return
    buf = ["\n# ---- S8 硬规则（向导生成） ----"]
    for i, r in enumerate(rules, 1):
        parts = [p.strip() for p in r.split("|")]
        if len(parts) < 3:
            continue
        cls, prop, constraint = parts[0], parts[1], parts[2]
        msg = parts[3] if len(parts) > 3 else "校验失败"
        if constraint == "min1":
            body = "sh:minCount 1 ;"
        elif constraint == "max1":
            body = "sh:maxCount 1 ;"
        elif constraint == "正数":
            body = "sh:minExclusive 0 ;"
        elif constraint.startswith("枚举"):
            vals = " ".join('"%s"' % v for v in constraint[2:].split(","))
            body = "sh:in (%s) ;" % vals
        else:
            continue
        buf.append(':Rule%dShape a sh:NodeShape ; sh:targetClass :%s ;\n'
                   '    sh:property [ sh:path :%s ; %s sh:message "%s" ] .'
                   % (i, cls, prop, body, msg))
    append_ontology(proj, "")   # 先确认本体没坏
    shapes = proj / "ontology" / "shapes.ttl"
    with open(shapes, "a", encoding="utf-8") as f:
        f.write("\n".join(buf) + "\n")
    n = validate_ttl(shapes)
    print("  ✔ %d 条硬规则已写入 shapes.ttl（%d 条三元组）" % (len(rules), n))


# ---------------------------------------------------------------- S9 验收
def s9(proj, state):
    banner("S9", "验收——CQ 回归 + 三道门禁")
    print("① 把 S2 的 CQ 翻成 SPARQL 放进 cq/*.rq（第一行写 # 注释说明）")
    print("② 可选：cq/expected.json 写期望值做精确比对")
    if ask_yes("现在跑门禁 ci.sh？"):
        r = subprocess.run(["bash", "ci.sh"], cwd=str(proj))
        print("门禁退出码：%d（0=全绿）" % r.returncode)
    print("\n之后可以用 agent.py 自然语言验收：")
    print("  python3 agent.py \"你的业务问题\"")


STATIONS = [
    ("S1", "定场景", s1), ("S2", "胜任力问题", s2), ("S3", "术语表", s3),
    ("S4", "类与层级", s4), ("S5", "属性与关系", s5), ("S6", "规则公理", s6),
    ("S7", "数据接入", s7), ("S8", "SHACL 硬规则", s8), ("S9", "验收", s9),
]


def main():
    if len(sys.argv) < 2:
        print("用法：python3 wizard.py projects/<name>")
        print("（先用 scaffold.py 生成项目骨架）")
        return 1
    proj = Path(sys.argv[1])
    if not (proj / "project.yml").exists():
        print("项目不存在或缺 project.yml：%s" % proj)
        return 1

    state = load_state(proj)
    meta = read_meta(proj)
    print("■ 本体建设向导 ■  项目：%s（%s）" % (meta.get("title"), proj))
    print("已完成站点：%s" % ("、".join(state["done"]) or "无"))

    for sid, title, fn in STATIONS:
        if sid in state["done"]:
            continue
        if not ask_yes("\n进入 %s（%s）？" % (sid, title)):
            print("  跳过 %s" % sid)
            continue
        try:
            fn(proj, state)
        except (KeyboardInterrupt, EOFError):
            print("\n已暂停，进度已保存。随时重新运行本向导继续。")
            save_state(proj, state)
            return 0
        state["done"].append(sid)
        save_state(proj, state)
        print("  ✔ %s 完成，进度已保存" % sid)

    print("\n🎉 九站全部走完。本体资产：%s/ontology/domain.ttl" % proj)
    print("持续演进：变更走 proposals/ 提案 → 三道门禁 → 升版本存档 versions/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
