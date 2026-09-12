# Regulatory Change-to-Action：当前任务交接

更新：2026-09-12。工作区：`/Users/yishanma/Desktop/reguagent`。本文件描述当前状态；旧交接记录保存在 `backups/2026-09-12-before-task-checkpoints/CODEX_CONTEXT.before.md`。

最高依据是 `require.md`。目标是虚构 Northstar 银行 SME ESG 案件的来源变化 → 调查/访谈 → 控制缺口 → 约束下计划 → 责任/期限 → 证据审核。bunq 仅作真实同业参考；A/B/C 与 Integration Guide 是设计参考。四角色共享模型和单进程，LLM 负责调查路径与候选解释，代码负责计算/校验/状态，人负责关键解释审核、责任接受和证据批准。

## 1. 已完成修改

- M1：唯一 baseline、重建保护、范围/日期分离、可选 AHP、控制设计与操作证据分离、治理文本盲映射、事实优先的组合表达。
- M2：SQLite 案件/版本对象/审计链，四角色工具循环，查询/引用/关系遍历，事实问题、答复补丁、依赖失效和恢复。
- M3/M4 已有：条件性成本、计划/行动草案、RACI 候选、法规日期与内部日期分开、人工接受、文件/hash 入库、证据内容判断、人工拒绝/确认和窄任务闭案。完整预算重规划仍未完成。
- 接口：JSON HTTP API、视图投影和待办处理；没有实际前端。
- Provider：Anthropic 兼容与 OpenAI adapter。用户已配置 OpenAI `gpt-5`，文本 smoke test 成功；此前真实工具调用也已成功。默认 provider 测试误读用户配置的问题已修复。
- 请求控制：安全错误分类/限流头、有限重试、单请求预算、旧工具观察压缩、默认摘要搜索后读取全文、OpenAI 单轮工具约束、60 秒 TPM 保守预留及同案件近期预留恢复。
- **本轮新增：** 协调角色只开放 `case_context/delegate/check_closure/finish`；专家自行查询、判断并保存结果。提示要求窄任务和尽早保存有依据的发现，专家没有交付物不能声明 completed，协调不能仅凭来源入库声明调查完成。
- **本轮新增：** `task_execution.py` 与 `task_checkpoint.py` 保存工具历史、已观察引用、待执行工具游标、未完成委派和循环计数。检查点绑定案件 revision、冻结输入 hash、提示/工具合同和协议版本，并与审计 hash 绑定。
- **本轮新增：** 嵌套 SQLite savepoint 让业务写入、工具审计和游标推进原子提交；专家子任务独立提交，父任务恢复可复用。模型请求/等待不持有写事务。
- **真实验证后补充：** 模型请求包含准备时剩余调用/时间、单任务剩余轮数和已保存交付物数量，要求优先保存有依据的部分结果。信息计入请求预算并写入审计；不改原任务检查点。本轮追加的一次真实请求仍未产出 Finding，因此提示不能视为已解决调查产出问题。

### 当前测试证据

| 检查 | 结果 |
|---|---|
| 本轮新增权限/检查点测试 | 12/12 通过 |
| 预算提示补充测试 | 2/2 通过；受影响组合 62/62 通过 |
| 最新 agent 全量 | **226/226 通过**，15.048 秒 |
| scripts | 最近一次 24/24 通过，本轮未重跑且代码未改 |
| 本轮真实 API | **10 次/10 次成功**，33746 个报告 tokens，428.588 秒；无 provider/工具错误 |
| 实际角色/恢复 | 一个法规专家委派、两次续跑；审计链/检查点有效 |
| 调查产出 | **Finding/Question/计划/行动均为 0**，专家任务范围过大 |
| 完整真实模型 demo | 未通过验收，T24 保持未完成 |

12 项新测试覆盖冷启动续跑、同轮多工具中断、业务写入与检查点共同回滚、子任务成功但父任务失败、输入版本变化、篡改拒绝、结果复用与数据库事务边界。它们使用测试客户端/显式 replay，不是 LLM 调查质量评测。日志有一个 HTTPError 临时资源清理 ResourceWarning，无失败。

