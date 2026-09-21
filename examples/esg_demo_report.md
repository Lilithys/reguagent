# Regulatory Change-to-Action — Demo report

**Mode:** scripted replay · synthetic Northstar scenario · 0 external API requests

**Case:** `CASE-53f690da27b64df0b84d042ed8e6dc32`  
**Result:** passed

## Workflow checks

| Check | Result |
|---|---|
| interview_requested | PASS |
| answer_applied | PASS |
| unrelated_evidence_rejected | PASS |
| replacement_evidence_verified | PASS |
| test_evidence_verified | PASS |
| action_closed | PASS |
| agent_runs_completed | PASS |
| audit_chain_valid | PASS |
| zero_api_requests | PASS |

## Investigation findings

### source-summary

来源为已登记候选；版本检查=insufficient_source_snapshots。候选范围=in_scope，时间=application_date_reached。使用整理后的条款转述，未独立完成原文抽取或法律审核。

References: `REF-13b33813bc34a869b50d6765`, `CIT-REQ-ESG-CREDIT-MONITORING-001-01`, `SOURCE-COMPARE-beeab69f2c291272`, `CALC-SCOPE-3d445682091cbc3e`

### conditional-costs

两条要求的模板三年TCO：{'OPT-ESG-MANUAL': 806818.0, 'OPT-ESG-AUTOMATED': 451436.0, 'OPT-ESG-HYBRID': 481002.0}。团队产能未知，最低成本不等于获批建议。

References: `CALC-COSTS-1ed096f31adda1eb`

### energy-data

按归属明确的答复：10000个存量SME客户中，6500个有可用能源数据，3500个待补齐。答复不是实操证据。

References: `CALC-ENERGY-4269cda992602006de12`

## Response and ownership

- **部署自动化存量ESG监测控制** — `verified`
- Accountable role: `ROLE-CHIEF-RISK`
- Internal target: 2027-03-08; regulatory date: 2026-01-11

## Review boundary

Answers and human decisions are simulated for this demonstration. Findings retain their provisional status. Closure applies to the scoped demo action; it is not institution-wide legal approval.

The accompanying JSON and SQLite database retain references, evidence history and audit events.
