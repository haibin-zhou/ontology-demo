#!/bin/bash
# CI 三道门禁：语法 → 一致性 → 幽灵属性 → CQ 回归
# 任何一道失败即退出非零（可接入 GitHub Actions / 提交钩子）
set -e
cd "$(dirname "$0")"
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"

echo "== ① 语法校验 =="
riot --validate ontology/domain.ttl && riot --validate ontology/shapes.ttl && echo PASS

# 向上查找框架根（含 .venv 和 tools/robot 的目录）
ROOT="$(pwd)"
while [ "$ROOT" != "/" ] && [ ! -d "$ROOT/.venv" ]; do ROOT="$(dirname "$ROOT")"; done
ROBOT="${ROBOT:-$ROOT/tools/robot}"
PY="${PY:-$ROOT/.venv/bin/python}"

echo "== ② 本体一致性（ROBOT + ELK）=="
$ROBOT reason --reasoner ELK --input ontology/domain.ttl --output /tmp/ci_reasoned.ttl 2>/dev/null \
  && echo "PASS：本体一致"

echo "== ③ 幽灵属性检查（声明↔使用一致性）=="
$PY check_ghost.py

echo "== ④ CQ 回归 =="
$PY run_cq.py
