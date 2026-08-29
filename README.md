# 品类运营本体 DEMO（ontology-demo）

> 📖 **学习手册**：[`docs/工具学习手册.md`](docs/工具学习手册.md) —— 每个工具的原理、
> 实操命令（基于本 DEMO 文件）、在项目中的作用、工业级替代方案。
> 🎓 **实操教程**：[`tutorial/`](tutorial/README.md) —— 7 课循序渐进，每条命令都跑通过：
> L1 RDF/Turtle → L2 RDFS 推理 → L3 OWL 公理 → L4 SHACL → L5 SPARQL → L6 ROBOT CI → L7 Fuseki 服务化。
> 工具已装好：Protégé（/Applications）、ROBOT（`tools/robot`）、Jena + Fuseki（brew）、Ontop（`tools/ontop-cli/`）。

企业级 AI 落地中 OWL 本体工程的最小可运行闭环，场景为**电商跑步品类运营**
（大促选品 / 滞销治理 / 合规审查）。一条命令跑通四大能力：

| 能力 | 落点 | 文件 |
|---|---|---|
| **本体设计** | OWL 2 RL：类层级、传递性 `subCategoryOf`、属性链（SKU→SPU→品牌、商家→授权书→品牌）、`disjointWith` 互斥 | `ontology/category.ttl` |
| **知识管理** | 装载本体+实例，OWL-RL 前向链推理物化，SHACL 封闭世界校验，SPARQL 查询 | `kg.py` |
| **治理能力** | disjoint 一致性检查、CQ 回归测试（本体的单元测试）、漂移指标看板、变更审计日志、阈值与本体分离 | `governance.py`、`cq/`、`rules/thresholds.json` |
| **自迭代机制** | 新批次数据 → 检测本体缺口 → 生成提案 → 审批 → 应用并升版本 → 治理回归，退化自动回滚 | `evolve.py`、`data/incoming_batch.ttl` |
| **Agent 应用** | 本体自动编译为系统提示词；CQ/SHACL/SPARQL 为受治理工具面；本体变更只能写提案 | `agent.py` |

## Agent 层（本体如何应用到智能体）

```bash
.venv/bin/python agent.py "哪些SKU可以报名大促？现有报名有没有违规？"
.venv/bin/python agent.py            # 交互模式
```

四条落地原则（对应 Palantir 式实践）：

1. **本体即上下文**：system prompt 由本体自动编译（类/属性/关系/阈值），
   本体升级后 Agent 的"世界观"自动更新，不存在文档漂移；
2. **本体即工具面**：`run_cq`（受治理标准动作）+ `sparql_select`（只读自由查询，
   写操作被 `_guard_readonly` 拒绝），Agent 的能力边界由本体决定；
3. **校验即护栏**：`validate_data`（SHACL）/ `check_consistency`（disjoint）
   是 Agent 的工具，"能不能报名"必须用校验结果说话，不能凭生成感觉；
4. **变更走提案**：Agent 发现本体缺口只能 `propose_ontology_change` 写提案到
   `proposals/`，人审后走 `evolve.approve()`（含治理回归与回滚）——
   **AI 看得到、提得出、改不了**。

实测（Kimi，单次问答约 ¥0.07）：问"哪些SKU能报名大促、报名有没有违规"，
Agent 自主调用了 `run_cq` → `validate_data` → `check_consistency` →
两次 `sparql_select` 深挖细节，输出了带依据的整改清单；
问"新数据里有本体没有的字段怎么办"，Agent 主动走了提案流程而不是脑补定义。

凭证配置：复制 `.env.example` 为 `.env` 填入 `KIMI_API_KEY`（或直接用环境变量；
模型默认 `kimi-k3`，404 时回退 `kimi-k2.5`，可用 `KIMI_MODEL` 等环境变量覆盖）。


## 运行

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python demo.py              # 全流程（含自迭代，会把本体升到 1.1.0）
.venv/bin/python demo.py --no-evolve  # 只跑知识管理 + 治理，不改动本体
```

`ontology/category.ttl` 可直接用 [Protégé](https://protege.stanford.edu/) 打开查看和继续建模。

## 关键设计决策

- **OWL 管推理，SHACL 管校验**。OWL 是开放世界假设（"没记录"≠"假"），
  做不了"必填/非负"这类校验；SHACL 是封闭世界，是品类运营的"自动合规官"。
  两者混用是新手第一大坑。
- **业务阈值不进本体**。滞销线、动销达标线都在 `rules/thresholds.json`，
  运营调阈值走审批改配置，不需要发本体版本。
- **CQ 即测试**。`cq/*.rq` 是立项时写的胜任力问题翻成的 SPARQL，
  `cq/expected.json` 是期望结果——每次本体变更都跑回归，等价于本体的 CI。
- **回归只拦新增退化**。`evolve.approve()` 对比变更前后的 CQ/SHACL 结果，
  存量脏数据（演示数据中故意埋的违规）不阻断本体演进，只进漂移看板。
- **LLM 接入点**在 `evolve.detect_gaps()` 注释中标注：生产环境由 LLM 判断
  未识别术语的语义并草拟提案（ontology oracle 模式），DEMO 用确定性逻辑替代。

## 演示数据中故意埋的"脏数据"（用于展示治理能力）

| 实例 | 问题 | 被谁抓到 |
|---|---|---|
| `sku7` | 同时是"在售"和"已下架" | disjoint 一致性检查 |
| `enr2` | sku4 促销价 449 > 价保基线 439 | SHACL 价保规则 |
| `enr3` | sku6 无资质证书就报名大促 | SHACL 资质规则 |
| `sku5` | 缺所属类目 | SHACL + 漂移指标 |
| `auth_beta_pace` | 授权书 30 天内到期 | CQ4 预警 + 漂移指标 |

## 目录

```
ontology-demo/
├── ontology/category.ttl     # T-Box：本体（OWL 2 RL）
├── ontology/shapes.ttl       # SHACL 校验规则
├── data/catalog.ttl          # A-Box：实例数据（含故意脏数据）
├── data/incoming_batch.ttl   # 新批次数据（含未声明术语，触发自迭代）
├── rules/thresholds.json     # 业务阈值（与本体分离，可配置）
├── cq/*.rq + expected.json   # 胜任力问题 → SPARQL 回归测试
├── kg.py                     # 知识管理：装载/推理/校验/查询
├── governance.py             # 治理：一致性/CQ回归/漂移/审计日志
├── evolve.py                 # 自迭代：缺口检测→提案→审批→回归→回滚
├── agent.py                  # Agent 层：本体驱动的品类运营助手（Kimi tool calling）
├── proposals/                # 生成的本体变更提案
├── governance/changelog.jsonl# 变更审计（运行后生成）
└── demo.py                   # 一键串全流程
```
