#!/bin/bash
# L6：一条最小"本体 CI 流水线"。每步失败即退出（set -e），和 CI 里一样。
set -e
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
cd "$(dirname "$0")"
ROBOT=../../tools/robot
ONTO=../../ontology/category.ttl   # 复用主 DEMO 的真实本体
DATA=../../data/catalog.ttl        # 复用主 DEMO 的真实数据（含故意埋的脏数据）

echo "== 步骤1：语法校验（riot）=="
riot --validate "$ONTO" && echo "PASS"

echo "== 步骤2：本体自身一致性（robot reason / ELK）=="
$ROBOT reason --reasoner ELK --input "$ONTO" --output /tmp/l6_reasoned.ttl 2>/dev/null \
  && echo "PASS：本体（T-Box）一致"

echo "== 步骤3：实例级矛盾检查（robot reason 本体+数据合并）=="
cat "$ONTO" "$DATA" > /tmp/l6_merged.ttl
if $ROBOT reason --reasoner ELK --input /tmp/l6_merged.ttl --output /tmp/l6_out.ttl 2>&1 \
     | grep -v WARNING | grep -q "inconsistent"; then
  echo "FAIL：合并实例后逻辑不一致（sku7 既在售又已下架）——CI 在此拦截"
else
  echo "PASS"
fi

echo "== 步骤4：自定义违规门禁（robot verify + 自带 SPARQL）=="
mkdir -p /tmp/l6_vr
if $ROBOT verify --input /tmp/l6_merged.ttl --queries violation.rq \
     --output-dir /tmp/l6_vr 2>/dev/null; then
  echo "PASS：无违规"
else
  echo "FAIL：发现违规实例 →"
  cat /tmp/l6_vr/*.csv
fi

echo "== 步骤5：质量报告（robot report）=="
$ROBOT report --input "$ONTO" --output /tmp/l6_report.tsv --fail-on none 2>/dev/null
echo "报告行数：$(wc -l < /tmp/l6_report.tsv)（节选前 5 行）"
head -5 /tmp/l6_report.tsv

echo "== 步骤6：格式转换（robot convert → RDF/XML）=="
$ROBOT convert --input "$ONTO" --format owx --output /tmp/l6_category.owl 2>/dev/null \
  && echo "PASS：已生成 /tmp/l6_category.owl"

echo "== 流水线结束（步骤 3/4 的 FAIL 是预期——演示数据故意埋了矛盾）=="
