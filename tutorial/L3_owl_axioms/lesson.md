# L3 OWL 公理：从"分类"到"关系推理"

## 概念

RDFS 会推理"是什么"（类型），OWL 开始推理"怎么关联"。本课四个公理是实战中最常用的：

| 公理 | 一句话 | 业务例子 |
|---|---|---|
| `owl:TransitiveProperty` | A⊂B 且 B⊂C ⇒ A⊂C | 类目树、组织架构、地理包含 |
| `owl:inverseOf` | hasSKU 的反面是 isSKUOf | 双向查询不用维护两份数据 |
| `owl:propertyChainAxiom` | A→B→C 压缩成 A→C | "SKU 的品牌"= SKU→SPU→品牌 |
| `owl:disjointWith` | 两类不可能有共同实例 | 在售 vs 已下架、男 vs 女 |

## 运行

```bash
cd ontology-demo/tutorial/L3_owl_axioms
../../.venv/bin/python run.py
```

预期输出（四个武器依次展示）：

```
【武器一：传递性】数据只写了相邻两层类目，推理后：
  cat_running_shoes ⊂ cat_running_gear
  cat_running_gear ⊂ cat_sports_outdoor
  cat_running_shoes ⊂ cat_sports_outdoor   ← 这条是推出来的

【武器二：互逆】...
  sku1 --isSKUOf--> p1                      ← 数据里只写了反向的 hasSKU

【武器三：属性链】...
  sku1 --skuBrand--> brand_stride           ← 链：sku1 →isSKUOf→ p1 →madeBy→ brand_stride

【武器四：互斥】...
  矛盾实例：['bad_sku']
```

## 观察点

1. **属性链是"业务预JOIN"**。数据库里"查 SKU 的品牌"要写 JOIN；本体里声明一次
   链公理，所有实例自动有直达边。DEMO 的 Agent 能直接答"这鞋什么牌子"，靠的就是它。
2. **互斥 ≠ 校验**。注意演示里矛盾实例是靠 SPARQL 查询抓出来的——OWL-RL 推理机
   不会主动喊停。想要"一写脏数据就炸"，两条路：SHACL（L4，拦在写入前）或
   DL 推理机（L6 的 `robot reason`，跑 CI 时报 inconsistent）。
3. 推理是有向无环的"单调增长"：物化只加不减，所以适合**写入时物化、查询时直接用**。

## 练习

1. 在 data.ttl 加 `:cat_trail_shoes :subCategoryOf :cat_running_shoes .`，
   重跑，观察它自动挂到几个祖先下。
2. 声明一条新链公理："商家 --销售→ SKU --属于→ SPU ⇒ 商家 --经营→ SPU"，
   并造数据验证。提示：`owl:propertyChainAxiom ( :sells :isSKUOf )`。
3. 把 bad_sku 的矛盾删掉，然后故意给两个**类目**声明 disjointWith，
   再让一个 SKU 同时属于它们，观察查询结果。
