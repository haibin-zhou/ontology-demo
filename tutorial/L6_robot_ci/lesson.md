# L6 ROBOT：把本体工程变成 CI 流水线

## 概念

前面几课都是"开发态"。工程化的核心问题是：**本体改了，怎么知道没把系统改挂？**
答案是和代码一样的——CI。ROBOT 就是本体界的 CI 工具，四个命令对应四道门：

| 门 | 命令 | 类比软件工程 |
|---|---|---|
| 语法门 | `riot --validate`（Jena） | 编译检查 |
| 一致性门 | `robot reason --reasoner ELK` | 类型检查：本体逻辑必须自洽 |
| 违规门禁 | `robot verify --queries x.rq` | 自定义 lint 规则 |
| 质量报告 | `robot report` | 代码质量扫描（缺 label/缺定义） |

`robot verify` 的机制值得理解：你给它一组 **SPARQL "违规查询"**——
"查出任何结果就算失败"——比如 violation.rq 查"既是 ActiveProduct 又是 DelistedProduct
的实例"。查询命中 = CI 红。这把"业务不允许出现的模式"变成了可执行的门禁。

## 运行

```bash
cd ontology-demo/tutorial/L6_robot_ci
bash run.sh
```

预期输出（注意步骤 3/4 的 FAIL 是**故意的**——主 DEMO 的数据里埋了 sku7 矛盾）：

```
== 步骤1：语法校验（riot）==
PASS
== 步骤2：本体自身一致性（robot reason / ELK）==
PASS：本体（T-Box）一致
== 步骤3：实例级矛盾检查 ==
FAIL：合并实例后逻辑不一致（sku7 既在售又已下架）——CI 在此拦截
== 步骤4：自定义违规门禁 ==
FAIL：发现违规实例 →
x
https://demo.local/ecat#sku7
== 步骤5：质量报告 ==
报告行数：57（节选前 5 行）
Level  Rule Name      Subject                       ...
ERROR  missing_label  ...#campaign                  ...
== 步骤6：格式转换 ==
PASS：已生成 /tmp/l6_category.owl
```

## 观察点

1. **两种"不一致"要分开**：步骤 2 查本体自身（T-Box），永远应该 PASS；
   步骤 3 查本体+数据合并（T-Box + A-Box），数据矛盾会在这里暴露。
   前者是"模型错了"，后者是"数据脏了"——处理方式完全不同。
2. 步骤 5 的报告对我们的真实本体报了 13 个 ERROR（缺 rdfs:label）——
   质量门不是摆设，它立刻在真实文件上找到了改进点。
3. 和 DEMO 的关系：`governance.py` 的 CQ 回归 + 一致性检查，就是这条流水线的
   Python 内嵌版；企业里把它搬到 GitHub Actions，本体 PR 自动跑 `run.sh`。

## 练习

1. 修掉矛盾：把 `data/catalog.ttl` 里 sku7 的 `a :ActiveProduct , :DelistedProduct`
   改成只保留一个，重跑 run.sh，步骤 3/4 应变 PASS。（改完记得改回来）
2. 给 `violation.rq` 加一条规则：查出"没有任何属性的孤儿实例"。
3. 看 `/tmp/l6_report.tsv` 全文，挑 3 个 missing_label 补进 `ontology/category.ttl`，
   重跑确认 ERROR 数下降。
