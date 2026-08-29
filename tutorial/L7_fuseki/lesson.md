# L7 Fuseki：图谱服务化——本体成为"平台层"的第一步

## 概念

L1–L6 全在单机进程内：rdflib 要 import、arq 要装 Jena。**只要消费方不止一个
（Agent、前端、BI、其他后端），图谱就必须变成服务。**

Fuseki 是 Jena 的 SPARQL HTTP 服务器：

```
任何语言/系统 ──HTTP──► Fuseki ──► 数据集（内存 / TDB2 持久化）
   POST /ecat/update        ↑ SPARQL Update（写）
   GET  /ecat/sparql        ↑ SPARQL Protocol（查）
```

两个端点对应两个 W3C 标准：**SPARQL Protocol**（查询）和 **SPARQL Update**（写入）。
Agent 查本体、Web 应用取数据、ETL 回写，全部走同一个 HTTP 协议——这就是
"本体即平台"的最小实现。

## 运行

```bash
cd ontology-demo/tutorial/L7_fuseki
bash run.sh
```

脚本做的事：起服务（内存模式）→ curl 写入 catalog.ttl → curl 查询销量前三 → 关服务。
预期输出：

```
== ① 启动 Fuseki ==
== ② 通过 HTTP 写入数据 ==
数据已加载
== ③ 用 curl 远程查询 ==
s,v
https://demo.local/ecat#sku4,260
https://demo.local/ecat#sku1,120
https://demo.local/ecat#sku3,80
== ④ ...
服务已停止。
```

服务运行时也可以开浏览器访问 http://localhost:3030 —— 自带管理界面，
可以交互式跑查询、看数据集状态。

## 观察点

1. **DEMO 的 kg.py 和 Fuseki 是可以互换的**：`kg.query(sparql)` 换成
   `requests.get("http://.../sparql", params={"query": sparql})`，CQ 回归、
   Agent 工具全部照常工作——因为 SPARQL 是标准协议，这就是标准化的红利。
2. **推理在服务化时的位置**：Fuseki 内存模式不做 OWL 推理。两种生产做法：
   先用 owlrl/ROBOT 物化再导出加载（简单），或用带推理的存储（TDB2+规则、
   GraphDB/Stardog）。L3 学到的"物化"概念在这里变成架构决策。
3. 本课用 `--mem`（重启即丢）；持久化用 TDB2：`tdb2.tdbloader --loc /data/db file.ttl`
   然后 `fuseki-server --loc /data/db /ecat`。

## 练习

1. 服务启动后，用浏览器 http://localhost:3030 跑一次 L5 的 Q4（属性路径查询）。
2. 用 SPARQL Update 写一条新三元组：
   ```bash
   curl -X POST http://localhost:3030/ecat/update \
     --data "PREFIX : <https://demo.local/ecat#> INSERT DATA { :sku9 a :SKU ; :sales30d 999 }"
   ```
   再查询验证。
3. 进阶：把 DEMO 的 `agent.py` 里 `kg.query` 换成对 Fuseki 的 HTTP 调用，
   Agent 就从"单机玩具"变成"客户端-服务端"架构了。
