"""幽灵属性检查：数据/查询里用了、但本体没声明的谓语。

为什么需要它（案例实测教训）：本体里把属性改名，SPARQL 照样能查出旧数据——
破坏变更不会炸，而是静默分裂。这道检查抓"声明与使用脱钩"。
用法：python3 check_ghost.py
"""
import sys
from pathlib import Path

from rdflib import Graph, RDF, OWL

BASE = Path(__file__).parent


def declared_terms(ont):
    terms = set()
    for t in (OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty):
        terms |= {str(s) for s in ont.subjects(RDF.type, t)}
    terms |= {str(s) for s in ont.subjects(OWL.inverseOf, None)}
    terms |= {str(s) for s in ont.subjects(OWL.propertyChainAxiom, None)}
    return terms


def main():
    ont = Graph().parse(str(BASE / "ontology" / "domain.ttl"), format="turtle")
    declared = declared_terms(ont)

    base_iri = None
    for line in (BASE / "project.yml").read_text(encoding="utf-8").splitlines():
        if line.startswith("base_iri:"):
            base_iri = line.split(":", 1)[1].strip().strip('"').strip("'")
    ghosts = []

    data_file = BASE / "data" / "catalog.ttl"
    if data_file.exists():
        data = Graph().parse(str(data_file), format="turtle")
        for p in {str(p) for _, p, _ in data}:
            if base_iri and p.startswith(base_iri) and p not in declared:
                ghosts.append(("data", p))

    if ghosts:
        print("❌ 发现幽灵属性（数据在用、本体没声明）：")
        for src, p in ghosts:
            print("   [%s] %s" % (src, p.split("#")[-1]))
        return 1
    print("✅ 无幽灵属性：数据与本体声明一致")
    return 0


if __name__ == "__main__":
    sys.exit(main())
