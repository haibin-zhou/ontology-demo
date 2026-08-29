"""S9 验收：六个胜任力问题的最终回归测试。

每个 CQ 一个 SPARQL（用字符串模板注入阈值），
跑在 本体+数据+推理物化 的完整图上。全部命中即验收通过。
"""
import datetime as dt
import json
from pathlib import Path
from rdflib import Graph
import owlrl

BASE = Path(__file__).parent
T = json.loads((BASE / "rules" / "thresholds.json").read_text(encoding="utf-8"))
AS_OF = dt.date.fromisoformat(T["asOfDate"])
P = "PREFIX : <https://demo.local/ecat#>\nPREFIX xsd: <http://www.w3.org/2001/XMLSchema#>\n"

CQS = {
  "CQ1 大促选品（GMV≥%d 且 毛利≥%s 且 资质有效）" % (T["promo"]["minGmv30d"], T["promo"]["minGrossMargin"]):
    P + """SELECT DISTINCT ?sku WHERE {
      ?sku a :SKU ; :gmv30d ?g ; :grossMargin ?m ; :hasCertification ?c .
      ?c :validUntil ?exp .
      FILTER(?g >= %d && ?m >= %s && ?exp > "%s"^^xsd:date) }"""
    % (T["promo"]["minGmv30d"], T["promo"]["minGrossMargin"], AS_OF),

  "CQ2 滞销治理（周转>%d天 且 GMV<%d）" % (T["slowMoving"]["inventoryDaysGt"], T["slowMoving"]["gmv30dLt"]):
    P + """SELECT DISTINCT ?sku WHERE {
      ?sku a :SKU ; :inventoryDays ?d ; :gmv30d ?g .
      FILTER(?d > %d && ?g < %d) }"""
    % (T["slowMoving"]["inventoryDaysGt"], T["slowMoving"]["gmv30dLt"]),

  "CQ3 价保检查（报名价 > 30天最低价 的报名单）":
    P + """SELECT ?enr ?sku WHERE {
      ?enr a :PromoEnrollment ; :enrollsSKU ?sku ; :promoPrice ?p .
      ?sku :minPrice30d ?min . FILTER(?p > ?min) }""",

  "CQ4 授权预警（%d 天内到期的授权书）" % T["authorization"]["expiringWithinDays"]:
    P + """SELECT ?merchant ?auth ?brand WHERE {
      ?merchant :authorizedBrand ?brand ; :holdsAuthorization ?auth .
      ?auth :validUntil ?exp .
      FILTER(?exp > "%s"^^xsd:date && ?exp <= "%s"^^xsd:date) }"""
    % (AS_OF, AS_OF + dt.timedelta(days=T["authorization"]["expiringWithinDays"])),

  "CQ5 新品扶持（上架≤%d天 且 GMV≥%d）" % (T["newProduct"]["listedWithinDays"], T["newProduct"]["minGmv30d"]):
    P + """SELECT DISTINCT ?sku WHERE {
      ?sku a :SKU ; :listedDate ?d ; :gmv30d ?g .
      FILTER(?d >= "%s"^^xsd:date && ?g >= %d) }"""
    % (AS_OF - dt.timedelta(days=T["newProduct"]["listedWithinDays"]),
       T["newProduct"]["minGmv30d"]),

  "CQ6 资质排查（无任何质检报告的在售 SKU）":
    P + """SELECT DISTINCT ?sku WHERE {
      ?sku a :SKU . FILTER NOT EXISTS { ?sku :hasCertification ?c } }""",
}

all_ok = True

def main():
    g = Graph()
    g.parse(str(BASE / "ontology" / "running.ttl"), format="turtle")
    g.parse(str(BASE / "data" / "catalog.ttl"), format="turtle")
    before = len(g)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                           axiomatic_triples=False).expand(g)
    print("图规模：%d → %d（推理物化 %d 条）\n" % (before, len(g), len(g) - before))
    all_ok = True
    for title, q in CQS.items():
        rows = sorted(set(" | ".join(str(v).split("#")[-1] for v in r) for r in g.query(q)))
        ok = len(rows) > 0
        all_ok = all_ok and ok
        print("%s %s" % ("✅" if ok else "❌", title))
        for r in rows:
            print("   → %s" % r)
        print()
    print("=" * 50)
    print("验收结论：6/6 CQ 全部可回答 ✅" if all_ok else "存在未达标 CQ ❌")


if __name__ == "__main__":
    main()
