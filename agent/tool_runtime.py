"""Budgeted role-specific tool loop. Shared budget bounds nested specialist work."""
from __future__ import annotations
import json
import time
from dataclasses import dataclass,field
from case_store import digest,uid,encode
from investigation_tools import InvestigationTools,tool_definitions,PERMISSIONS,SCHEMAS
from tool_contracts import validate
from roles import system_prompt


class BudgetExceeded(RuntimeError):pass

@dataclass
class RunBudget:
    max_model_calls:int=36
    max_tool_calls:int=70
    max_delegations:int=5
    max_tokens:int=160000
    max_seconds:float=180
    model_calls:int=0
    tool_calls:int=0
    delegations:int=0
    tokens:int=0
    started:float=field(default_factory=time.monotonic)

    def remaining_seconds(self):return self.max_seconds-(time.monotonic()-self.started)
    def check(self):
        if self.remaining_seconds()<=0 or self.tokens>=self.max_tokens:raise BudgetExceeded('Time or token budget exhausted')
    def model(self):
        self.check()
        if self.model_calls>=self.max_model_calls:raise BudgetExceeded('Model call budget exhausted')
        self.model_calls+=1
    def tool(self):
        self.check()
        if self.tool_calls>=self.max_tool_calls:raise BudgetExceeded('Tool call budget exhausted')
        self.tool_calls+=1
    def delegate(self):
        self.check()
        if self.delegations>=self.max_delegations:raise BudgetExceeded('Delegation budget exhausted')
        self.delegations+=1
    def summary(self):return dict(model_turn_attempts=self.model_calls,tool_calls=self.tool_calls,
        delegations=self.delegations,tokens=self.tokens,elapsed_seconds=round(time.monotonic()-self.started,3))


