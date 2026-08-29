"""规则层内化验证：bootstrap 骨架 + 语义补丁 + 数据库物化数据，
逐条验证 L2/L3 的六个武器是否全部生效。"""
from rdflib import Graph, Namespace, URIRef
import owlrl

B = "https://demo.local/ecat/"
fmt = lambda x: str(x).replace(B, ":")

g = Graph()
g.parse("bootstrap_full.ttl", format="xml")   # 数据库反向生成的骨架
g.parse("semantic_patch.ttl")                  # 手写语义补丁（规则层）
g.parse("materialized_full.ttl")               # H2 商品中台物化的实例

before = len(g)
owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                       axiomatic_triples=False).expand(g)
print("骨架+数据 %d 条 → 推理后 %d 条（新增 %d）\n" % (before, len(g), len(g) - before))

checks = []

def check(name, sparql, expect_desc):
    rows = sorted(set(tuple(fmt(v) for v in r) for r in g.query(sparql)))
    ok = len(rows) > 0
    checks.append(ok)
    print("%s %s" % ("✅" if ok else "❌", name))
    for r in rows[:6]:
        print("     %s" % " | ".join(r))
    print("     （验证点：%s）\n" % expect_desc)

check("L2-① 类层级：所有 SKU 自动是 SellableItem",
      "SELECT ?s WHERE { ?s a <%sSellableItem> }" % B,
      "8 个 SKU 实例全部出现")

check("L2-② domain/range：ref-PRODUCT_ID 的两端类型",
      "SELECT ?s ?p WHERE { ?s a <%sSKU> . ?p a <%sPRODUCT> . "
      "?s <%s> ?p }" % (B, B, B + "SKU#ref-PRODUCT_ID"),
      "SKU 和 PRODUCT 的类型由属性两端自动确认")

check("L3-① 互逆：SPU 反向查出它的 SKU（数据里只写了外键正向）",
      "SELECT ?sku WHERE { <%sPRODUCT/ID=1> <%shasSKU> ?sku }" % (B, B),
      "PRODUCT/ID=1 → SKU/ID=1")

check("L3-② 传递：跑步鞋（cat3）的全部祖先类目",
      "SELECT ?a WHERE { <%sCATEGORY/ID=3> <%s> ?a }"
      % (B, B + "CATEGORY#ref-PARENT_ID"),
      "应含 cat2 跑步装备 + cat1 运动户外（两跳）")

check("L3-③a 属性链：SKU 的品牌（SKU→SPU→品牌，两步压缩成一步）",
      "SELECT ?b WHERE { <%sSKU/ID=1> <%sskuBrand> ?b }" % (B, B),
      "SKU/ID=1 → BRAND/ID=1（StrideMax）")

check("L3-③b 授权链：商家被授权的品牌（穿过授权书中间表）",
      "SELECT ?b WHERE { <%sMERCHANT/ID=1> <%sauthorizedBrand> ?b }" % (B, B),
      "MERCHANT/ID=1 → BRAND/ID=1（中间穿过 BRAND_AUTHORIZATION 表）")

print("=" * 50)
print("总结：%d/6 个规则武器全部生效" % sum(checks) if all(checks)
      else "有未生效项：%d/6" % sum(checks))
