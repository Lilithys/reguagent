# Development guide

## Environment

Python 3.12+；验证环境为 Python 3.14.6。`requirements.txt` 固定验证使用的 NumPy 和两种模型 SDK 版本。默认场景回放使用标准库；完整测试与 Live 模式使用安装后的环境。

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
make check
```

Windows 可使用 `.venv\Scripts\activate`，并以 README 中的 Python 命令代替 Make。导入 PDF 快照时另安装 `pypdf`；TXT 快照不需要该依赖。

## Runtime modes

| 模式 | 调用来源 | 用途 |
|---|---|---|
| `replay` | 明确编排的工具调用和模拟决定 | 可复现的完整场景演示、回归测试 |
| `live` | 已配置的模型 provider | 由模型选择工具和专家任务的调查 |

不存在 Live 失败后静默切换 Replay 的路径。CLI 通用预算参数放在 `start`、`resume` 等子命令之前；所有续跑必须使用同一个数据库和案件 ID。

`--max-model-calls` 包含重试；`--max-seconds` 包含等待；`--max-request-tokens` 是输入与预留输出的本地估算上限。`--tokens-per-minute` 从同一案件近期审计恢复预留，不覆盖其他应用的用量。超出预算时保留已提交的任务状态。

模型配置来自终端环境或 `.env.local`。配置辅助命令以 owner-only 权限新建文件，不覆盖已有文件；已有配置可自行编辑。`.env.example` 是空密钥模板。模型 ID 与账户限额由使用者配置，代码不自动更换 provider。

## Case operations

`python agent/run_case.py --help` 提供全部入口。主要操作包括：

- `start / resume / show`：创建、恢复、查看案件。
- `answer`：提交带角色、分母、日期和来源的事实答复。
- `accept`：人工接受指定版本的行动责任。
- `submit-evidence / decide-evidence / close-action`：提交证据、人工决定和任务结案。
- `import-source`：导入本地来源快照，并保存 hash 与版本信息。

后四类关键写入通过服务端校验，接受/审核/结案不作为 LLM 可调用工具。当前本地 HTTP API 适合单人演示环境，默认绑定 `127.0.0.1`；身份字段为原型角色声明，尚未接入身份认证服务。

## Verification and packaging

```bash
python -m unittest discover -s agent -p 'test_*.py'
python -m unittest discover -s scripts -p 'test_*.py'
python scripts/validate_dataset.py
python data/regulatory-governance-dataset/scripts/validate_person1_data.py --root calibrated_v0_2 --strict --require-first-demo
python scripts/demo.py
python scripts/package_submission.py
```

提交包按允许清单构建，保留代码、测试、固定数据、模拟材料和使用文档。文件排序、ZIP 时间和权限固定，内容不变时可生成一致压缩包。包内 `SUBMISSION_MANIFEST.json` 保存每个源文件的 SHA-256；包外 `.zip.sha256` 用于传输校验。

本地凭据、运行数据库、开发备份、历史调查日志和第三方 PDF 不进入提交包。重新解压后的包可以自行执行 demo、校验和测试。

## Evaluation scope and next iteration

本地测试覆盖工具权限、输入合同、引用约束、成本/日期计算、事务回滚、检查点恢复及证据状态机。完整场景以 Replay 验证；已有 Live 记录覆盖工具往返、专家委派和跨运行恢复。

当前 Live 行为优化重点是缩小专家任务范围并提前交付有引用的发现；最近一次受限实验成功收到 10 次响应，但尚未形成正式 Finding。后续验收将关注“单一问题 → 可审核交付物”，以及预算约束贯通、来源更新检测和交互界面。该研发记录与默认演示的状态服务验证分别评估。
