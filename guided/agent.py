"""S9 验收：把引导共建的本体接上 Agent。

复用 demo 的 Agent 模式，但所有数据/规则都指向 guided/ 工作区：
  - 本体即上下文：system prompt 由 guided/ontology/running.ttl 自动编译
  - 工具面：run_cq（六个 CQ）、validate_data（SHACL）、sparql_select（只读）、
            propose_ontology_change（提案制，写 guided/proposals/）

用法：
  ../.venv/bin/python agent.py "哪些SKU能报名大促？现有报名有没有违规？"
"""
import json
import re
import sys
import datetime as dt
from pathlib import Path

import requests
from rdflib import Graph, Namespace, RDF
import owlrl
from pyshacl import validate

BASE = Path(__file__).parent
# 向上找到仓库根目录的 llm_config.py（凭证与模型配置）
for _up in (BASE, *BASE.parents):
    if (_up / "llm_config.py").exists():
        sys.path.insert(0, str(_up))
        break
import llm_config as config                     # noqa: E402

ECAT = Namespace("https://demo.local/ecat#")
SESSION = requests.Session()
SESSION.trust_env = False                            # 绕开本机代理（项目惯例）


def load_graph():
    g = Graph()
    g.parse(str(BASE / "ontology" / "running.ttl"), format="turtle")
    g.parse(str(BASE / "data" / "catalog.ttl"), format="turtle")
    owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                           axiomatic_triples=False).expand(g)
    return g


def compile_context():
    """本体 → Agent 的世界观（label/comment 都是图里的三元组，直接读）。"""
    ont = Graph().parse(str(BASE / "ontology" / "running.ttl"), format="turtle")
    lines = []
    q = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?x ?label WHERE {
      { ?x a owl:Class } UNION { ?x a owl:ObjectProperty } UNION { ?x a owl:DatatypeProperty }
      OPTIONAL { ?x rdfs:label ?label }
      FILTER(STRSTARTS(STR(?x), "https://demo.local/ecat#")) } ORDER BY ?x"""
    for x, label in ont.query(q):
        lines.append("- %s（%s）" % (str(x).split("#")[-1], label or ""))
    t = json.loads((BASE / "rules" / "thresholds.json").read_text(encoding="utf-8"))
    lines.append("\n【业务阈值】动销=GMV：大促达标 GMV≥%d 且毛利≥%s；滞销=周转>%d天且GMV<%d；"
                 "新品=上架≤%d天且GMV≥%d；授权预警=%d天内。基准日 %s"
                 % (t["promo"]["minGmv30d"], t["promo"]["minGrossMargin"],
                    t["slowMoving"]["inventoryDaysGt"], t["slowMoving"]["gmv30dLt"],
                    t["newProduct"]["listedWithinDays"], t["newProduct"]["minGmv30d"],
                    t["authorization"]["expiringWithinDays"], t["asOfDate"]))
    return "\n".join(lines)


SYSTEM = """你是跑步品类运营助手。你的业务认知完全来自下面的本体，不允许凭常识编造定义。

【本体术语】
%s

