"""自迭代机制：数据信号 → 本体缺口 → 提案 → 人工审批 → 应用 → 回归验证 → 版本化。

真实企业里"信号检测 + 提案草拟"通常由 LLM 完成（ontology oracle），
本 DEMO 用确定性逻辑替代以便离线跑通，LLM 的接入点在 detect_gaps() 注释中标注。

铁律：任何变更必须先过治理回归（一致性 + CQ + SHACL），失败自动回滚。
"""
import json
import re
import shutil
import datetime as dt
from pathlib import Path

from rdflib import Graph

from kg import KnowledgeGraph, BASE, ECAT, STD_NAMESPACES
import governance

PROPOSALS = BASE / "proposals"


# ---- 信号检测 ------------------------------------------------------------------
def detect_gaps(kg: KnowledgeGraph, incoming_file):
    """扫描新批次数据，找出使用了、但本体未声明的本命名空间术语。

    生产环境中这里可以换成：把未识别谓词 + 上下文样本喂给 LLM，
    让它判断"这是新属性/新类/还是脏数据拼写错误"，并草拟提案。
    """
    incoming = Graph().parse(str(incoming_file), format="turtle")
    known = kg.declared_terms()
    gaps = []
    seen = set()
    for s, p, o in incoming:
        for term, role in ((p, "predicate"),):
            t = str(term)
            if t in seen or not t.startswith(str(ECAT)):
                continue
            seen.add(t)
            if t not in known:
                gaps.append({
                    "term": t.split("#")[-1],
                    "role": role,
                    "sample_subject": str(s).split("#")[-1],
                    "sample_object": str(o),
                })
    return gaps


# ---- 提案生成 --------------------------------------------------------------------
def write_proposal(kg: KnowledgeGraph, gaps):
    ts = dt.datetime.now().strftime("%Y%m%d%H%M%S")
    pid = "P%s" % ts
    snippets = []
    for g in gaps:
        snippets.append(
            ':{term} a owl:DatatypeProperty ; rdfs:domain :SKU ;\n'
            '    rdfs:range xsd:decimal ;\n'
            '    rdfs:label "{term}（自迭代提案 {pid}）" .'.format(term=g["term"], pid=pid)
        )
    proposal = {
        "id": pid,
        "status": "pending",
        "created_by": "evolve-agent",
        "based_on_version": kg.version(),
        "gaps": gaps,
        "suggested_ttl": "\n\n".join(snippets),
        "reason": "新批次数据出现本体未声明术语；LLM 接入点：由模型判定语义并补 label/comment。",
    }
    path = PROPOSALS / ("%s.json" % pid)
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    return proposal


# ---- 审批与应用 ------------------------------------------------------------------
def _bump_version(v):
    parts = [int(x) for x in v.split(".")]
    parts[1] += 1
    return ".".join(str(x) for x in parts)


def approve(proposal_id, kg: KnowledgeGraph, approver):
    """应用提案：改本体文件 → 升版本 → 治理回归 → 退化则回滚。

    回归口径：只拦截"本次变更引入的"退化——SHACL 违规变多、CQ 由绿变红；
    存量脏数据（变更前就存在的违规/矛盾）只上报、不阻断演进。
    """
    path = PROPOSALS / ("%s.json" % proposal_id)
    proposal = json.loads(path.read_text(encoding="utf-8"))
    assert proposal["status"] == "pending", "提案状态不是 pending"

    # 变更前基线
    _, base_cq_details = governance.cq_regression(kg)
    base_cq_pass = {d["cq"] for d in base_cq_details if d["ok"]}
    _, base_violations, _ = kg.validate()
    base_violation_sigs = {(v["focus"], v["message"]) for v in base_violations}

    ont_file = kg.ontology_file
    backup = ont_file.with_suffix(".ttl.bak")
    shutil.copy(ont_file, backup)

    old_v = kg.version()
    new_v = _bump_version(old_v)
    text = ont_file.read_text(encoding="utf-8")
    text = re.sub(r'owl:versionInfo "%s"' % re.escape(old_v),
                  'owl:versionInfo "%s"' % new_v, text)
    text += ("\n\n# ---- 自迭代提案 %s（审批人：%s，%s）----\n%s\n"
             % (proposal_id, approver, dt.date.today(), proposal["suggested_ttl"]))
    ont_file.write_text(text, encoding="utf-8")

    # 变更后回归
    kg.reload()
    kg.reason()
    _, new_cq_details = governance.cq_regression(kg)
    new_cq_pass = {d["cq"] for d in new_cq_details if d["ok"]}
    _, new_violations, _ = kg.validate()
    new_violation_sigs = {(v["focus"], v["message"]) for v in new_violations}

    cq_regressed = base_cq_pass - new_cq_pass
    shacl_regressed = new_violation_sigs - base_violation_sigs
    regression_ok = not cq_regressed and not shacl_regressed

    if regression_ok:
        backup.unlink()
        proposal["status"] = "applied"
        proposal["applied_version"] = new_v
        governance.log_change({
            "type": "ontology_evolution", "proposal": proposal_id,
            "approver": approver, "from": old_v, "to": new_v,
            "terms_added": [g["term"] for g in proposal["gaps"]],
        })
    else:
        shutil.copy(backup, ont_file)   # 回滚
        backup.unlink()
        kg.reload()
        kg.reason()
        proposal["status"] = "rejected_by_regression"

    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "applied": regression_ok,
        "version": kg.version(),
        "cq_regressed": sorted(cq_regressed),
        "shacl_regressed": ["%s: %s" % (f, m) for f, m in sorted(shacl_regressed)],
    }
