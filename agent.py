"""本体驱动的品类运营 Agent：演示"本体如何应用到智能体"。

架构要点（对应调研结论的四条落地原则）：
  1. 本体即上下文：system prompt 由本体自动编译生成（类/属性/关系/标签），
     不是手写文档——本体改了，Agent 的"世界观"随之更新；
  2. 本体即工具面：CQ（胜任力问题）是受治理的"标准动作"，
     自由 SPARQL 只读（SELECT/ASK/DESCRIBE），写操作一律禁止；
  3. 校验即护栏：SHACL / 一致性检查是 Agent 可调用的合规工具，
     Agent 回答"能不能报名大促"必须先过校验，不能凭感觉；
  4. 变更走提案：Agent 发现本体缺口只能 propose_ontology_change 写提案，
     由人审批（对接 evolve.py 的回归与回滚）——AI 看得到、提得出、但改不了。

用法：
  .venv/bin/python agent.py "哪些SKU可以报名大促？现有报名有没有违规？"
  .venv/bin/python agent.py            # 进入交互模式
"""
import json
import os
import re
import sys

import requests

from kg import KnowledgeGraph, BASE, ECAT
import governance
import evolve

# 凭证与模型配置：仓库根目录 llm_config.py（环境变量或本地 .env，见 .env.example）
sys.path.insert(0, str(BASE))
import llm_config as config  # noqa: E402

# 本机代理（127.0.0.1:7890）不稳定，所有外网调用绕开（主项目惯例）
SESSION = requests.Session()
SESSION.trust_env = False


# =============================================================================
# 1. 本体 → 系统提示词（本体即上下文）
# =============================================================================
def compile_ontology_context(kg: KnowledgeGraph):
    """从本体文件自动生成 Agent 的语义上下文。本体变更后重新编译即可。"""
    lines = ["【本体版本】%s" % kg.version(), "", "【类】"]
    q = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?c ?label ?comment WHERE {
  ?c a owl:Class .
  OPTIONAL { ?c rdfs:label ?label }
  OPTIONAL { ?c rdfs:comment ?comment }
  FILTER(STRSTARTS(STR(?c), "https://demo.local/ecat#"))
}"""
    for r in kg.ont.query(q):
        name = str(r[0]).split("#")[-1]
        label = str(r[1]) if r[1] else ""
        lines.append("- %s（%s）" % (name, label))

    lines.append("")
    lines.append("【属性】")
    q = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
SELECT ?p ?label ?dom ?rng WHERE {
  { ?p a owl:ObjectProperty } UNION { ?p a owl:DatatypeProperty }
  OPTIONAL { ?p rdfs:label ?label }
  OPTIONAL { ?p rdfs:domain ?dom }
  OPTIONAL { ?p rdfs:range ?rng }
  FILTER(STRSTARTS(STR(?p), "https://demo.local/ecat#"))
}"""
    for r in kg.ont.query(q):
        name = str(r[0]).split("#")[-1]
        dom = str(r[2]).split("#")[-1].split("/")[-1] if r[2] else "?"
        rng = str(r[3]).split("#")[-1].split("/")[-1] if r[3] else "?"
        label = str(r[1]) if r[1] else ""
        lines.append("- %s: %s → %s（%s）" % (name, dom, rng, label))

    lines.append("")
    lines.append("【可推导关系（推理机自动得出，查询时直接用）】")
    lines.append("- :subCategoryOf 传递闭包：查父类目自动含全部子类目实例")
    lines.append("- :skuBrand —— SKU 的品牌（由 SKU→SPU→品牌 属性链推出）")
    lines.append("- :authorizedBrand —— 商家被授权的品牌（由 商家→授权书→品牌 推出）")

    t = governance.load_thresholds()
    lines.append("")
    lines.append("【当前业务阈值（rules/thresholds.json，基准日 %s）】" % t["asOfDate"])
    lines.append("- 大促达标：近30天销量 ≥ %d 件 且 毛利率 ≥ %s 且 资质在有效期内"
                 % (t["promo"]["minSales30d"], t["promo"]["minGrossMargin"]))
    lines.append("- 滞销：库存周转 > %d 天 且 近30天销量 < %d 件"
                 % (t["slowMoving"]["inventoryDaysGt"], t["slowMoving"]["sales30dLt"]))
    lines.append("- 新品：%d 天内上架 且 销量 ≥ %d 件" % (
        t["newProduct"]["listedWithinDays"], t["newProduct"]["minSales30d"]))
    return "\n".join(lines)


