# Regulatory Change-to-Action

以 `require.md` 为最高要求，围绕虚构 Northstar 银行的 SME ESG 案件构建可追溯、有人审核的 multi-agent 演示。bunq 仅作真实同业参考。

- [总体架构：文字描述](docs/architecture.md)
- [实施 TODO 与进度](TODO.md)
- [本轮 M1 实施与验证报告](research/m1_implementation_2026-09-12.md)
- [架构与代码 Review](research/architecture_review_2026-09-11.md)
- [同类产品、开源项目和公开数据集调研](research/market_landscape_2026-09-08.md)
- [数据内容与运行方式](calibrated_v0_2/README.md)、[数据字典](calibrated_v0_2/DATA_DICTIONARY.md)
- [来源审计与缺失证据](research/source_audit.md)

## 当前可运行

```bash
# 离线基线检查；不会调用 LLM、选择方案或执行批准
.venv/bin/python agent/run_demo.py --non-interactive

# 交互式查看基线并选择方案草案；回车不选择
.venv/bin/python agent/run_demo.py

# 可选方法审核：需要配置当前 LLM provider
.venv/bin/python agent/run_demo.py --review-ahp
```

当前主入口仍是确定性基线，不是已完成的自主四角色系统。M1（T01–T06）已实施；案件持久化、动态工具调用、业务访谈恢复、约束重规划、证据状态机及前端按后续 TODO 推进。上述离线检查不能证明 LLM 的调查质量。

## 数据与复现

唯一 baseline 是根目录 `calibrated_v0_2/`，数据版本 `0.2.1`，场景和法律研究截止仍为 `2026-09-08`。原始 `data/person1` 至 `person4` 不变。方法记录在 `config/`，运行输出写入 `runs/`；不要把整个工作区递归送给模型。

```bash
# 检查本地修订，临时构建并校验，备份后发布到唯一 baseline
.venv/bin/python scripts/calibrate_dataset.py

# 指定一个尚不存在的临时输出目录，并固定构建时间，便于逐字节复现
.venv/bin/python scripts/calibrate_dataset.py --output /tmp/northstar-review-build --build-timestamp 2026-09-12T00:00:00Z

.venv/bin/python -m unittest discover -s agent -p 'test_*.py'
.venv/bin/python -m unittest discover -s scripts -p 'test_*.py'
.venv/bin/python scripts/validate_dataset.py
.venv/bin/python data/regulatory-governance-dataset/scripts/validate_person1_data.py --root calibrated_v0_2 --strict --require-first-demo
.venv/bin/python scripts/run_eval.py
```

重建检测到未经合并的 baseline 修改时会停止发布，保留当前文件；先在新目录生成、审查差异，并把应保留的修订纳入迁移规则。已有人工矩阵原样迁移，旧版本的确认不会静默批准新方法。

全部法规要求仍为 silver、待合资格人工审核；官方全文版本快照、真实操作证据和完整模型端到端评测尚未补齐。
