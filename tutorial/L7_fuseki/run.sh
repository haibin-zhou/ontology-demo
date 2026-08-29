#!/bin/bash
# L7：把图谱从"进程内对象"变成"HTTP 服务"。
export PATH="/opt/homebrew/opt/openjdk/bin:$PATH"
cd "$(dirname "$0")"

echo "== ① 启动 Fuseki（内存数据集，挂载点 /ecat，--update 允许写入）=="
fuseki-server --update --mem /ecat &
SERVER_PID=$!
trap "kill $SERVER_PID 2>/dev/null" EXIT
sleep 4

echo "== ② 通过 HTTP 写入数据（Graph Store Protocol，POST 文件内容）=="
curl -s -X POST "http://localhost:3030/ecat/data?default" \
  -H "Content-Type: text/turtle" \
  --data-binary @../../data/catalog.ttl && echo "数据已加载"

echo "== ③ 用 curl 远程查询（任何语言都能发这个 HTTP 请求）=="
curl -s -G http://localhost:3030/ecat/sparql \
  --data-urlencode "query=PREFIX : <https://demo.local/ecat#> SELECT ?s ?v WHERE { ?s :sales30d ?v } ORDER BY DESC(?v) LIMIT 3" \
  -H "Accept: text/csv"
echo

echo "== ④ 也可以先跑推理再导出、再加载——服务化的是物化后的图（见 run.py 注释）=="
kill $SERVER_PID 2>/dev/null
trap - EXIT
echo "服务已停止。"
