# L2 RDFS 推理：声明一次，处处生效

## 概念

RDFS（RDF Schema）是 OWL 的"轻量前奏"，只有四个推理武器，但已经能解决 80% 的
"数据里没写、但人人都知道"的问题：

| 武器 | 声明 | 推理效果 |
|---|---|---|
| `rdfs:subClassOf` | 跑步鞋 ⊂ 鞋 ⊂ 商品 | 实例自动获得全部祖先类型 |
| `rdfs:subPropertyOf` | 旗舰店销售 ⊂ 销售 | 子属性的每条边自动升格 |
| `rdfs:domain` | soldBy 的主语必须是 SKU | 谁用了这个属性，谁自动获得类型 |
| `rdfs:range` | soldBy 的宾语必须是 Merchant | 被指向者自动获得类型 |

关键认知：**这些不是校验，是推理**。`domain` 不是说"非 SKU 用 soldBy 就报错"，
而是说"用了 soldBy 的东西，我就当它是个 SKU"。（想报错？那是 L4 SHACL 的事。）

## 运行

```bash
cd ontology-demo/tutorial/L2_rdfs_inference
../../.venv/bin/python run.py
```

预期输出：

```
数据只写了 2 条事实。RDFS 推理补出了：

  sku1 --type--> Footwear
  sku1 --type--> Product
  sku1 --type--> SKU
  sku1 --soldBy--> m_alpha
  m_alpha --type--> Merchant
  ...

逐条解释：
  sku1 是 RunningShoe →（subClassOf ×2）→ sku1 也是 Footwear、Product
  ...
```

## 观察点

1. **数据可以非常"瘦"**：写入方只说最少的事实（"sku1 是跑步鞋"），
   读取方查到的是完整的知识（"sku1 是商品"）。数据录入成本 ↓，查询能力 ↑。
2. 这就是为什么 L1 的数据里每个 SKU 都要写 `a :SKU`——因为 DEMO 的类层级浅，
   没有可推导的祖先。如果类目层级深，写一个叶子类型就够了。
3. `domain/range` 是双向的"类型推断器"：写数据的人忘了标类型也不怕。

## 练习

1. 在 `onto.ttl` 里加 `:CarbonPlateShoe rdfs:subClassOf :RunningShoe`，
   在 `data.ttl` 里加 `:sku9 a :CarbonPlateShoe`，重跑——sku9 应该自动是
   RunningShoe / Footwear / Product 四层类型。
2. 把 `:soldBy` 的 `rdfs:domain :SKU` 删掉再跑，sku1 的 `a :SKU` 还在吗？
   体会"类型从哪来"。
