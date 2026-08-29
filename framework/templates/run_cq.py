"""CQ 回归（通用版）：跑 cq/*.rq，与 cq/expected.json 比对。

胜任力问题 = 本体的单元测试。每次本体变更后必须全绿。
用法：python3 run_cq.py
"""
import json
import sys
from pathlib import Path
from string import Template

from rdflib import Graph
import owlrl

BASE = Path(__file__).parent


def load_params():
    """thresholds.json 展平为模板变量：asOfDate→ASOFDATE，嵌套 promo.minX→PROMO_MINX。"""
    t = json.loads((BASE / "rules" / "thresholds.json").read_text(encoding="utf-8"))
    params = {}

    def flat(d, prefix=""):
        for k, v in d.items():
            key = (prefix + "_" + k if prefix else k).upper()
            if isinstance(v, dict):
                flat(v, key)
            else:
                params[key] = v
    flat(t)
    return params


def build_graph():
    g = Graph()
    g.parse(str(BASE / "ontology" / "domain.ttl"), format="turtle")
    data_file = BASE / "data" / "catalog.ttl"
    if data_file.exists():
        g.parse(str(data_file), format="turtle")
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                           axiomatic_triples=False).expand(g)
    return g


def main():
    params = load_params()
    g = build_graph()
    print("图规模：%d 条（含推理物化）\n" % len(g))

    expected_path = BASE / "cq" / "expected.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8")) \
        if expected_path.exists() else {}

    all_ok = True
    for rq in sorted((BASE / "cq").glob("*.rq")):
        sparql = Template(rq.read_text(encoding="utf-8")).substitute(params)
        res = g.query(sparql)
        var0 = str(res.vars[0]) if res.vars else None
        actual = sorted(set(str(row[0]).split("#")[-1] for row in res)) if var0 else []

        exp = expected.get(rq.name)
        if exp is None:                      # 无期望值：能回答即过
            ok = len(actual) > 0
            note = "结果 %s" % actual
        else:                                # 有期望值：精确比对
            ok = actual == sorted(exp)
            note = "结果 %s（期望 %s）" % (actual, sorted(exp))
        all_ok = all_ok and ok
        print("%s %s  %s" % ("✅" if ok else "❌", rq.name, note))

    print("\n" + ("验收通过：CQ 全绿 ✅" if all_ok else "存在失败项 ❌"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