日志：`research/task_checkpoint_validation/agent_tests.log`（224 项历史）、`agent_tests_after_budget_feedback.log`（最新 226 项）。完整说明与真实结果：`research/task_checkpoints_2026-09-12.md`。

## 2. 未完成事项

1. **T12/T24 调查产出。** 职责限制、检查点和 TPM 已组合真实运行。协调实际要求专家逐条调查八条要求、保存九项 Finding，与单任务 12 轮预算不匹配。专家持续读取，尚无正式发现。优先增加可校验的窄委派合同：一个决策问题、明确目标范围、一个预期交付物、调查预算及未完成工作返回；随后再验收问题、更新、计划与证据审查。
2. **T17 约束重规划。** 底层 `evaluate_option(..., budget=...)` 已有；`compare_costs()`、`propose_plan()`、案件约束版本和 API 尚未贯通。
3. **T21/T22 界面与完整接口。** 实际前端、创建/启动/恢复案件、约束更新等主线操作尚缺；人工接口还需客户端 expected version 验证，上传 filename 需严格路径边界。
4. **T07/T08 来源和材料。** 已有登记事件回放、本地候选快照导入、hash/文本比较；官方双版本快照和单一来源更新检测未补齐。synthetic 答复、无关政策及设计/pilot 测试样本已存在，仍需对齐行动 scope，pilot 不能证明全量运行有效。
5. **T23/T25 评测和复演。** 本地回归持续完善，尚缺真实行为场景集和约七分钟完整交互演示。

TODO 已纠正 T17/T21/T22 的提前勾选，真实验证后 T12 也恢复为部分完成；T07/T08/T23/T24/T25 也未完成。其余勾选代表已有实现，不能代替 T24 的真实端到端验收。

还应审查：计划引用已观察不等于支持充分；登记 RACI 不代表产能；当前 source intake 的 `registered_source_replay` 不可包装成现场实时监测。全部法规解释仍 provisional，不能由模型自动批准法律结论或关闭行动。

检查点限制：旧版无检查点任务首次新建；revision/角色合同变化会新建任务上下文，非逐依赖迁移；单任务 12 轮上限跨重启保留；预算耗尽目前仍显示 failed，但进度可恢复；仅支持同一案件串行运行，完整历史版本会增加 SQLite 体积。

## 3. 当前代码结构

```text
agent/
  run_case.py             当前 live/replay 案件 CLI、答复/接受/证据等入口
  tool_runtime.py         全局预算、请求压缩、TPM/重试、任务入口
  task_execution.py       逐工具执行、委派、完成门槛、恢复
  task_checkpoint.py      版本绑定、完整性校验、持久化检查点
  investigation_tools.py  查询/访谈/计划/证据工具、权限和 schema
  roles.py                四角色提示；顺序由模型选择
  case_store.py           SQLite 对象、嵌套事务、版本、审计、人工操作
  request_controls.py    请求估算、观察压缩、安全诊断、TPM 窗口
  llm.py                  Anthropic/OpenAI adapter
  llm_config.py           本地配置；不要打印配置或密钥
  source_intake.py        登记来源回放、候选快照与版本比较
  evidence_intake.py      证据文件/hash、确定性闭案检查
  replay_client.py        显式脚本回放，不证明模型能力
  view_adapter.py         展示视图与待办
  api_server.py           本地 JSON API，尚无实际前端
  run_demo.py             旧确定性基线入口，AHP 可选
  test_task_checkpoints.py 新增故障恢复和角色门槛测试
scripts/                  数据加载/成本计算、校准、校验、开发评测
calibrated_v0_2/           唯一 baseline v0.2.1
materials/esg_demo/        明确 synthetic 的答复与证据
runs/                     运行数据库与文件
research/                 调研、review、实施/验收证据
```

## 4. 下一步建议操作

下一步先修复结构化的窄任务/交付合同，再完成“委派 → Finding → 中断恢复”验收。已有委派和恢复证据，缺的是正式产出；不要重新 `start --new` 或继续只加提示词。之后再接通预算重规划和完整 demo。

### 当前真实案件及历史结果

数据库：`runs/esg_live.sqlite3`。案件：`CASE-cb4fa9d654e14a34b4df0a8ea7109e56`，目前 failed（预算停止），revision 1；本轮保存了任务检查点/观察，未改 baseline 或业务事实。

