#!/bin/bash
# 环境基线：一键装齐本体工程工具栈（macOS / arm64）
# 国内网络：brew 走 USTC 镜像；GitHub 大文件断点续传
set -e
cd "$(dirname "$0")/.."

export HOMEBREW_BOTTLE_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles
export HOMEBREW_API_DOMAIN=https://mirrors.ustc.edu.cn/homebrew-bottles/api

echo "== 1/5 Java 运行时（ROBOT/Jena/Ontop/Protégé 共用）=="
/opt/homebrew/opt/openjdk/bin/java -version 2>/dev/null || brew install openjdk

echo "== 2/5 Jena（arq/riot）+ Fuseki（SPARQL 服务）=="
which arq >/dev/null 2>&1 || brew install jena
which fuseki-server >/dev/null 2>&1 || brew install fuseki

echo "== 3/5 Protégé（本体编辑器，GUI）=="
ls -d /Applications/Protégé.app >/dev/null 2>&1 || brew install --cask protege

echo "== 4/5 ROBOT（本体 CI）=="
if [ ! -f tools/robot.jar ]; then
  mkdir -p tools
  for i in 1 2 3 4 5; do
    curl -sL -C - -o tools/robot.jar --max-time 600 \
      https://github.com/ontodev/robot/releases/download/v1.9.10/robot.jar && break
    echo "retry $i"; sleep 2
  done
fi
[ -f tools/robot ] || printf '#!/bin/bash\nexec /opt/homebrew/opt/openjdk/bin/java -jar "$(dirname "$0")/robot.jar" "$@"\n' > tools/robot
chmod +x tools/robot

echo "== 5/5 Ontop（数据库虚拟化 OBDA）=="
if [ ! -d tools/ontop-cli ]; then
  mkdir -p tools
  for i in 1 2 3 4 5; do
    curl -sL -C - -o /tmp/ontop-cli.zip --max-time 600 \
      https://github.com/ontop/ontop/releases/download/ontop-5.5.0/ontop-cli-5.5.0.zip && break
    echo "retry $i"; sleep 2
  done
  mkdir -p tools/ontop-cli && unzip -q -o /tmp/ontop-cli.zip -d tools/ontop-cli
  # H2 JDBC 驱动（本地演示/测试用）
  curl -sL -o tools/ontop-cli/jdbc/h2.jar \
    https://repo1.maven.org/maven2/com/h2database/h2/2.3.232/h2-2.3.232.jar || true
fi

echo "== Python 虚拟环境（rdflib/owlrl/pyshacl/requests）=="
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install -q -r requirements.txt

echo ""
echo "✅ 环境基线就绪。验证："
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
java -version 2>&1 | head -1
arq --version 2>/dev/null | head -1
tools/robot --version 2>/dev/null | head -1 || echo "ROBOT ok"
tools/ontop-cli/ontop --version 2>/dev/null | grep -i version | head -1
.venv/bin/python -c "import rdflib, owlrl, pyshacl; print('python deps ok')"
