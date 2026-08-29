"""治理能力：逻辑一致性检查、CQ 回归测试、漂移指标、变更日志。

定位：本体是"活资产"，治理层回答四个问题——
  1. 模型自身有没有矛盾？（disjoint 一致性检查）
  2. 改动有没有把能回答的问题打挂？（CQ 回归 = 本体的单元测试）
  3. 数据与模型的偏离是否在恶化？（漂移指标，月度评审看板）
  4. 谁、什么时候、为什么改了本体？（changelog.jsonl 审计）
"""
import json
import datetime as dt
from pathlib import Path
from string import Template

from kg import KnowledgeGraph, BASE, ECAT

PREFIX = """PREFIX :    <https://demo.local/ecat#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

CHANGELOG = BASE / "governance" / "changelog.jsonl"


# ---- 1. 一致性检查（开放世界推理的补充：开放世界不会"报错"，要主动查矛盾） --------
def check_consistency(kg: KnowledgeGraph):
    q = PREFIX + """
SELECT ?x WHERE { ?x a :ActiveProduct ; a :DelistedProduct . }
"""
    return [str(r[0]).split("#")[-1] for r in kg.query(q)]


# ---- 2. CQ 回归 ------------------------------------------------------------------
def build_params(thresholds: dict):
    as_of = dt.date.fromisoformat(thresholds["asOfDate"])
    return {
        "AS_OF": str(as_of),
        "AS_OF_PLUS_AUTH": str(as_of + dt.timedelta(days=thresholds["authorization"]["expiringWithinDays"])),
        "NEW_SINCE": str(as_of - dt.timedelta(days=thresholds["newProduct"]["listedWithinDays"])),
        "MIN_SALES": thresholds["promo"]["minSales30d"],
        "MIN_MARGIN": thresholds["promo"]["minGrossMargin"],
        "INV_GT": thresholds["slowMoving"]["inventoryDaysGt"],
        "SALES_LT": thresholds["slowMoving"]["sales30dLt"],
        "NEW_MIN_SALES": thresholds["newProduct"]["minSales30d"],
    }


def load_thresholds():
    return json.loads((BASE / "rules" / "thresholds.json").read_text(encoding="utf-8"))


def run_cq(kg: KnowledgeGraph, thresholds=None):
    """跑全部胜任力问题，返回 {文件名: 结果行列表}。"""
    thresholds = thresholds or load_thresholds()
    params = build_params(thresholds)
    out = {}
    for rq in sorted((BASE / "cq").glob("*.rq")):
        sparql = Template(rq.read_text(encoding="utf-8")).substitute(params)
        res = kg.query(sparql)
        rows = [[str(v).split("#")[-1] for v in row] for row in res]
        out[rq.name] = rows
    return out


def cq_regression(kg: KnowledgeGraph, thresholds=None):
    """CQ 回归：比对实际结果与 expected.json，返回 (全过?, 明细)。"""
    thresholds = thresholds or load_thresholds()
    params = build_params(thresholds)
    expected = json.loads((BASE / "cq" / "expected.json").read_text(encoding="utf-8"))
    details, all_ok = [], True
    for fname, exp in sorted(expected.items()):
        sparql = Template((BASE / "cq" / fname).read_text(encoding="utf-8")).substitute(params)
        res = kg.query(sparql)
        var_idx = [str(v) for v in res.vars].index(exp["var"])
        actual = sorted(str(row[var_idx]).split("#")[-1] for row in res)
        ok = actual == sorted(exp["values"])
        all_ok = all_ok and ok
        details.append({"cq": fname, "ok": ok, "expected": sorted(exp["values"]), "actual": actual})
    return all_ok, details


# ---- 3. 漂移指标 ------------------------------------------------------------------
def drift_report(kg: KnowledgeGraph, thresholds=None):
    thresholds = thresholds or load_thresholds()
    params = build_params(thresholds)
    metrics = {}

    metrics["无类目SKU数"] = len(list(kg.query(PREFIX + """
SELECT ?s WHERE { ?s a :SKU . FILTER NOT EXISTS { ?s :belongsToCategory ?c } }""")))

    metrics["30天内到期授权书"] = len(list(kg.query(
        Template(PREFIX + """
SELECT ?a WHERE { ?a a :Authorization ; :validUntil ?e .
  FILTER(?e > "$AS_OF"^^xsd:date && ?e <= "$AS_OF_PLUS_AUTH"^^xsd:date) }"""
        ).substitute(params))))

    metrics["状态矛盾实例数"] = len(check_consistency(kg))

    _, violations, _ = kg.validate()
    metrics["SHACL违规数"] = len(violations)

    all_ok, details = cq_regression(kg, thresholds)
    metrics["CQ回归通过率"] = "%d/%d" % (sum(1 for d in details if d["ok"]), len(details))

    metrics["本体版本"] = kg.version()
    return metrics


# ---- 4. 变更日志（审计） --------------------------------------------------------------
def log_change(entry: dict):
    entry = dict(entry)
    entry["at"] = dt.datetime.now().isoformat(timespec="seconds")
    with open(CHANGELOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