- 原始用户运行：6 次请求尝试、3 次成功响应、11275 个报告 tokens，只有协调查询，随后连接/限流失败。
- 上轮经用户明确确认的恢复：合计 12 次请求、9 次成功响应、37855 个报告 tokens、178.322 秒。一次本地 RequestTooLarge；后续三个明确的 `429/rate_limit_exceeded`，服务端 tokens=10000、requests=50，前两次等待后重试成功。
- 上轮无专家委派、Finding、Question、PlanVersion 或 Action；不能宣称四角色成功。
- 尚无 `context_length_exceeded` 证据，不能把 429 归因于模型上下文窗口较短。

### 新增预算授权已落实，实验已结束

用户明确回复“授权 新增预算”，同意新增最多 12 次请求/480 秒；此前自动审批阻塞已解除，三个阶段均获准执行。不要再把同一授权说成缺失。

实际第一段 3 次/75.831 秒，第二段 6 次/340.699 秒；补充预算提示并通过 226 项本地测试后，第三段使用余额，1 次/12.058 秒。合计 **10 次/428.588 秒、33746 tokens**，全部模型响应成功，provider/工具错误为 0。等待记录合计 383.888 秒，约占 90%；当前节流明显拖慢演示。

所有阶段使用 `--max-request-tokens 10000 --tokens-per-minute 10000 --min-request-interval 12`。第三段上限 3 次/60 秒，总上限保持在授权范围内。实验主动结束，**尚余 2 次请求/51.412 秒未用**；后续如用余额必须严格按剩余额度，不能重新视为整轮 12 次/480 秒。运行耗时包括请求和等待，本地开发/测试另计。

最新审计 seq=225，hash 链及两个当前协议检查点均有效。法规专家已完成 8 轮、保留 10 项观察；协调完成 2 轮，仍等待同一委派返回。完成工具：case_context×1、source_versions×1、search_records×2、get_record×5。没有完全相同的重复请求，但搜索有重叠。没有正式 Finding、Question、GapAssessment、PlanVersion、Action 或 Evidence；不计为四角色闭环成功。预算提示后的单次模型响应仍读取 DATA-SELECTION，不能宣称提示有效解决了产出问题。

结果文件：`research/task_checkpoint_validation/live_checkpoint_pause.json`、`live_checkpoint_resume.json`、`live_budget_feedback.json`、`live_summary.json`、`live_tool_results.json`。`summarize_live.py` 可只读重新导出核查。完整分析和下一步合同建议见 `research/task_checkpoints_2026-09-12.md`。生产角色/工具合同此次未改；下一次收窄合同需要明确处理旧的大任务，不假称它已完成。

之后先查看真实 Question/schema，再由人提供范围/日期/分母明确的答复。虚构银行的演示答复仍标记 synthetic；不要代替人签字或批准法律结论。

## 5. 关键文件路径和稳定约束

- 项目要求：`require.md`；架构：`docs/architecture.md`；计划：`TODO.md`；运行说明：`README.md`。
- 最新实现报告：`research/task_checkpoints_2026-09-12.md`。
- 旧请求控制记录：`research/request_controls_2026-09-12.md` 与 `research/request_controls_validation/`。
- 当前测试与审批边界：`research/task_checkpoint_validation/`。
- 本轮代码/案件备份：`backups/2026-09-12-before-task-checkpoints/`；案件备份前最后审计 seq=80。
- 预算提示修改前备份：`backups/2026-09-12-before-budget-feedback/`，含第二段结束后的案件检查点。
- 原资料：`data/person1` 至 `person4`、`data/bunq_reference bank`；数据 skill：`data/regulatory-governance-dataset/SKILL.md`。
- baseline：`calibrated_v0_2/` v0.2.1；场景/法律研究截止 2026-09-08，组合快照 2026-06-30；实际系统日期不覆盖场景日期。
- SME 分母 10000 客户、2300m EUR；能源答复样本 65% = 6500 有数据、3500 待补，不推导风险、自动化率或 TCO 变化。
- 本轮无 baseline/事实修改。绝不把整个工作区递归发送模型；不要读取或输出 `.env.local` 中的密钥。