def build_system_prompt(kg: KnowledgeGraph):
    cq_catalog = []
    for rq in sorted((BASE / "cq").glob("*.rq")):
        first = rq.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
        cq_catalog.append("- %s：%s" % (rq.name, first))

    return """你是跑步品类运营助手，服务于品类运营负责人。你的所有业务认知来自下方的领域本体（Ontology），不允许凭常识编造业务定义。

%s

【受治理的标准动作（CQ，优先使用 run_cq 调用）】
%s

【行为准则】
1. 回答业务问题优先调用 run_cq 跑标准动作；CQ 覆盖不了再用 sparql_select 自由查询（只读）。
2. 凡是涉及"合规/能不能报名/有没有违规"的问题，必须先调 validate_data 或 check_consistency，用校验结果说话。
3. SPARQL 中命名空间：PREFIX : <https://demo.local/ecat#>，xsd 同理。日期比较用 "$AS_OF" 格式字面量需带 ^^xsd:date，基准日见上方阈值段。
4. 如果你发现数据里出现了本体中没有的概念/属性，不要自己脑补定义——调用 propose_ontology_change 写提案，交给品类负责人审批。
5. 回答用中文，给出结论时附上依据（哪个查询/哪条校验）。
""" % (compile_ontology_context(kg), "\n".join(cq_catalog))


# =============================================================================
# 2. 工具面（本体即工具：读 = CQ/SPARQL，校验 = SHACL/一致性，写 = 仅提案）
# =============================================================================
def _guard_readonly(sparql):
    """只允许只读查询形式，拒绝一切写操作。"""
    head = re.sub(r"PREFIX[^\n]*\n", "", sparql, flags=re.IGNORECASE).strip().upper()
    return head.startswith(("SELECT", "ASK", "DESCRIBE", "CONSTRUCT"))


