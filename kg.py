"""知识管理层：装载本体 + 实例数据，OWL-RL 推理物化，SHACL 校验，SPARQL 查询。

分工原则：
  - OWL（category.ttl）：开放世界，管"推理"——类层级、传递、属性链、互斥；
  - SHACL（shapes.ttl）：封闭世界，管"校验"——必填、格式、价保等业务规则。
"""
import json
import warnings
from pathlib import Path

from rdflib import Graph, Namespace, RDF, OWL
import owlrl
from pyshacl import validate

warnings.filterwarnings("ignore")

BASE = Path(__file__).parent
ECAT = Namespace("https://demo.local/ecat#")
STD_NAMESPACES = ("w3.org", "w3id.org")   # rdf/rdfs/owl/xsd/sh 等标准命名空间不算"缺口"


def load_graph(*files):
    g = Graph()
    for f in files:
        g.parse(str(Path(f)), format="turtle")
    return g


class KnowledgeGraph:
    """本体 + 数据 + 推理结果 + 校验结果的统一入口。"""

    def __init__(self, base=BASE):
        self.base = Path(base)
        self.ontology_file = self.base / "ontology" / "category.ttl"
        self.shapes_file = self.base / "ontology" / "shapes.ttl"
        self.data_file = self.base / "data" / "catalog.ttl"
        self.reload()

    def reload(self):
        self.ont = load_graph(self.ontology_file)
        self.shapes = load_graph(self.shapes_file)
        self.data = load_graph(self.data_file)
        self.enriched = None  # reason() 之后 = 本体 + 数据 + 推理物化

    # ---- 本体元信息 ---------------------------------------------------------
    def version(self):
        for o in self.ont.objects(None, OWL.versionInfo):
            return str(o)
        return None

    def declared_terms(self):
        """本体中显式声明的类与属性（本命名空间内），用于自迭代的缺口检测。"""
        terms = set()
        decl_types = [OWL.Class, OWL.ObjectProperty, OWL.DatatypeProperty]
        for t in decl_types:
            for s in self.ont.subjects(RDF.type, t):
                if str(s).startswith(str(ECAT)):
                    terms.add(str(s))
        # 在 domain/range/链公理中出现过的属性也算"已知"
        for p in (OWL.propertyChainAxiom,):
            for s in self.ont.subjects(p, None):
                if str(s).startswith(str(ECAT)):
                    terms.add(str(s))
        return terms

    # ---- 推理 ---------------------------------------------------------------
    def reason(self):
        """OWL-RL 前向链推理，把可推导的三元组物化进 enriched 图。"""
        g = Graph()
        g += self.ont
        g += self.data
        before = len(g)
        owlrl.DeductiveClosure(
            owlrl.OWLRL_Semantics, rdfs_closure=True, axiomatic_triples=False
        ).expand(g)
        self.enriched = g
        return len(g) - before

    # ---- SHACL 校验 -----------------------------------------------------------
    def validate(self):
        """对原始实例数据跑 SHACL（不把推理结果当借口放过脏数据）。"""
        conforms, results_graph, results_text = validate(
            self.data,
            shacl_graph=self.shapes,
            ont_graph=self.ont,
            inference="rdfs",
            abort_on_first=False,
            advanced=True,
        )
        violations = []
        SH = Namespace("http://www.w3.org/ns/shacl#")
        for r in results_graph.subjects(RDF.type, SH.ValidationResult):
            msg = results_graph.value(r, SH.resultMessage)
            focus = results_graph.value(r, SH.focusNode)
            violations.append({
                "focus": str(focus).split("#")[-1] if focus else "?",
                "message": str(msg),
            })
        return conforms, violations, results_text

    # ---- 查询 -----------------------------------------------------------------
    def query(self, sparql):
        assert self.enriched is not None, "先调用 reason()"
        return self.enriched.query(sparql)
