# Demo walkthrough

本演示围绕一个具体决策：现有 ESG 新授信筛查控制，能否支持 SME 存量贷款的持续监测？

## 运行

```bash
python3 scripts/demo.py
# 可使用独立输出目录保存另一轮演示
python3 scripts/demo.py --output runs/review-session
```

演示以 `scripted_replay` 模式调用真实工具与案件服务，模拟事实答复、责任接受及证据审核，不需要模型密钥。每次运行创建新案件，数据库保留历史，报告文件指向最新一次运行。

## 建议讲解顺序

| 环节 | 展示重点 | 可以打开的结果 |
|---|---|---|
| 监管与业务上下文 | 来源定位、适用日期、案件数据快照 | `summary.json` 的 investigation |
| 控制范围差异 | 新申请筛查不能直接证明存量持续监测 | gap_assessments |
| 缺失事实与更新 | 10000 个客户，模拟答复 65% 有能源数据，3500 个待补 | energy_coverage |
| 方案与责任 | 三种方案模板的条件性成本；行动范围、责任候选和目标日期 | plans / actions |
| 证据退回 | 不相关政策被拒绝，保留旧版本与理由 | evidence.history |
| 补交与结案 | 设计、测试材料分别审核后关闭窄任务 | evidence.current / actions |
| 可追溯执行 | 事实答复、对象版本和人工决定均有审计事件 | `audit.json` |

`report.md` 汇总检查结果、发现和行动，适合直接演示；`workflow.json` 保留阶段性运行结果，便于回答追问。65% 描述数据覆盖程度，不被换算成风险概率或自动节省的成本。

## 从 API 查看同一案件

```bash
python3 agent/api_server.py --db runs/demo/cases.sqlite3
```

复制演示输出的 `CASE_ID`，在浏览器或终端读取：

```bash
curl http://127.0.0.1:8765/api/cases/CASE_ID
curl http://127.0.0.1:8765/api/cases/CASE_ID/investigation
curl http://127.0.0.1:8765/api/cases/CASE_ID/plans
curl http://127.0.0.1:8765/api/cases/CASE_ID/evidence
curl http://127.0.0.1:8765/api/cases/CASE_ID/audit
```

API 提供 JSON 数据视图。模式标签、证据版本和审核状态随结果展示。Live 调查与场景回放使用相同业务工具，运行方式见 [开发说明](development.md)。
