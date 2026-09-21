#!/usr/bin/env python3
"""Run the complete synthetic ESG demonstration and export reviewable artifacts."""
import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(PROJECT_ROOT/'agent'))
sys.path.insert(0,str(PROJECT_ROOT/'scripts'))
from case_store import CaseStore
from run_case import demo_replay
import view_adapter


def export_demo(output):
    output=Path(output).resolve()
    with CaseStore(output/'cases.sqlite3') as store:
        result=demo_replay(store,PROJECT_ROOT/'materials/esg_demo/energy_answer.synthetic.json')
        case_id=result['case_id']
        investigation=view_adapter.investigation_summary(store,case_id)
        plans=view_adapter.plan_and_action_view(store,case_id)
        evidence=view_adapter.evidence_view(store,case_id)
        runs=[v for v in result.values() if isinstance(v,dict) and 'outcome' in v]
        checks=dict(
            interview_requested=result['before_answer']['outcome']['status']=='waiting',
            answer_applied=result.get('after_answer',{}).get('outcome',{}).get('status')=='completed',
            unrelated_evidence_rejected=result.get('reject_bad_design',{}).get('status')=='rejected',
            replacement_evidence_verified=result.get('verify_good_design',{}).get('status')=='verified',
            test_evidence_verified=result.get('verify_test',{}).get('status')=='verified',
            action_closed=result.get('close_result',{}).get('status')=='verified',
            agent_runs_completed=all(r['outcome']['status'] in ('waiting','completed') for r in runs),
            audit_chain_valid=store.verify_audit(case_id),
            zero_api_requests=all(r['api_requests_attempted']==0 for r in runs))
        summary=dict(project='Regulatory Change-to-Action',mode='scripted_replay',synthetic=True,
            case_id=case_id,status='passed' if all(checks.values()) else 'failed',checks=checks,
            api_requests_attempted=sum(r['api_requests_attempted'] for r in runs),
            human_steps='Simulated demo decisions through the human-only service endpoints',
            energy_coverage=result.get('energy_coverage'),
            investigation=investigation,**plans,evidence=evidence)
        audit=view_adapter.audit_log(store,case_id)
    for name,content in (('summary.json',summary),('workflow.json',result),('audit.json',audit)):
        (output/name).write_text(json.dumps(content,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    lines=['# Regulatory Change-to-Action — Demo report','',
        '**Mode:** scripted replay · synthetic Northstar scenario · 0 external API requests','',
        f"**Case:** `{case_id}`  ",f"**Result:** {summary['status']}",'',
        '## Workflow checks','', '| Check | Result |','|---|---|']
    lines += [f"| {name} | {'PASS' if passed else 'FAIL'} |" for name,passed in checks.items()]
    lines += ['', '## Investigation findings','']
    for finding in investigation['findings']:
        lines += [f"### {finding['key']}",'',finding['summary'],'',
            'References: '+', '.join('`'+r+'`' for r in finding['reference_ids']),'']
    lines += ['## Response and ownership','']
    for action in plans['actions']:
        lines += [f"- **{action['title']}** — `{action['status']}`",
            f"- Accountable role: `{action['accountable_role_id']}`",
            f"- Internal target: {action['target_date']}; regulatory date: {action['regulatory_due_date']}",'']
    lines += ['## Review boundary','',
        'Answers and human decisions are simulated for this demonstration. Findings retain their provisional status. '
        'Closure applies to the scoped demo action; it is not institution-wide legal approval.','',
        'The accompanying JSON and SQLite database retain references, evidence history and audit events.','']
    (output/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=PROJECT_ROOT/'runs/demo')
    args=parser.parse_args()
    summary=export_demo(args.output)
    print('Regulatory Change-to-Action | ESG demo | scripted replay')
    print('Synthetic answers and review decisions | external API requests: 0')
    for name,passed in summary['checks'].items():print(f"  {'PASS' if passed else 'FAIL'}  {name}")
    print('Case:',summary['case_id'])
    print('Report:',(args.output/'report.md').resolve())
    print('Artifacts: summary.json, workflow.json, audit.json, cases.sqlite3')
    return 0 if summary['status']=='passed' else 1


if __name__=='__main__':raise SystemExit(main())
