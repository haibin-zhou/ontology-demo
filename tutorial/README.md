# 本体工程实操教程（7 课）

> 配套工具已全部装好：rdflib/owlrl/pyshacl（`.venv`）、Jena（brew）、ROBOT（`../tools/robot`）、
> Ontop（`../tools/ontop-cli/`）、Protégé（/Applications）。
> **每一课的命令都真实跑通过**，你照做就能得到同样的输出。

## 学习地图

```
L1 RDF/Turtle ──► L2 RDFS 推理 ──► L3 OWL 公理 ──► L4 SHACL 校验
   格式层            一级推理           三大武器           数据质量门
                                                        │
L7 Fuseki 服务化 ◄── L6 ROBOT CI ◄── L5 SPARQL 查询 ◄───┘
   对外服务           工程化              业务提问
```

- **L1–L3 是"语义怎么进数据"**：格式 → 分类推理 → 关系推理；
- **L4–L5 是"数据怎么被管住、被问出答案"**：校验 → 查询；
- **L6–L7 是"怎么变成工程系统"**：CI 门禁 → HTTP 服务。

## 每课结构

- `lesson.md` —— 讲解（概念 → 最小例子 → 运行 → 预期输出 → 观察点 → 练习）
- 数据/查询文件 —— 都是最精简的可运行实例
- 有 `run.py` / `run.sh` 的直接执行即可复现

## 建议节奏

每课 20–40 分钟。**先跑通，再改坏**——每课的"练习"都是让你故意制造问题，
观察工具的报错方式，这是建立直觉最快的路径。

| 课 | 主题 | 用什么工具 |
|---|---|---|
| L1 | RDF 与 Turtle 格式 | riot、arq |
| L2 | RDFS 推理（类层级、domain/range） | rdflib + owlrl |
| L3 | OWL 三大武器（传递/互逆/属性链/互斥） | rdflib + owlrl |
| L4 | SHACL 数据校验 | pyshacl |
| L5 | SPARQL 五种查询模式 | arq |
| L6 | ROBOT 工程化 CI | robot |
| L7 | Fuseki 图谱服务化 | fuseki-server + curl |
| L8 | 从数据库反向生成本体 + 规则层内化 | Ontop + H2 + owlrl |

学完回到上一级目录跑 `demo.py` 和 `agent.py`，你会看懂每一行在干什么。
