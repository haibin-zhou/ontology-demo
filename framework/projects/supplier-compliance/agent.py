"""本体驱动 Agent（通用版）：本体编译进提示词，CQ/SHACL/SPARQL 为工具面。

用法：python3 agent.py "你的业务问题"
凭证：复用 startup 主项目 .env 的 KIMI_API_KEY。
"""
import json
import re
import sys
import datetime as dt
from pathlib import Path
from string import Template

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

SESSION = requests.Session()
SESSION.trust_env = False
PROJ = {l.split(":", 1)[0].strip(): l.split(":", 1)[1].strip().strip('"').strip("'")
        for l in (BASE / "project.yml").read_text(encoding="utf-8").splitlines()
        if ":" in l and not l.startswith("#")}
BASE_IRI = PROJ["base_iri"]


def load_graph(with_reasoning=True):
    g = Graph()
    g.parse(str(BASE / "ontology" / "domain.ttl"), format="turtle")
    data_file = BASE / "data" / "catalog.ttl"
    if data_file.exists():
        g.parse(str(data_file), format="turtle")
    if with_reasoning:
        owlrl.DeductiveClosure(owlrl.OWLRL_Semantics, rdfs_closure=True,
                               axiomatic_triples=False).expand(g)
    return g


def compile_context():
    ont = Graph().parse(str(BASE / "ontology" / "domain.ttl"), format="turtle")
    lines = []
    q = """PREFIX owl: <http://www.w3.org/2002/07/owl#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?x ?label WHERE {
      { ?x a owl:Class } UNION { ?x a owl:ObjectProperty } UNION { ?x a owl:DatatypeProperty }
      OPTIONAL { ?x rdfs:label ?label } } ORDER BY ?x"""
    for x, label in ont.query(q):
        lines.append("- %s（%s）" % (str(x).split("#")[-1], label or ""))
    t = (BASE / "rules" / "thresholds.json").read_text(encoding="utf-8")
    lines.append("\n【业务阈值配置】\n" + t)
    cqs = sorted((BASE / "cq").glob("*.rq"))
    if cqs:
        lines.append("【可调用的标准业务问题（CQ）】")
        for rq in cqs:
            first = rq.read_text(encoding="utf-8").splitlines()[0].lstrip("# ")
            lines.append("- %s：%s" % (rq.name, first))
    return "\n".join(lines)


SYSTEM = """你是「%s」业务助手。你的业务认知完全来自下方本体，不允许凭常识编造定义。

【本体术语】
%s

【规则】
1. 业务问题优先调 run_cq；覆盖不了再用 sparql_select（只读）。
2. 涉及合规/违规判断必须先调 validate_data。
3. SPARQL 命名空间：PREFIX : <%s>。
4. 发现本体没有的概念，调 propose_ontology_change 写提案，不要自己编。
5. 中文回答，结论附依据。
"""


def make_tools(g):
    params = {}
    t = json.loads((BASE / "rules" / "thresholds.json").read_text(encoding="utf-8"))

    def flat(d, prefix=""):
        for k, v in d.items():
            key = (prefix + "_" + k if prefix else k).upper()
            flat(v, key) if isinstance(v, dict) else params.update({key: v})
    flat(t)

    def run_cq(name):
        path = BASE / "cq" / name
        if not path.exists():
            return {"error": "CQ 不存在，可选：%s" % [p.name for p in (BASE / "cq").glob("*.rq")]}
        q = Template(path.read_text(encoding="utf-8")).substitute(params)
        rows = sorted(set(" | ".join(str(v).split("#")[-1] for v in r) for r in g.query(q)))
        return {"cq": name, "rows": rows}

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
        data = load_graph(with_reasoning=False)
        shapes = Graph().parse(str(BASE / "ontology" / "shapes.ttl"), format="turtle")
        conforms, report, _ = validate(data, shacl_graph=shapes, advanced=True)
        SH = Namespace("http://www.w3.org/ns/shacl#")
        return {"conforms": conforms,
                "violations": [{"focus": str(report.value(r, SH.focusNode)).split("#")[-1],
                                "message": str(report.value(r, SH.resultMessage))}
                               for r in report.subjects(RDF.type, SH.ValidationResult)]}

    def propose_ontology_change(term, definition, reason):
        (BASE / "proposals").mkdir(exist_ok=True)
        pid = "P" + dt.datetime.now().strftime("%Y%m%d%H%M%S")
        (BASE / "proposals" / (pid + ".json")).write_text(json.dumps({
            "id": pid, "term": term, "definition": definition, "reason": reason,
            "status": "pending"}, ensure_ascii=False, indent=2), encoding="utf-8")
        return {"proposal_id": pid, "note": "提案已写入 proposals/，等人审"}

    handlers = {"run_cq": lambda a: run_cq(a["name"]),
                "sparql_select": lambda a: sparql_select(a["query"]),
                "validate_data": lambda a: validate_data(),
                "propose_ontology_change": lambda a: propose_ontology_change(
                    a["term"], a["definition"], a["reason"])}
    specs = [
        {"type": "function", "function": {
            "name": "run_cq", "description": "运行一个标准业务问题（CQ）",
            "parameters": {"type": "object",
                           "properties": {"name": {"type": "string", "description": "CQ 文件名"}},
                           "required": ["name"]}}},
        {"type": "function", "function": {
            "name": "sparql_select", "description": "只读 SPARQL 自由查询",
            "parameters": {"type": "object", "properties": {"query": {"type": "string"}},
                           "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "validate_data", "description": "SHACL 合规校验",
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
    messages = [{"role": "system",
                 "content": SYSTEM % (PROJ.get("title", ""), compile_context(), BASE_IRI)},
                {"role": "user", "content": question}]
    for _ in range(8):
        resp = SESSION.post(config.KIMI_BASE_URL + "/chat/completions",
                            headers={"Authorization": "Bearer " + config.require("KIMI_API_KEY")},
                            json={"model": config.KIMI_MODEL, "messages": messages,
                                  "tools": specs, "temperature": 1.0}, timeout=120)
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
    q = " ".join(sys.argv[1:]) or "你好，介绍一下你能做什么"
    print("问：%s\n" % q)
    print("答：%s" % chat(q))
