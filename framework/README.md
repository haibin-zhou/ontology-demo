# 企业本体落地框架（Ontology Delivery Framework）

> 从"跑步品类运营"案例抽象出的可规模化实施框架。
> 一条命令起项目、九站流程建本体、三道门禁保质量、提案制管演进。
>
> 配套：`scaffold.py`（项目脚手架）、`install_env.sh`（环境基线）、`templates/`（模板库）。
> 案例存档：`../guided/`（完整共建过程）、`../tutorial/`（L1-L8 学习教程）。

## 0. 什么时候用这个框架（立项评估）

满足越多越适合；≤2 项就别用本体，传统应用+数据库就够：

- [ ] 业务对象 ≥ 10 类且关系复杂（多对多、跨实体遍历）
- [ ] 业务规则多且频繁变化（每月有新规则）
- [ ] 需要"推理/检查"而不只是"查询/检索"
- [ ] 同一业务变更有多个入口（Web/移动/第三方/AI Agent）
- [ ] 监管要求决策可审计、可回溯
- [ ] 计划接 LLM/Agent 做业务自动化
- [ ] 术语歧义已经在跨部门造成实际损失（"销售额"三个口径）

## 1. 环境基线

```bash
bash install_env.sh   # 一键装齐：OpenJDK、Jena（arq/riot）、Fuseki、Protégé、
                      # ROBOT、Ontop、Python venv（rdflib/owlrl/pyshacl/requests）
```

国内网络提示：brew 走 USTC 镜像；GitHub 大文件下载需断点续传（`curl -C -`）。

## 2. 角色与职责（RACI）

| 角色 | 职责 | 典型人选 |
|---|---|---|
| 领域专家 | 裁决术语口径、确认 CQ、审批提案 | 业务负责人（如品类运营） |
| 本体工程师 | 类/属性/公理建模、CI 维护 | 架构师/资深后端 |
| 数据工程师 | 数据源接入、映射、物化管道 | 数据开发 |
| 治理官 | 版本发版、漂移看板、月度评审 | 数据治理/PMO |
| Agent 开发 | 工具面封装、提示词编译器 | AI 工程师 |

## 3. 九站建设流程（S1–S9）

| 站 | 建设内容 | 关键输入（人） | 产物（机器） | 验收 |
|---|---|---|---|---|
| S1 | 定场景 | 选一个最痛的决策 | 场景声明 | 一句话说清"做对哪类决策" |
| S2 | 胜任力问题 CQ | 确认/增删业务问题 | `cq/competency_questions.md` | 5-8 个可回答的问题 |
| S3 | 术语表 | 裁决口径歧义 | `glossary.md` | 每个指标有唯一定义 |
| S4 | 类与层级 | 类目树进本体 or 实例等结构决策 | `ontology/domain.ttl` 类骨架 | 类图评审通过 |
| S5 | 属性与关系 | 确认字段与关系方向 | 属性声明 | 覆盖全部 CQ 所需字段 |
| S6 | 规则公理 | 勾选传递/互逆/属性链/互斥 | 公理声明 | 推理演示可见效果 |
| S7 | 数据接入 | 给数据源/样例 | `mapping/` + `data/` | 实例入图、脏数据可见 |
| S8 | 校验规则 | 确认哪些是硬规则 | `ontology/shapes.ttl` | 埋的脏数据全被抓到 |
| S9 | CQ 回归 + Agent | 验收提问 | `run_cq.py` + `agent.py` | CQ 全绿 + Agent 答对 |

**铁律：每站先出草案、人裁决、机器落盘。本体文件头注释携带决策记录（审计痕迹）。**

## 4. 工程规范

### 4.1 目录规范（scaffold 生成）

```
<project>/
├── project.yml            # 项目身份：名称/命名空间/版本
├── cq/                    # 胜任力问题：.rq 查询 + expected.json 期望值
├── glossary.md            # 术语表（裁决记录）
├── ontology/domain.ttl    # T-Box：类/属性/公理
├── ontology/shapes.ttl    # SHACL 硬规则
├── mapping/               # Ontop .obda 映射（接数据库时）
├── data/                  # 物化的实例数据
├── rules/thresholds.json  # 业务阈值（与本体分离！改阈值不发版本）
├── proposals/             # 变更提案（审计）
├── versions/              # 历史版本存档
├── run_cq.py              # CQ 回归（通用）
├── check_ghost.py         # 幽灵属性检查（声明↔使用一致性）
├── ingest.py              # 自然语言录入：LLM 抽取 → 三道闸门 → 入库（通用）
├── agent.py               # 本体驱动 Agent（通用）
└── ci.sh                  # 三道门禁流水线
```

### 4.2 命名规范