【规则】
1. 业务问题优先调 run_cq；CQ 覆盖不了再用 sparql_select（只读）。
2. 涉及"合规/违规/能不能报名"必须先调 validate_data。
3. SPARQL 命名空间：PREFIX : <https://demo.local/ecat#>；日期比较带 ^^xsd:date，基准日见上。
4. 发现本体没有的概念，调 propose_ontology_change 写提案，不要自己编。
5. 中文回答，结论附依据。
"""


def make_tools(g):
    from run_cq import CQS  # 六个 CQ 的 title→SPARQL 映射

    def run_cq(name):
        for title, q in CQS.items():
            if name in title:
                rows = sorted(set(" | ".join(str(v).split("#")[-1] for v in r)
                                  for r in g.query(q)))
                return {"cq": title, "rows": rows}
        return {"error": "CQ 不存在，可选：CQ1~CQ6"}

    def sparql_select(query):
        head = re.sub(r"PREFIX[^\n]*\n", "", query, flags=re.IGNORECASE).strip().upper()
        if not head.startswith(("SELECT", "ASK", "DESCRIBE", "CONSTRUCT")):
            return {"error": "只允许只读查询"}
        try:
            res = g.query(query)
            if res.type == "ASK":
                return {"answer": bool(res)}
            return {"vars": [str(v) for v in res.vars],
                    "rows": [[str(v) for v in row] for row in res][:50]}
        except Exception as e:
            return {"error": str(e)}

    def validate_data():
        data = Graph().parse(str(BASE / "data" / "catalog.ttl"), format="turtle")
        shapes = Graph().parse(str(BASE / "ontology" / "shapes.ttl"), format="turtle")
        conforms, report, _ = validate(data, shacl_graph=shapes, advanced=True)
        SH = Namespace("http://www.w3.org/ns/shacl#")
        return {"conforms": conforms,
                "violations": [{"focus": str(report.value(r, SH.focusNode)).split("#")[-1],
                                "message": str(report.value(r, SH.resultMessage))}
                               for r in report.subjects(RDF.type, SH.ValidationResult)]}

    def propose_ontology_change(term, definition, reason):
        PROPOSALS = BASE / "proposals"
        PROPOSALS.mkdir(exist_ok=True)
        pid = "P" + dt.datetime.now().strftime("%Y%m%d%H%M%S")
        (PROPOSALS / (pid + ".json")).write_text(json.dumps({
            "id": pid, "term": term, "definition": definition,
            "reason": reason, "status": "pending",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"proposal_id": pid, "note": "提案已写入 guided/proposals/，等人审"}

    handlers = {"run_cq": lambda a: run_cq(a["name"]),
                "sparql_select": lambda a: sparql_select(a["query"]),
                "validate_data": lambda a: validate_data(),
                "propose_ontology_change": lambda a: propose_ontology_change(
                    a["term"], a["definition"], a["reason"])}
    specs = [
        {"type": "function", "function": {
            "name": "run_cq",
            "description": "运行一个胜任力问题（CQ1大促选品/CQ2滞销/CQ3价保/CQ4授权预警/CQ5新品/CQ6资质排查）",
            "parameters": {"type": "object",
                           "properties": {"name": {"type": "string", "description": "如 CQ1"}},
                           "required": ["name"]}}},
        {"type": "function", "function": {
            "name": "sparql_select", "description": "只读 SPARQL 自由查询（CQ 覆盖不了时用）",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                           "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "validate_data", "description": "SHACL 合规校验（类目/价保/资质/字段约束）",
            "parameters": {"type": "object", "properties": {}}}},
        {"type": "function", "function": {
            "name": "propose_ontology_change", "description": "本体缺概念时提交变更提案（需人审）",
            "parameters": {"type": "object", "properties": {
                "term": {"type": "string"}, "definition": {"type": "string"},
                "reason": {"type": "string"}}, "required": ["term", "definition", "reason"]}}},
    ]
    return handlers, specs


def chat(question):
    g = load_graph()
    handlers, specs = make_tools(g)
    messages = [{"role": "system", "content": SYSTEM % compile_context()},
                {"role": "user", "content": question}]
    for _ in range(8):
        resp = SESSION.post(config.KIMI_BASE_URL + "/chat/completions",
                            headers={"Authorization": "Bearer " + config.require("KIMI_API_KEY")},
                            json={"model": config.KIMI_MODEL, "messages": messages,
                                  "tools": specs, "temperature": 1.0},
                            timeout=120)
        if resp.status_code in (400, 404):
            resp = SESSION.post(config.KIMI_BASE_URL + "/chat/completions",
                                headers={"Authorization": "Bearer " + config.require("KIMI_API_KEY")},
                                json={"model": config.KIMI_FALLBACK_MODEL,
                                      "messages": messages, "tools": specs,
                                      "temperature": 1.0}, timeout=120)
        resp.raise_for_status()
        msg = resp.json()["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return msg.get("content", "")
        for tc in calls:
            name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"] or "{}")
            print("  🔧 %s(%s)" % (name, json.dumps(args, ensure_ascii=False)[:100]))
            result = handlers[name](args) if name in handlers else {"error": "未知工具"}
            messages.append({"role": "tool", "tool_call_id": tc["id"],
                             "content": json.dumps(result, ensure_ascii=False)})
    return "（工具调用轮次耗尽）"


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "哪些SKU能报名大促？现有报名有没有违规？"
    print("问：%s\n" % q)
    print("答：%s" % chat(q))