def make_tools(kg: KnowledgeGraph):
    def run_cq(name):
        thresholds = governance.load_thresholds()
        params = governance.build_params(thresholds)
        from string import Template
        path = BASE / "cq" / name
        if not path.exists():
            return {"error": "CQ 不存在，可用列表见系统提示"}
        sparql = Template(path.read_text(encoding="utf-8")).substitute(params)
        rows = [[str(v).split("#")[-1] if hasattr(v, "split") else str(v) for v in row]
                for row in kg.query(sparql)]
        return {"cq": name, "rows": rows, "sparql": sparql}

    def sparql_select(query):
        if not _guard_readonly(query):
            return {"error": "只允许 SELECT/ASK/DESCRIBE/CONSTRUCT 只读查询"}
        try:
            res = kg.query(query)
            if res.type == "ASK":
                return {"answer": bool(res)}
            rows = [[str(v) for v in row] for row in res]
            return {"vars": [str(v) for v in res.vars], "rows": rows[:50]}
        except Exception as e:
            return {"error": "SPARQL 执行失败：%s" % e}

    def validate_data():
        conforms, violations, _ = kg.validate()
        return {"conforms": conforms, "violations": violations}

    def check_consistency():
        return {"conflicts": governance.check_consistency(kg)}

    def propose_ontology_change(term, definition, reason):
        gaps = [{"term": term, "role": "predicate", "sample_subject": "(agent)",
                 "sample_object": definition}]
        proposal = evolve.write_proposal(kg, gaps)
        proposal["reason"] = "Agent 提案：%s；建议定义：%s" % (reason, definition)
        path = BASE / "proposals" / ("%s.json" % proposal["id"])
        path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"proposal_id": proposal["id"],
                "note": "提案已写入 proposals/，等待品类负责人审批（evolve.approve 会跑治理回归）"}

    handlers = {
        "run_cq": lambda a: run_cq(a["name"]),
        "sparql_select": lambda a: sparql_select(a["query"]),
        "validate_data": lambda a: validate_data(),
        "check_consistency": lambda a: check_consistency(),
        "propose_ontology_change": lambda a: propose_ontology_change(
            a["term"], a["definition"], a["reason"]),
    }

    specs = [
        {"type": "function", "function": {
            "name": "run_cq",
            "description": "运行一个受治理的胜任力问题（标准业务动作），返回查询结果",
            "parameters": {"type": "object",
                           "properties": {"name": {"type": "string",
                                                   "description": "CQ 文件名，如 cq1_promo_eligible.rq"}},
                           "required": ["name"]}}},
        {"type": "function", "function": {
            "name": "sparql_select",
            "description": "对知识图谱执行只读 SPARQL（SELECT/ASK/DESCRIBE/CONSTRUCT）。CQ 覆盖不了时用",
            "parameters": {"type": "object",
                           "properties": {"query": {"type": "string"}},
                           "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "validate_data",
            "description": "对实例数据跑 SHACL 合规校验（价保、资质、类目完整性等）",
            "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {
            "name": "check_consistency",
            "description": "检查数据中的逻辑矛盾（如同一商品既在售又已下架）",
            "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {
            "name": "propose_ontology_change",
            "description": "发现本体缺口时提交变更提案（Agent 无权直接改本体，必须人审）",
            "parameters": {"type": "object",
                           "properties": {
                               "term": {"type": "string", "description": "新术语名"},
                               "definition": {"type": "string", "description": "建议的语义定义"},
                               "reason": {"type": "string", "description": "为什么需要它"}},
                           "required": ["term", "definition", "reason"]}}},
    ]
    return handlers, specs


# =============================================================================
# 3. Agent 主循环（Kimi tool calling）
# =============================================================================
def _call_kimi(messages, tools):
    payload = {
        "model": config.KIMI_MODEL,
        "messages": messages,
        "tools": tools,
        "temperature": 1.0,  # kimi-k2.5 仅允许 temperature=1
    }
    url = config.KIMI_BASE_URL + "/chat/completions"
    headers = {"Authorization": "Bearer " + config.require("KIMI_API_KEY")}
    resp = SESSION.post(url, headers=headers, json=payload, timeout=120)
    if resp.status_code in (400, 404) and config.KIMI_FALLBACK_MODEL:
        print("[agent] 模型 %s 不可用（%s），回退 %s"
              % (payload["model"], resp.status_code, config.KIMI_FALLBACK_MODEL))
        payload["model"] = config.KIMI_FALLBACK_MODEL
        resp = SESSION.post(url, headers=headers, json=payload, timeout=120)
    resp.raise_for_status()
    return resp.json()


def chat(question, kg=None, verbose=True):
    kg = kg or KnowledgeGraph()
    kg.reason()
    handlers, specs = make_tools(kg)
    messages = [
        {"role": "system", "content": build_system_prompt(kg)},
        {"role": "user", "content": question},
    ]
    total_usage = {"prompt_tokens": 0, "completion_tokens": 0}

    for _ in range(8):  # 工具调用轮次上限
        data = _call_kimi(messages, specs)
        usage = data.get("usage") or {}
        for k in total_usage:
            total_usage[k] += usage.get(k, 0)
        msg = data["choices"][0]["message"]
        messages.append(msg)

        tool_calls = msg.get("tool_calls") or []
        if not tool_calls:
            cost = (total_usage["prompt_tokens"] * config.COST["kimi_input_per_mtok"]
                    + total_usage["completion_tokens"] * config.COST["kimi_output_per_mtok"]) / 1e6
            return msg.get("content", ""), total_usage, round(cost, 4)

        for tc in tool_calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"] or "{}")
            if verbose:
                print("  🔧 %s(%s)" % (name, json.dumps(args, ensure_ascii=False)[:120]))
            result = handlers[name](args) if name in handlers else {"error": "未知工具"}
            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": json.dumps(result, ensure_ascii=False),
            })
    return "（工具调用轮次耗尽）", total_usage, None


def main():
    if len(sys.argv) > 1:
        questions = [" ".join(sys.argv[1:])]
    else:
        print("品类运营 Agent（输入 quit 退出）")
        questions = []
        while True:
            q = input("\n你：").strip()
            if q.lower() in ("quit", "exit", ""):
                return
            questions.append(q)
            break  # 简化：交互模式也逐问处理

    kg = KnowledgeGraph()
    kg.reason()
    print("本体 %s 已装载（%d 类术语）" % (kg.version(), len(kg.declared_terms())))
    for q in questions:
        print("\n问：%s" % q)
        answer, usage, cost = chat(q, kg=kg)
        print("\n答：%s" % answer)
        print("\n（tokens: %s，估算 ¥%s）" % (usage, cost))


if __name__ == "__main__":
    main()
