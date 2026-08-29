"""推理 X 光：把语义补丁里的每条公理 → 它触发的 OWL 2 RL 规则 → 产出的三元组，
逐条摊开。让你看到推理机"脑子里"到底跑了什么。"""
from collections import Counter, defaultdict
from rdflib import Graph, Namespace, URIRef, RDF, RDFS
import owlrl

B = "https://demo.local/ecat/"
NS = {
    "http://www.w3.org/1999/02/22-rdf-syntax-ns#": "rdf:",
    "http://www.w3.org/2000/01/rdf-schema#": "rdfs:",
    "http://www.w3.org/2002/07/owl#": "owl:",
}
def fmt(x):
    x = str(x).replace(B, ":")
    for full, short in NS.items():
        x = x.replace(full, short)
    return x

# ============================================================
# 第一部分：我们的公理 ↔ OWL 2 RL 规则 对照表
# ============================================================
print("=" * 66)
print("第一部分：我们写的公理，对应推理机里的哪条规则")
print("=" * 66)
RULES = [
    ("ecat:SKU ⊂ ecat:SellableItem", "cax-sco（类包含传播）",
     "IF  x 的类型是 SKU  且  SKU ⊂ SellableItem\n"
     "       THEN  x 的类型也是 SellableItem"),
    ("ref-PRODUCT_ID 的 domain=SKU, range=PRODUCT", "prp-dom / prp-rng",
     "IF  a --ref-PRODUCT_ID--> b\n"
     "       THEN  a 的类型是 SKU  且  b 的类型是 PRODUCT"),
    ("hasSKU = inverse(ref-PRODUCT_ID)", "prp-inv1 / prp-inv2",
     "IF  a --ref-PRODUCT_ID--> b\n"
     "       THEN  b --hasSKU--> a   （反向边自动生成）"),
    ("ref-PARENT_ID 是 TransitiveProperty", "prp-trp（传递规则）",
     "IF  a --PARENT--> b  且  b --PARENT--> c\n"
     "       THEN  a --PARENT--> c   （反复触发直到不动点）"),
    ("skuBrand = chain(ref-PRODUCT_ID, ref-BRAND_ID)", "prp-spo2（属性链规则）",
     "IF  a --ref-PRODUCT_ID--> p  且  p --ref-BRAND_ID--> b\n"
     "       THEN  a --skuBrand--> b"),
    ("authorizedBrand = chain(hasAuthorization, ref-BRAND_ID)", "prp-spo2（同上，链内含逆属性）",
     "IF  m --hasAuthorization--> au  且  au --ref-BRAND_ID--> b\n"
     "       THEN  m --authorizedBrand--> b"),
]
for axiom, rule, logic in RULES:
    print("\n公理：%s" % axiom)
    print("  触发规则：%s" % rule)
    print("  规则逻辑：%s" % logic.replace("\n", "\n           "))

# ============================================================
# 第二部分：跑推理，把新增三元组按"是哪条规则产的"分类
# ============================================================
print("\n" + "=" * 66)
print("第二部分：推理产物分类统计（886 - 320 = 566 条都是什么）")
print("=" * 66)

def load(with_patch):
    g = Graph()
    g.parse("bootstrap_full.ttl", format="xml")
    g.parse("materialized_full.ttl")
    if with_patch:
        g.parse("semantic_patch.ttl")
    return g

# 推理前：骨架+数据，以及骨架+数据+补丁 各自的三元组集合
g_plain = load(with_patch=False)
plain_asserted = set(g_plain)
g_full = load(with_patch=True)
full_asserted = set(g_full)

owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                       axiomatic_triples=False).expand(g_full)
inferred = g_full - full_asserted          # 纯推理产物

# 按谓语分桶
buckets = defaultdict(list)
for s, p, o in inferred:
    buckets[fmt(p)].append((fmt(s), fmt(o)))

BUSINESS_ORDER = [
    ":skuBrand", ":authorizedBrand", ":hasSKU", ":hasAuthorization",
    ":CATEGORY#ref-PARENT_ID", "rdf:type",
]
print("\n【业务知识类产物】（规则层公理直接产出的）")
for pred in BUSINESS_ORDER:
    rows = buckets.get(pred, [])
    if not rows:
        continue
    if pred == "rdf:type":
        # type 桶里只有"推到 SellableItem"是业务知识，其余是公理噪音
        rows = [r for r in rows if r[1] == ":SellableItem"]
        if not rows:
            continue
        print("\n  谓语 rdf:type → :SellableItem —— 共 %d 条（cax-sco 类包含传播）" % len(rows))
    else:
        print("\n  谓语 %s —— 共 %d 条" % (pred, len(rows)))
    for s, o in rows[:4]:
        print("    %s → %s" % (s, o))
    if len(rows) > 4:
        print("    ... 等共 %d 条" % len(rows))

print("\n【结构噪音类产物】（RDFS/OWL 公理自动铺的底座，业务上无增量）")
noise = Counter()
for pred, rows in buckets.items():
    if pred not in BUSINESS_ORDER:
        noise[pred] += len(rows)
for pred, n in noise.most_common(8):
    print("  %-40s %d 条" % (pred, n))

biz = len([r for r in buckets.get("rdf:type", []) if r[1] == ":SellableItem"])
biz += sum(len(buckets[p]) for p in BUSINESS_ORDER
           if p != "rdf:type" and p in buckets)
print("\n合计：推理新增 %d 条 = 业务知识 %d 条 + 结构噪音 %d 条"
      % (len(inferred), biz, len(inferred) - biz))
