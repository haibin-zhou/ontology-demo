"""一键演示：本体设计 → 知识管理 → 治理 → 自迭代 全闭环。

用法：
  .venv/bin/python demo.py              # 全流程（含自迭代提案 + 模拟审批应用）
  .venv/bin/python demo.py --no-evolve  # 只跑知识管理 + 治理，不动本体
"""
import sys

from kg import KnowledgeGraph, BASE
import governance
import evolve


def section(title):
    print("\n" + "=" * 64)
    print("  %s" % title)
    print("=" * 64)


def main():
    evolve_enabled = "--no-evolve" not in sys.argv

    kg = KnowledgeGraph()

    # ---- 1. 装载与推理（知识管理）-------------------------------------------
    section("1/6 知识管理：装载本体 + 数据，OWL-RL 推理物化")
    inferred = kg.reason()
    print("本体版本：%s" % kg.version())
    print("原始三元组：%d 条（本体 %d + 数据 %d）" % (
        len(kg.ont) + len(kg.data), len(kg.ont), len(kg.data)))
    print("推理后物化新增：%d 条" % inferred)

    print("\n推理能力抽查：")
    q = """PREFIX : <https://demo.local/ecat#>
SELECT ?sku ?cat WHERE { ?sku :belongsToCategory ?cat . ?cat :subCategoryOf* :cat_sports_outdoor . }
"""
    print("  · 传递闭包：'运动户外'大类下共有 %d 个 SKU（含子类目自动继承）"
          % len(list(kg.query(q))))
    q_chain = """PREFIX : <https://demo.local/ecat#>
SELECT DISTINCT ?sku ?brand WHERE { ?sku :skuBrand ?brand . }
"""
    print("  · 属性链推导 skuBrand（SKU→SPU→品牌）：")
    for r in kg.query(q_chain):
        print("      %s → %s" % tuple(str(v).split("#")[-1] for v in r))
    q_auth = """PREFIX : <https://demo.local/ecat#>
SELECT DISTINCT ?m ?b WHERE { ?m :authorizedBrand ?b . }
"""
    print("  · 属性链推导 authorizedBrand（商家→授权书→品牌）：")
    for r in kg.query(q_auth):
        print("      %s → %s" % tuple(str(v).split("#")[-1] for v in r))

    # ---- 2. 一致性检查（治理）------------------------------------------------
    section("2/6 治理：逻辑一致性检查（disjoint 矛盾检测）")
    conflicts = governance.check_consistency(kg)
    if conflicts:
        print("❌ 发现状态矛盾实例：%s（同时是'在售'和'已下架'）" % ", ".join(conflicts))
    else:
        print("✅ 无逻辑矛盾")

    # ---- 3. SHACL 校验（治理）------------------------------------------------
    section("3/6 治理：SHACL 数据校验（封闭世界合规检查）")
    conforms, violations, _ = kg.validate()
    print("整体合规：%s" % ("✅ 通过" if conforms else "❌ 发现 %d 条违规" % len(violations)))
    for v in violations:
        print("  ❌ %s —— %s" % (v["focus"], v["message"]))

    # ---- 4. CQ 回归（治理：本体的单元测试）------------------------------------
    section("4/6 治理：胜任力问题（CQ）回归测试")
    thresholds = governance.load_thresholds()
    print("当前阈值：动销≥%d件 / 毛利≥%s / 滞销线：周转>%d天且月销<%d件" % (
        thresholds["promo"]["minSales30d"], thresholds["promo"]["minGrossMargin"],
        thresholds["slowMoving"]["inventoryDaysGt"], thresholds["slowMoving"]["sales30dLt"]))
    all_ok, details = governance.cq_regression(kg, thresholds)
    for d in details:
        flag = "✅" if d["ok"] else "❌"
        print("  %s %s → %s（期望 %s）" % (flag, d["cq"], d["actual"], d["expected"]))
    print("CQ 回归：%s" % ("全部通过" if all_ok else "存在失败项"))

    # ---- 5. 漂移指标（治理看板）------------------------------------------------
    section("5/6 治理：漂移监控指标（月度评审看板）")
    for k, v in governance.drift_report(kg, thresholds).items():
        print("  %-18s %s" % (k, v))

    # ---- 6. 自迭代 -------------------------------------------------------------
    if evolve_enabled:
        section("6/6 自迭代：新数据信号 → 提案 → 审批 → 应用 → 回归")
        incoming = BASE / "data" / "incoming_batch.ttl"
        gaps = evolve.detect_gaps(kg, incoming)
        if not gaps:
            print("新批次数据未发现本体缺口。")
            return
        print("检测到本体缺口：")
        for g in gaps:
            print("  ⚠️  未声明术语 :%s（样本：%s → %s）" % (
                g["term"], g["sample_subject"], g["sample_object"]))
        proposal = evolve.write_proposal(kg, gaps)
        print("\n已生成提案 %s（基于版本 %s）：" % (proposal["id"], proposal["based_on_version"]))
        print("  " + proposal["suggested_ttl"].replace("\n", "\n  "))

        # 模拟人工审批（生产中这一步是人审，或 LLM 补语义后人审）
        print("\n模拟人工审批通过，应用提案……")
        result = evolve.approve(proposal["id"], kg, approver="category-owner@demo")
        if result["applied"]:
            print("✅ 提案已应用，本体升级：%s → %s" % (
                proposal["based_on_version"], result["version"]))
            print("   治理回归：无 CQ 退化、无新增 SHACL 违规（变更安全）")
            # 验证新属性可查询
            rows = list(kg.query("""PREFIX : <https://demo.local/ecat#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
SELECT ?t WHERE { :energyReturnRating a ?t }"""))
            print("   新属性 :energyReturnRating 已可被本体查询：类型=%s"
                  % str(rows[0][0]).split("#")[-1])
        else:
            print("❌ 提案被治理回归拦截并自动回滚：")
            print("   CQ 退化：%s" % result["cq_regressed"])
            print("   新增违规：%s" % result["shacl_regressed"])

        print("\n变更审计（governance/changelog.jsonl）：")
        log = governance.CHANGELOG
        if log.exists():
            for line in log.read_text(encoding="utf-8").strip().splitlines():
                print("  " + line)

    section("完成")
    print("本体 %s · 黑板式文件全在 ontology-demo/ 下，可用 Protégé 打开 ontology/category.ttl"
          % kg.version())


if __name__ == "__main__":
    main()
