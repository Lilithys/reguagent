"""Budgeted role-specific tool loop. Shared budget bounds nested specialist work."""
from __future__ import annotations
import json
import time
import random
import math
from dataclasses import dataclass,field
from datetime import datetime
from case_store import digest,uid,encode
from investigation_tools import InvestigationTools,tool_definitions,PERMISSIONS,SCHEMAS
from tool_contracts import validate
from roles import system_prompt
from request_controls import bounded_messages,error_diagnostic,RequestTooLarge,TokenWindow


class BudgetExceeded(RuntimeError):pass

@dataclass
class RunBudget:
    max_model_calls:int=36
    max_tool_calls:int=70
    max_delegations:int=5
    max_tokens:int=160000
    max_seconds:float=180
    max_request_tokens:int=16000
    max_output_tokens:int=2400
    min_request_interval:float=0
    tokens_per_minute:int=0
    model_calls:int=0
    tool_calls:int=0
    delegations:int=0
    tokens:int=0
    started:float=field(default_factory=time.monotonic)

    def __post_init__(self):
        for name in ('max_model_calls','max_tool_calls','max_delegations','max_tokens','max_request_tokens','max_output_tokens'):
            if type(getattr(self,name)) is not int or getattr(self,name)<=0:raise ValueError(name+' must be a positive integer')
        if self.max_request_tokens-self.max_output_tokens<256:raise ValueError('Request budget must leave at least 256 input tokens')
        if not math.isfinite(self.max_seconds) or self.max_seconds<=0:raise ValueError('max_seconds must be positive and finite')
        if not math.isfinite(self.min_request_interval) or self.min_request_interval<0:raise ValueError('min_request_interval must be non-negative and finite')
        if type(self.tokens_per_minute) is not int or self.tokens_per_minute<0:raise ValueError('tokens_per_minute must be a non-negative integer')

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
        self.last_request_started=None
        self.last_diagnostic=None
        self.token_window=TokenWindow()
        if mode=='live' and self.budget.tokens_per_minute:
            now=time.monotonic();wall=time.time()
            for event in self.store.audit_events(case_id):
                if event['event_type']!='model_request':continue
                payload=event['payload']
                reserved=payload.get('estimated_input_tokens',0)+payload.get('output_token_cap',0)
                age=max(0,wall-datetime.fromisoformat(event['created_at']).timestamp())
                if age<60 and type(reserved) is int and reserved>0:self.token_window.record(now-age,reserved)

    def _pause(self,seconds,reason,role):
        if seconds<=0:return
        if seconds+1>=self.budget.remaining_seconds():
            raise BudgetExceeded('Required wait exceeds remaining run time; case can be resumed later')
        self.store.audit(self.case_id,'request_wait',dict(seconds=round(seconds,3),reason=reason),actor=role)
        # Short interruptible sleeps; all waiting consumes the shared run budget.
        end=time.monotonic()+seconds
        while time.monotonic()<end:
            time.sleep(max(0,min(1,end-time.monotonic())))
            self.budget.check()

    def _invoke(self,role,messages,definitions):
        # SDK retries remain disabled. One bounded retry; never immediately hammer
        # a throttled endpoint or retry quota/context errors unchanged.
        system=system_prompt(role)
        request_cap=min(self.budget.max_request_tokens,self.budget.tokens_per_minute or self.budget.max_request_tokens)
        if request_cap<512:raise RequestTooLarge('Configured request/TPM budget is too small for this tool protocol.')
        max_output=min(self.budget.max_output_tokens,request_cap-256)
        bounded,estimated_input,compacted=bounded_messages(system,messages,definitions,
            request_cap-max_output)
        if compacted:self.store.audit(self.case_id,'context_compacted',dict(role=role,observations=compacted,
            estimated_input_tokens=estimated_input),actor=role)
        for attempt in range(2):
            self.budget.check()
            if self.budget.model_calls>=self.budget.max_model_calls:raise BudgetExceeded('Model call budget exhausted')
            if self.last_request_started is not None and self.client.mode=='live':
                self._pause(max(0,self.budget.min_request_interval-(time.monotonic()-self.last_request_started)),
                    'minimum_request_interval',role)
            remaining_tokens=self.budget.max_tokens-self.budget.tokens-estimated_input
            if remaining_tokens<256:raise BudgetExceeded('Insufficient remaining context/output token budget')
            reserved_tokens=estimated_input+min(max_output,remaining_tokens)
            if self.client.mode=='live':
                self._pause(self.token_window.delay(time.monotonic(),reserved_tokens,self.budget.tokens_per_minute),
                    'tokens_per_minute_window',role)
            self.budget.model()
            before=getattr(self.client,'request_attempts',0);start=time.monotonic()
            self.last_request_started=start
            if self.client.mode=='live':self.token_window.record(start,reserved_tokens)
            self.store.audit(self.case_id,'model_request',dict(role=role,attempt=attempt+1,
                estimated_input_tokens=estimated_input,output_token_cap=min(max_output,remaining_tokens),
                request_token_cap=request_cap,tokens_per_minute=self.budget.tokens_per_minute),actor=role)
            try:
                response=self.client.generate(role=role,system=system,messages=bounded,tools=definitions,
                    max_tokens=min(max_output,remaining_tokens),timeout=max(.1,min(35,self.budget.remaining_seconds())))
            except Exception as exc:
                diagnostic=error_diagnostic(exc);self.last_diagnostic=diagnostic
                self.store.audit(self.case_id,'model_error',dict(role=role,error_type=type(exc).__name__,attempt=attempt+1,
                    api_requests_attempted=getattr(self.client,'request_attempts',0)-before,**diagnostic),actor=role)
                if not diagnostic['retryable'] or attempt==1:raise
                if self.budget.model_calls>=self.budget.max_model_calls:
                    raise BudgetExceeded('Model call budget exhausted before retry') from None
                delay=diagnostic['retry_after_seconds']
                if delay is None:delay=(8 if diagnostic['category']=='rate_limit' else 1)*2**attempt+random.uniform(0,1)
                self._pause(delay,'provider_retry',role)
                continue
            self.last_diagnostic=None
            usage=response.get('usage',{})
            tokens=usage.get('input_tokens',estimated_input)+usage.get('output_tokens',max(1,len(encode(response.get('content',[])))//3))
            if type(tokens) is not int or tokens<0:raise ValueError('Invalid provider usage metadata')
            self.budget.tokens+=tokens
            self.store.audit(self.case_id,'model_response',dict(role=role,latency_seconds=round(time.monotonic()-start,3),
                tokens=tokens,stop_reason=response.get('stop_reason'),mode=self.client.mode,
                input_tokens=usage.get('input_tokens'),output_tokens=usage.get('output_tokens'),
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
            if self.last_diagnostic:outcome['provider_diagnostic']=self.last_diagnostic
            if isinstance(exc,(RequestTooLarge,BudgetExceeded)):outcome['message']=str(exc)
            self.store.set_status(self.case_id,'failed',outcome['error_type'])
        result=dict(case_id=self.case_id,outcome=outcome,budget=self.budget.summary(),
                    api_requests_attempted=getattr(self.client,'request_attempts',0),mode=self.client.mode)
        self.store.audit(self.case_id,'run_finished',result)
        return result
