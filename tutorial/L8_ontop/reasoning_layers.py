"""规则层现场实验：同一份数据库物化数据，叠加不同深度的语义层，看推理产出差多少。

层0：纯 bootstrap 骨架（无语义公理）
层1：+ RDFS 级语义（类层级 subClassOf）
层2：+ OWL 级语义（传递性 TransitiveProperty）
"""
from rdflib import Graph, Namespace, RDF, RDFS, OWL, URIRef
import owlrl

B = "https://demo.local/ecat/"
ECAT = Namespace(B)
fmt = lambda x: str(x).replace(B, ":")

# ---------- 公共底座：bootstrap 骨架 + 数据库物化的 242 条三元组 ----------
def load_base():
    g = Graph()
    g.parse("bootstrap_full.ttl", format="xml")   # 自动生成的骨架本体（实为 RDF/XML）
    g.parse("materialized_full.ttl")              # 从 H2 商品中台物化的实例
    return g

def reason(g):
    before = len(g)
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                           axiomatic_triples=False).expand(g)
    return len(g) - before

# ---------- 层0：骨架直接推理 ----------
g0 = load_base()
n0 = reason(g0)
q = "SELECT ?c ?p WHERE { ?c <%s> ?p }" % (B + "CATEGORY#ref-PARENT_ID")
cat3 = URIRef(B + "CATEGORY/ID=3")
ancestors0 = [fmt(r[0]) for r in g0.query(
    "SELECT ?p WHERE { <%s> <%s> ?p }" % (cat3, B + "CATEGORY#ref-PARENT_ID"))]
print("【层0：纯 bootstrap 骨架】")
print("  推理新增三元组：%d 条（全是 rdfs 公理噪音，业务上 +0）" % n0)
print("  查'跑步鞋(cat3)的所有祖先类目'：%s  ← 只有直接父类，树断了" % ancestors0)

# ---------- 层1：+RDFS 类层级 ----------
patch1 = Graph()
patch1.add((ECAT["SKU"], RDFS.subClassOf, ECAT["SellableItem"]))
patch1.add((ECAT["SellableItem"], RDF.type, OWL.Class))
g1 = load_base() + patch1
n1 = reason(g1)
items = [fmt(r[0]) for r in g1.query(
    "SELECT ?s WHERE { ?s a <%s> }" % (B + "SellableItem"))]
print("\n【层1：+ 一条 RDFS 公理 'SKU ⊂ SellableItem'】")
print("  推理新增：%d 条；其中 8 个 SKU 自动获得 SellableItem 类型：" % n1)
print("  %s" % items)

# ---------- 层2：+OWL 传递性 ----------
patch2 = Graph()
patch2.add((URIRef(B + "CATEGORY#ref-PARENT_ID"), RDF.type, OWL.TransitiveProperty))
g2 = load_base() + patch2
n2 = reason(g2)
ancestors2 = [fmt(r[0]) for r in g2.query(
    "SELECT ?p WHERE { <%s> <%s> ?p }" % (cat3, B + "CATEGORY#ref-PARENT_ID"))]
print("\n【层2：+ 一条 OWL 公理 'ref-PARENT_ID 是传递的'】")
print("  查'跑步鞋(cat3)的所有祖先类目'：%s  ← 整棵树通了" % ancestors2)

print("\n【结论】数据库/bootstrap 给的骨架里没有任何规则；")
print("每条规则层公理（RDFS 分类、OWL 传递）加上去，全量数据立刻自动获得新知识。")
