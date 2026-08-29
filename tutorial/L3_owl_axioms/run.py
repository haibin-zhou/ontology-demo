"""L3：OWL 四大公理逐个现场演示。"""
from rdflib import Graph, Namespace
import owlrl

ECAT = Namespace("https://demo.local/ecat#")
fmt = lambda x: x.split("#")[-1] if "#" in str(x) else str(x)

g = Graph()
g.parse("onto.ttl", format="turtle")
g.parse("data.ttl", format="turtle")
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                       axiomatic_triples=False).expand(g)

print("【武器一：传递性】数据只写了相邻两层类目，推理后：")
q = "PREFIX : <https://demo.local/ecat#> SELECT ?a ?b WHERE { ?a :subCategoryOf ?b }"
for a, b in g.query(q):
    print("  %s ⊂ %s" % (fmt(a), fmt(b)))

print("\n【武器二：互逆】数据只写了 p1 --hasSKU--> sku1，反方向自动成立：")
q = "PREFIX : <https://demo.local/ecat#> SELECT ?s ?p WHERE { ?s :isSKUOf ?p }"
for s, p in g.query(q):
    print("  %s --isSKUOf--> %s" % (fmt(s), fmt(p)))

print("\n【武器三：属性链】sku1 的品牌，数据里没人写过：")
q = "PREFIX : <https://demo.local/ecat#> SELECT ?s ?b WHERE { ?s :skuBrand ?b }"
for s, b in g.query(q):
    print("  %s --skuBrand--> %s  （链：sku1 →isSKUOf→ p1 →madeBy→ brand_stride）"
          % (fmt(s), fmt(b)))

print("\n【武器四：互斥】OWL-RL 不会'报错'，用查询主动抓矛盾：")
q = """PREFIX : <https://demo.local/ecat#>
SELECT ?x WHERE { ?x a :ActiveProduct ; a :DelistedProduct }"""
hits = [fmt(r[0]) for r in g.query(q)]
print("  矛盾实例：%s" % (hits if hits else "无"))
print("  注意：这是'查询发现'而非'推理机报错'——开放世界下要主动出击。")
print("  （L6 会演示工业级做法：ROBOT + ELK 推理机直接让 CI 失败）")