- 类：PascalCase（`PromoEnrollment`）；属性：camelCase（`hasCertification`）
- IRI：`<base>#<Name>`，全项目一个 base IRI（写进 `project.yml`）
- 每个类/属性必须有 `rdfs:label`（中文）——Agent 上下文编译依赖它
- 实例 ID：业务可读（`sku1`）或系统主键，禁止混用

### 4.3 分层规范（最重要的架构纪律）

| 规则类型 | 放哪 | 反模式 |
|---|---|---|
| 结构语义（是什么/怎么关联） | OWL 公理 | 拿 OWL 约束当非空校验 |
| 数据校验（必填/范围/跨字段） | SHACL | 指望推理机拦脏数据 |
| 数值阈值（≥50、>60天） | `rules/thresholds.json` | 阈值烧进本体公理 |
| 业务提问（CQ） | SPARQL + `cq/` | 逻辑散在应用代码里 |
| 行为/流程（什么条件下做什么） | Agent 工具面/Action 层 | 给 Agent 裸 SQL |

### 4.4 版本管理规范

- **只加不改**：已发布 IRI 永不删除；废弃用 `owl:deprecated true`
- 变更分级：新增=MINOR 直接发；改名/删除/改基数=MAJOR，双写过渡
- 版本谱系：`owl:versionInfo` + `owl:priorVersion` + `owl:backwardCompatibleWith`
- 每次变更必走：提案（proposals/）→ 人审 → 三道门禁 → 升版本 → 存档（versions/）

## 5. 测试与质量门禁（CI）

`ci.sh` 三道门，缺一不可（案例实测：只跑①会漏掉"属性改名"这种静默分裂）：

1. **CQ 回归**（`run_cq.py`）：抓"查询结果变了"——语义破坏
2. **ROBOT 一致性**（`robot reason`）：抓"逻辑矛盾"——公理破坏
3. **幽灵属性检查**（`check_ghost.py`）：抓"声明与使用脱钩"——改名/删除

辅助门禁：`riot --validate`（语法）、`robot report`（缺 label 等质量项）、
SHACL 基线对比（变更不得引入新增违规，存量脏数据不阻断）。

## 6. 治理与演进

- **漂移看板**（月度评审）：无类目实例数、证照临期数、SHACL 违规数、CQ 通过率
- **自迭代闭环**：新数据出现未声明术语 → 检测 → 提案 → 人审 → 门禁 → 发版
  （LLM 可做"ontology oracle"辅助提议，人永远做裁决）
- **Agent 护栏**：本体编译进系统提示词；工具面只读 + CQ；变更只许写提案

## 7. 规模化路径

```
单场景 MVP（本框架默认）
   └─► 多域扩展：每域独立本体 + owl:imports 组合，共享上位概念单独成文件
        └─► 服务化：Fuseki/GraphDB 起 SPARQL 端点，Agent 走 HTTP
             └─► 联邦：跨企业/部门时中心只共享类型定义，数据留本地
```

选型决策树：数据能搬 → 物化进图库（GraphDB/Stardog）；不能搬 → Ontop 虚拟化；
要权限/审计/多团队 → 商业平台（Stardog/TopBraid）。

## 8. 快速开始

```bash
# ① 起项目骨架
python3 scaffold.py --name supplier-compliance --title "供应商合规审查" \
  --base-iri "https://example.com/sc#"

# ② 启动交互向导，一站一站走（进度自动保存，随时中断续走）
python3 wizard.py projects/supplier-compliance

# ③ 随时跑门禁
cd projects/supplier-compliance && bash ci.sh

# ④ 自然语言录入（本体建好后，业务人员直接说话入库）
python3 ingest.py "新签供应商宁波箱包厂，资质 2027-06 到期，主供旅行箱类目"
python3 ingest.py "……" --dry-run   # 只看抽取和校验结果，不入库
```

`ingest.py` 的纪律：**LLM 只做"提议"，入库权在确定性代码**——LLM 抽取成中间态
JSON 后，依次过三道闸门：①本体校验（类/属性存在、domain/range、类型）→
②SHACL（违规即回滚，存量业务违规只提示不阻断）→ ③幽灵检查（只写已声明谓词）。
LLM 找不到对应概念的信息会如实放进 `unsure` 列表，绝不硬编——这正是
"自迭代闭环"的入口：unsure 积累到一定程度就是本体变更提案的素材。

向导（`wizard.py`）每站的动作：**解释原则 → 收集输入 → 生成文件 → 立即校验**。
S1 场景 → S2 CQ → S3 术语裁决 → S4 类 → S5 属性 → S6 公理（传递/互逆/属性链/互斥
四个开关式提问）→ S7 数据接入 → S8 硬规则 → S9 门禁验收。
中途退出没关系：进度在 `projects/<name>/.wizard_state.json`，重跑自动续上。
