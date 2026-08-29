# L4 SHACL：封闭世界的数据质量门

## 概念

回顾 L3 的遗留问题：OWL 是**开放世界**——"没写类目"不等于"违规"，推理机永远不拦你。
但业务需要拦：上架审核、大促报名、ETL 入库，都要"不满足规则就拒绝"。

SHACL（Shapes Constraint Language）就是干这个的，三个核心概念：

- **Shape**：一份"数据应该长什么样"的声明，绑定到目标（`sh:targetClass :SKU`）；
- **Constraint**：`sh:minCount`（必填）、`sh:maxCount`（唯一）、`sh:datatype`（类型）、
  `sh:minExclusive`（取值范围）……几十种内置约束；
- **`sh:sparql`**：内置约束表达不了的业务规则（如"促销价 ≤ 30天最低价"），
  用一段 SPARQL 表达，返回行即违规。

校验输出是一份标准的 ValidationReport（哪个节点、违反哪条、什么级别），
程序可以直接消费——这就是它能卡进流水线的原因。

## 运行

```bash
cd ontology-demo/tutorial/L4_shacl
../../.venv/bin/python run.py
```

预期输出：

```
=== 校验 data_ok.ttl（干净数据）===
结论：✅ 全部合规

=== 校验 data_bad.ttl（埋了 4 种违规）===
结论：❌ 发现 4 条违规
  ❌ sku_bad1 —— SKU 必须有名字
  ❌ sku_bad2 —— SKU 必须且只能挂一个叶子类目
  ❌ sku_bad3 —— 价格必须是正的小数
  ❌ sku_bad4 —— 击穿价保：促销价高于30天最低价
```

## 观察点

1. **OWL vs SHACL 的分工**（企业本体工程最容易搞混的一点）：

   | | OWL | SHACL |
   |---|---|---|
   | 世界观 | 开放世界（没写=未知） | 封闭世界（没写=违规） |
   | 用途 | 推理：补全隐含知识 | 校验：拦截不合规数据 |
   | 类比 | 逻辑学家 | 质检员 |

2. **`sh:sparql` 是逃生口**：跨字段、跨实体的业务规则都能表达，
   但规则越复杂性能越差——生产环境把热点规则写成内置约束，低频复杂的才用 SPARQL。
3. Shape 本身也是 RDF——意味着**校验规则和业务数据存在同一种格式里**，
   可以一起进 Git、一起被查询、一起被治理。

## 练习

1. 给 shapes.ttl 加一条：`:listedDate` 必填且必须是 `xsd:date`，
   然后在 data_bad.ttl 造一个缺失案例验证。
2. 把 sku_bad4 的 promoPrice 改成 699.00，重跑——价保违规应该消失（799→699 = 边界值）。
3. 进阶：写一条 SPARQL 约束"同一 SKU 不得挂在两个类目下"，
   注意它和 `sh:maxCount 1` 的等价性——体会内置约束其实是 SPARQL 的语法糖。
