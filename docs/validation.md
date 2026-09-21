# Submission validation

验证日期：2026-09-21。环境：macOS、Python 3.14.6，依赖版本固定于 `requirements.txt`。

| 检查 | 结果 |
|---|---|
| Agent 自动化测试 | 229 / 229 通过 |
| 数据、构建与提交包测试 | 26 / 26 通过 |
| 数据结构、引用及计算检查 | 1256 条通过 |
| 治理数据严格校验 | 0 errors，0 warnings |
| 完整 ESG 场景回放 | 9 项流程检查通过 |
| 提交包隔离复现 | 解压后使用标准库运行完整 demo，通过 |
| 提交包完整性 | 文件 SHA-256 校验；相同输入生成相同 ZIP |
| 本地 Python 依赖检查 | 无依赖冲突 |

统一入口：

```bash
make check
make package
```

自动化测试覆盖角色权限、schema、引用约束、事实更新、成本/日期、事务回滚、任务恢复、证据版本与人工状态转换。本次另外覆盖上传路径越界、JSON 类型和体积校验；包测试在隔离导入且禁用 site-packages 的 Python 子进程中运行。

默认演示执行调查、业务答复、方案与行动、责任接受、无关证据退回、重新提交及窄任务结案，并检查审计链。该演示明确使用 synthetic 场景和 scripted replay；本轮提交检查不产生模型 API 用量。

详细输出保存在本地 `runs/submission_validation/check.log`、`dataset_validation.json` 和 `governance_validation.log`。运行日志与数据库不随源码包分发，接收方可用上述命令重新生成。Live 行为评估与后续开发范围见 [开发说明](development.md)。
