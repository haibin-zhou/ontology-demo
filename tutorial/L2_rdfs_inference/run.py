"""L2：RDFS 推理现场——数据只写了 2 条事实，看推理机补出多少。"""
from rdflib import Graph, Namespace, RDF, RDFS
import owlrl

ECAT = Namespace("https://demo.local/ecat#")

g = Graph()
g.parse("onto.ttl", format="turtle")
g.parse("data.ttl", format="turtle")
before = set(g)

owlrl.DeductiveClosure(owlrl.RDFS_Semantics, axiomatic_triples=False).expand(g)
new = sorted(set(g) - before)

print("数据只写了 2 条事实。RDFS 推理补出了（已滤掉 rdfs 自身的公理噪音）：\n")
NOISE_OBJ = {str(RDFS.Resource), str(RDF.Property), str(RDFS.Class)}
for s, p, o in new:
    # 只关心我们命名空间里的"业务知识"：滤掉 xx a rdfs:Resource / rdf:Property
    # 和 A subX A 这类自反三元组
    if str(s).startswith(str(ECAT)) and str(o) not in NOISE_OBJ and s != o:
        fmt = lambda x: x.split("#")[-1] if "#" in str(x) else x.split("/")[-1]
        print("  %s --%s--> %s" % (fmt(s), fmt(p), fmt(o)))

print("\n逐条解释：")
print("  sku1 是 RunningShoe →（subClassOf ×2）→ sku1 也是 Footwear、Product")
print("  sku1 flagshipSoldBy m_alpha →（subPropertyOf）→ sku1 soldBy m_alpha")
print("  soldBy 的 domain 是 SKU → 用它的 sku1 自动获得类型 SKU")
print("  soldBy 的 range 是 Merchant → 被指向的 m_alpha 自动获得类型 Merchant")
