# L1 RDF 与 Turtle：一切皆是三元组

## 概念

RDF 的数据模型只有一条规则：**任何事实都表示为（主语, 谓语, 宾语）三元组**。
Turtle 是 RDF 的人类可读写法。三种节点类型：

| 类型 | 长什么样 | 能当主语？ | 能当宾语？ |
|---|---|---|---|
| IRI（资源） | `:sku1` | ✅ | ✅ |
| 字面量（值） | `120`、`"499.00"^^xsd:decimal`、`"闪电跑鞋"@zh` | ❌ | ✅ |
| 空白节点 | `[ ... ]`（本教程不展开） | ✅ | ✅ |

Turtle 语法糖只有三个：`;`（同主语换谓语）、`,`（同主语同谓语换宾语）、`a`（= rdf:type）。

## 运行

```bash
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"   # Jena 需要 Java
cd ontology-demo/tutorial/L1_rdf_turtle

# ① 语法校验（CI 里卡 ttl 合法性的工具）
riot --validate data.ttl

# ② 规范化输出：把语法糖"展开"成最朴素的 N-Triples，一行一个三元组
riot --output nt data.ttl
```

预期输出（节选）——注意 `:sku1` 那 8 行声明被展开成了 9 条独立三元组：

```nt
<https://demo.local/ecat#sku1> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <https://demo.local/ecat#SKU> .
<https://demo.local/ecat#sku1> <https://demo.local/ecat#name> "闪电跑鞋"@zh .
<https://demo.local/ecat#sku1> <https://demo.local/ecat#sales30d> "120"^^<http://www.w3.org/2001/XMLSchema#integer> .
...
```

```bash
# ③ 查询：中文名 + 销量 > 50，按销量倒序
arq --data data.ttl --query query.rq
```

预期输出：

```
--------------------------
| sku   | name     | sales |
==========================
| :sku3 | "竞速碳板"@zh | 260 |
| :sku1 | "闪电跑鞋"@zh | 120 |
--------------------------
```

（sku2 销量 45 被过滤掉了。）

## 观察点

1. **前缀只是缩写**：`:sku1` 的真实身份是 `https://demo.local/ecat#sku1` 这个 IRI。
   两个系统只要用同一个 IRI，指的就一定是同一个东西——这是"语义互联"的地基。
2. **字面量有类型**：`120` 会被规范化为 `"120"^^xsd:integer`。类型决定了能不能做
   `?sales > 50` 这种比较——`"120"`（字符串）就比不了。
3. **`:madeBy` 的宾语是资源不是字符串**：`"StrideMax"` 和 `:brand_stride` 完全不同——
   前者是死文本，后者是"图里的一个节点"，还能继续长出自己的属性。
   **建模原则：还会被追问的东西，建模成资源（IRI）；只是展示的文本，用字面量。**

## 练习

1. 把 `:sales30d 120` 改成 `:sales30d "一百二"`，`riot --validate` 还能过吗？
   `arq` 的 `FILTER(?sales > 50)` 会怎样？（语法没错但语义错了——体会"格式合法 ≠ 数据正确"，
   这正是 L4 SHACL 存在的理由）
2. 给 `:brand_stride` 加一条 `:country "美国"` ，用 `arq` 查出所有美国品牌的 SKU。
   提示：`?sku :madeBy ?b . ?b :country "美国"`
