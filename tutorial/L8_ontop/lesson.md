# L8 Ontop Bootstrap：从现有数据库反向生成本体（答案的现场版）

> 这一课回答的问题是：**本体第一层的信息，能不能从工程里已有的领域建模生成？**
> 答案：骨架可以全自动，语义必须人工补。下面是完整证据链。

## 实验设计

`schema.sql` 模拟了一个"商品中台"关系库：6 张表（category 自引用类目树、brand、
merchant、brand_authorization、product、sku），`data.sql` 灌了少量数据。

## 运行步骤（全部实测通过）

```bash
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
cd ontology-demo/tutorial/L8_ontop

# ① 建 H2 数据库（Ontop 自带的 JDBC 驱动在 tools/ontop-cli/jdbc/h2.jar）
java -cp ../../tools/ontop-cli/jdbc/h2.jar org.h2.tools.RunScript \
  -url "jdbc:h2:./shop_db" -user sa -script schema.sql
java -cp ../../tools/ontop-cli/jdbc/h2.jar org.h2.tools.RunScript \
  -url "jdbc:h2:./shop_db" -user sa -script data.sql

# ② 一键 bootstrap：数据库 schema → 本体 + 映射
../../tools/ontop-cli/ontop bootstrap \
  -b "https://demo.local/ecat/" \
  -p db.properties -m bootstrap.obda -t bootstrap_ontology.ttl

# ③ 物化：15 行关系数据 → 95 条三元组（187ms）
../../tools/ontop-cli/ontop materialize \
  -m bootstrap.obda -p db.properties -o materialized.rdf
riot --output turtle materialized.rdf > materialized.ttl
```

## 实验结果：生成了什么、没生成什么

**bootstrap 自动生成的（骨架，约 60%）：**

| 数据库元素 | 生成结果 |
|---|---|
| 6 张表 | 6 个 `owl:Class`（SKU、PRODUCT、BRAND、CATEGORY、MERCHANT、BRAND_AUTHORIZATION） |
| 7 个外键 | 7 个 `owl:ObjectProperty`（如 `SKU#ref-PRODUCT_ID`） |
| 23 个字段 | 23 个 `owl:DatatypeProperty`（如 `SKU#SALES_30D`） |
| 每行数据 | 三元组（`SKU/ID=101` → sales 120、属于 PRODUCT/ID=1） |

**生成不了的（语义，那 40%，也正是手写 category.ttl 里最值钱的部分）：**

| 手写本体有 | bootstrap 没有 | 为什么生成不了 |
|---|---|---|
| `subCategoryOf` 是**传递的** | ❌ | parent_id 只是个自引用外键，schema 不说"可传递" |
| `skuBrand` **属性链**（SKU→SPU→品牌） | ❌ | 两个外键的组合语义只在业务认知里 |
| `authorizedBrand` **授权链** | ❌ | 同上 |
| `ActiveProduct`/`DelistedProduct` **互斥** | ❌ | 业务规则，库里没有 |
| 中文 `rdfs:label`、业务注释 | ❌ | 表没有注释就生成不了（有 COMMENT 的库会带上） |
| 语义化命名（`madeBy`） | ❌ | 只有 `PRODUCT#ref-BRAND_ID` 这种机械名 |
| domain/range 的精确类型 | ⚠️ 粗糙 | 能推出大致范围，但粒度粗 |
| NOT NULL/唯一约束 → SHACL | ❌ | bootstrap 不生成 shapes，需另做 |

## 结论（也是练习）

**正确姿势 = bootstrap 生成骨架 → 领域专家/LLM 补语义 → CQ 回归验证。**

练习：打开 `bootstrap_ontology.ttl` 和 `../../ontology/category.ttl` 对照，
把后者里的三条语义公理（传递性、两条属性链、disjointWith）"翻译"成前者的命名
（如 `CATEGORY#ref-PARENT_ID` 声明为 TransitiveProperty），
再用 `ontop materialize` + owlrl 推理验证链公理生效。

## 进阶实验：规则层内化（L2/L3 在数据库数据上的完整版）

全量数据集（9 表，与 `data/catalog.ttl` 逐字段对齐）已入库：
`schema_full.sql` + `data_full.sql` 重建 `shop_db`，重新 bootstrap + materialize
（242 条三元组），然后用**手写语义补丁** `semantic_patch.ttl` 补齐规则层，
`apply_patch.py` 逐条验证——**6/6 全部生效**：

| 规则武器 | 补丁里的一行声明 | 验证结果 |
|---|---|---|
| L2 类层级 | `SKU ⊂ SellableItem` | 8 个 SKU 全部自动获得新类型 |
| L2 domain/range | ref-PRODUCT_ID 两端类型 | 用属性即推断类型 |
| L3 互逆 | `hasSKU = inverse(ref-PRODUCT_ID)` | SPU 反查出 SKU |
| L3 传递 | `ref-PARENT_ID` 可传递 | 跑步鞋祖先 = 跑步装备 + 运动户外 |
| L3 属性链 | `ref-PRODUCT_ID ∘ ref-BRAND_ID → skuBrand` | SKU/ID=1 直达 BRAND/ID=1 |
| L3 授权链 | `hasAuthorization ∘ ref-BRAND_ID → authorizedBrand` | 商家穿过中间表直达品牌 |

关键体验：**补丁只有约 20 行声明，没碰一行数据，320 条三元组推理出 886 条**。
这就是"规则与数据分离"——改规则改的是本体，不是数据。

运行：

```bash
cd ontology-demo/tutorial/L8_ontop
../../.venv/bin/python apply_patch.py
```

踩坑记录：Ontop 生成的 IRI 含 `#`（如 `SKU#ref-PRODUCT_ID`），在 Turtle 补丁里
必须写 `<完整IRI>` 不能用前缀缩写；bootstrap 输出的 `.ttl` 实际是 RDF/XML，
rdflib 读取时要显式 `format="xml"`。


- `ontop endpoint`：不物化，直接起 SPARQL 服务实时查询数据库（虚拟化路线）；
- 接真实 MySQL/PG：换 db.properties 里的 jdbc.url 和驱动即可；
- LLM 的接入点：把 bootstrap 草稿 + 业务文档喂给模型，让它提议"哪些关系应声明
  传递/互逆/互斥"，人审后合入——这就是调研里说的 "LLM as ontology oracle"。
