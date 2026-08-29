"""L4：SHACL 校验现场——同一份规则，先验干净数据，再验脏数据。"""
from rdflib import Graph, Namespace, RDF
from pyshacl import validate

SH = Namespace("http://www.w3.org/ns/shacl#")


def check(data_file):
    data = Graph().parse(data_file, format="turtle")
    shapes = Graph().parse("shapes.ttl", format="turtle")
    conforms, report, _ = validate(data, shacl_graph=shapes, advanced=True)
    violations = []
    for r in report.subjects(RDF.type, SH.ValidationResult):
        focus = report.value(r, SH.focusNode)
        msg = report.value(r, SH.resultMessage)
        violations.append((str(focus).split("#")[-1], str(msg)))
    return conforms, violations


print("=== 校验 data_ok.ttl（干净数据）===")
conforms, violations = check("data_ok.ttl")
print("结论：" + ("✅ 全部合规" if conforms else "❌ 有违规"))
for f, m in violations:
    print("  ❌ %s —— %s" % (f, m))

print("\n=== 校验 data_bad.ttl（埋了 4 种违规）===")
conforms, violations = check("data_bad.ttl")
print("结论：" + ("✅ 全部合规" if conforms else "❌ 发现 %d 条违规" % len(violations)))
for f, m in violations:
    print("  ❌ %s —— %s" % (f, m))
