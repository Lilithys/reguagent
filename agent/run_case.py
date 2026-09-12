#!/usr/bin/env python3
"""Persisted investigation CLI. Live mode calls the configured model; replay is explicit."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from project_paths import RUNS_ROOT,PROJECT_ROOT
from case_store import CaseStore,digest,uid
from source_intake import open_registered_case,register_local_snapshot
from investigation_tools import InvestigationTools,FACT_ID
from tool_runtime import ToolRunner,RunBudget
from replay_client import ReplayClient

GOAL='Investigate the SME ESG credit-monitoring change, source limitations, governance gaps and missing energy-data facts. Compare conditional economics when useful; resume affected findings after an owner answer. No final legal approval or action closure.'


def client_for(mode):
    if mode=='replay':return ReplayClient()
    if mode=='live':
        from llm import AnthropicToolClient
        return AnthropicToolClient()
    raise ValueError('Test cases cannot run through the public CLI')


def run(store,case_id):return ToolRunner(store,case_id,client_for(store.case(case_id)['mode'])).run()


def view(store,case_id,include_audit=False):
    result=dict(case=store.case(case_id),objects=store.objects(case_id),audit_chain_valid=store.verify_audit(case_id))
    if include_audit:result['audit_events']=store.audit_events(case_id)
    return result


def answer(store,case_id,path,request_key=None,question_version=1):
    payload=json.loads(Path(path).read_text())
    return InvestigationTools(store,case_id,'human_input').answer_question(FACT_ID,payload,
        request_key or 'answer-'+digest(payload),question_version)


def accept(store,case_id,action_key,accepted_by_role_id,action_version,request_key=None):
    """Human-only; deliberately not reachable through InvestigationTools/PERMISSIONS."""
    return store.accept_action(case_id,action_key,accepted_by_role_id,
        request_key or 'accept-'+digest(dict(action_key=action_key,role=accepted_by_role_id,version=action_version)),action_version)


def demo_replay(store,answer_fixture=None):
    case_id,_=open_registered_case(store,GOAL,'replay',nonce=uid('DEMO'))
    before=run(store,case_id)
    result=dict(case_id=case_id,mode='explicit_scripted_replay',before_answer=before)
    if answer_fixture and before['outcome']['status']=='waiting':
        result['answer_result']=answer(store,case_id,answer_fixture)
        result['after_answer']=run(store,case_id)
        result['energy_coverage']=InvestigationTools(store,case_id,'bank_investigator').energy_coverage()
    result['case_status']=store.case(case_id)['status']
    result['audit_chain_valid']=store.verify_audit(case_id)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',type=Path,default=RUNS_ROOT/'cases.sqlite3')
    sub=parser.add_subparsers(dest='command',required=True)
    start=sub.add_parser('start');start.add_argument('--mode',choices=['live','replay'],default='live')
    start.add_argument('--goal',default=GOAL);start.add_argument('--new',action='store_true')
    resume=sub.add_parser('resume');resume.add_argument('case_id')
    show=sub.add_parser('show');show.add_argument('case_id');show.add_argument('--audit',action='store_true')
    respond=sub.add_parser('answer');respond.add_argument('case_id');respond.add_argument('--file',type=Path,required=True)
    respond.add_argument('--request-key');respond.add_argument('--question-version',type=int,default=1)
    accept_cmd=sub.add_parser('accept');accept_cmd.add_argument('case_id');accept_cmd.add_argument('--action-key',required=True)
    accept_cmd.add_argument('--role',required=True,help='accepted_by_role_id; must match the action\'s own proposed accountable_role_id')
    accept_cmd.add_argument('--action-version',type=int,required=True);accept_cmd.add_argument('--request-key')
    demo=sub.add_parser('demo-replay');demo.add_argument('--answer-fixture',type=Path)
    source=sub.add_parser('import-source');source.add_argument('case_id');source.add_argument('--identifier',required=True);source.add_argument('--file',type=Path,required=True)
    args=parser.parse_args()
    with CaseStore(args.db) as store:
        if args.command=='start':
            case_id,created=open_registered_case(store,args.goal,args.mode,nonce=uid('CASE') if args.new else None)
            result=dict(created=created,**run(store,case_id))
        elif args.command=='resume':result=run(store,args.case_id)
        elif args.command=='show':result=view(store,args.case_id,args.audit)
        elif args.command=='answer':result=answer(store,args.case_id,args.file,args.request_key,args.question_version)
        elif args.command=='accept':result=accept(store,args.case_id,args.action_key,args.role,args.action_version,args.request_key)
        elif args.command=='import-source':result=register_local_snapshot(store,args.case_id,args.identifier,args.file,store.path.parent/'source_artifacts')
        else:result=demo_replay(store,args.answer_fixture)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if result.get('outcome',{}).get('status')=='failed' or result.get('case_status')=='failed':return 1
    return 0


if __name__=='__main__':
    try:raise SystemExit(main())
    except (ValueError,KeyError) as exc:
        print(json.dumps(dict(status='input_error',message=str(exc)),ensure_ascii=False),file=sys.stderr)
        raise SystemExit(2)