class ToolRunner:
    def __init__(self,store,case_id,client,budget=None):
        self.store=store;self.case_id=case_id;self.client=client;self.budget=budget or RunBudget();self.run_id=uid('RUN')
        mode=store.case(case_id)['mode']
        if getattr(client,'mode',None)!=mode:raise ValueError('Client and case modes must match; no silent replay fallback')
        self.active_tasks=set()

    def _invoke(self,role,messages,definitions):
        # The client uses zero SDK retries. At most one explicit transient retry,
        # counted in the same global budget; credentials/errors are never printed.
        for attempt in range(2):
            self.budget.model()
            estimated_input=max(1,len(encode(messages)+encode(definitions))//3)
            remaining_tokens=self.budget.max_tokens-self.budget.tokens-estimated_input
            if remaining_tokens<256:raise BudgetExceeded('Insufficient remaining context/output token budget')
            before=getattr(self.client,'request_attempts',0);start=time.monotonic()
            try:
                response=self.client.generate(role=role,system=system_prompt(role),messages=messages,tools=definitions,
                    max_tokens=min(2400,remaining_tokens),timeout=max(.1,min(35,self.budget.remaining_seconds())))
            except Exception as exc:
                self.store.audit(self.case_id,'model_error',dict(role=role,error_type=type(exc).__name__,attempt=attempt+1,
                    api_requests_attempted=getattr(self.client,'request_attempts',0)-before),actor=role)
                # SDK exception classes carry HTTP status, not a safe-to-log body.
                transient=getattr(exc,'status_code',None) in (429,500,502,503,504) or type(exc).__name__ in ('APIConnectionError','APITimeoutError','TimeoutError')
                if not transient or attempt==1:raise
                continue
            usage=response.get('usage',{})
            tokens=usage.get('input_tokens',estimated_input)+usage.get('output_tokens',max(1,len(encode(response.get('content',[])))//3))
            if type(tokens) is not int or tokens<0:raise ValueError('Invalid provider usage metadata')
            self.budget.tokens+=tokens
            self.store.audit(self.case_id,'model_response',dict(role=role,latency_seconds=round(time.monotonic()-start,3),
                tokens=tokens,stop_reason=response.get('stop_reason'),mode=self.client.mode,
                api_requests_attempted=getattr(self.client,'request_attempts',0)-before),actor=role)
            self.budget.check()
            return response

    def _task(self,role,task,task_key,depth=0):
        revision=self.store.case(self.case_id)['revision']
        identity=digest(dict(role=role,task=task,key=task_key,revision=revision))
        cached=self.store.get(self.case_id,'Task',identity)
        if cached and cached['status']=='completed':return dict(cached['payload']['result'],reused=True)
        if identity in self.active_tasks:raise ValueError('Duplicate active task')
        self.active_tasks.add(identity)
        service=InvestigationTools(self.store,self.case_id,role)
        task_payload=dict(role=role,task=task,task_key=task_key,run_id=self.run_id,case_revision=revision)
        self.store.put(self.case_id,'Task',identity,task_payload,status='running')
        messages=[dict(role='user',content=encode(dict(task=task,case_id=self.case_id,case_revision=revision,
            instruction='Inspect case_context and choose tools as needed. Return through finish.')))]
        definitions=tool_definitions(role);repeated={};no_tool_turns=0;completion=None
        try:
            for _ in range(12):
                response=self._invoke(role,messages,definitions)
                content=response.get('content')
                if not isinstance(content,list):raise ValueError('Malformed model content')
                calls=[b for b in content if isinstance(b,dict) and b.get('type')=='tool_use']
                if response.get('stop_reason') in ('refusal','max_tokens'):
                    raise ValueError('Model refused or truncated this task; state is retained')
                if not calls:
                    no_tool_turns+=1
                    if no_tool_turns>1:raise ValueError('No structured tool call after correction')
                    messages.append(dict(role='assistant',content=content or 'No tool result supplied.'))
                    messages.append(dict(role='user',content='Use an available investigation tool or finish with a structured status.'))
                    continue
                ids=[b.get('id') for b in calls]
                if any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):raise ValueError('Malformed/duplicate tool-use IDs')
                messages.append(dict(role='assistant',content=content))
                results=[]
                for call in calls:
                    self.budget.tool();name=call.get('name');arguments=call.get('input');error=False
                    started=time.monotonic()
                    try:
                        if completion:raise ValueError('No tools may execute after finish in the same response')
                        if name not in PERMISSIONS[role]:raise PermissionError('Tool is not permitted for this role')
                        validate(arguments,SCHEMAS[name])
                        progress=digest([(o['object_id'],o['status']) for o in self.store.objects(self.case_id) if o['kind']!='Task'])
                        signature=digest(dict(tool=name,arguments=arguments,progress=progress))
                        repeated[signature]=repeated.get(signature,0)+1
                        if repeated[signature]>2:raise BudgetExceeded('Repeated identical tool request without progress')
                        if name=='delegate':
                            if depth!=0:raise PermissionError('Specialists cannot delegate')
                            self.budget.delegate()
                            output=self._task(arguments['role'],arguments['task'],arguments['task_key'],depth+1)
                        elif name=='finish':
                            if role=='coordinator' and arguments['status']=='completed':
                                if any(q['status']=='open' for q in self.store.objects(self.case_id,'Question')):
                                    raise ValueError('Open questions remain: finish waiting or continue independent work')
                                if any(o['status']=='stale' for o in self.store.objects(self.case_id) if o['kind'] in ('Finding','GapAssessment')):
                                    raise ValueError('Affected findings are stale; recompute or explicitly return needs_review')
                            completion=dict(arguments,role=role,review_status='provisional')
                            output=completion
                        else:output=getattr(service,name)(**arguments)
                    except BudgetExceeded:raise
                    except (ValueError,KeyError,PermissionError,TypeError) as exc:
                        error=True;output=dict(status='tool_error',error_type=type(exc).__name__,message=str(exc)[:600])
                    encoded=encode(output)
                    if len(encoded)>42000:
                        output=dict(status='result_too_large',message='Narrow the search or read individual record IDs.',
                            record_ids=[r.get('record_id') for r in output.get('results',[])],truncated=True)
                        encoded=encode(output)
                    self.store.audit(self.case_id,'tool_result',dict(role=role,task_id=identity,tool_call_id=call['id'],
                        tool=name,arguments=arguments,output=output,is_error=error,elapsed_seconds=round(time.monotonic()-started,3)),actor=role)
                    results.append(dict(type='tool_result',tool_use_id=call['id'],content=encoded,is_error=error))
                messages.append(dict(role='user',content=results))
                if completion:
                    status='completed' if completion['status']=='completed' else 'waiting'
                    self.store.put(self.case_id,'Task',identity,dict(task_payload,result=completion),status=status)
                    return completion
            raise BudgetExceeded('Specialist turn limit exhausted')
        except Exception as exc:
            self.store.put(self.case_id,'Task',identity,dict(task_payload,error_type=type(exc).__name__),status='failed')
            raise
        finally:self.active_tasks.discard(identity)

    def run(self):
        self.store.set_status(self.case_id,'running','Investigation run started')
        try:
            outcome=self._task('coordinator',self.store.case(self.case_id)['goal'],'coordinate')
            status={'completed':'investigation_complete','waiting':'waiting_for_input','needs_review':'needs_review'}[outcome['status']]
            self.store.set_status(self.case_id,status,outcome['summary'])
        except Exception as exc:
            outcome=dict(status='failed',error_type=type(exc).__name__,
                message='Investigation stopped; committed case state is retained. Inspect audit events and provider configuration before resuming.')
            self.store.set_status(self.case_id,'failed',outcome['error_type'])
        result=dict(case_id=self.case_id,outcome=outcome,budget=self.budget.summary(),
                    api_requests_attempted=getattr(self.client,'request_attempts',0),mode=self.client.mode)
        self.store.audit(self.case_id,'run_finished',result)
        return result
