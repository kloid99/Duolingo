"""Synthetic boundary validation only; no treatment effect is estimated from actual data."""
from pathlib import Path
import json
from measurement_reference import evaluate,allowed_plan_dates,utc
ROOT=Path(__file__).resolve().parent
a=[dict(assignment_id='synthetic-c',experiment_id='synthetic-only',user_id='c',variant='control',eligibility_at_utc='2026-10-01T10:00:00Z',assigned_at_utc='2026-10-01T10:00:01Z'),dict(assignment_id='synthetic-t',experiment_id='synthetic-only',user_id='t',variant='treatment',eligibility_at_utc='2026-10-01T23:00:00Z',assigned_at_utc='2026-10-01T23:00:01Z')]
coverage=[dict(date_utc=d,complete=True,version=1,checked_at_utc='2026-10-04T00:00:00Z') for d in ['2026-10-02','2026-10-03']]
def event(uid,time,key):return dict(event_id=key,user_id=uid,occurred_at_utc=time,received_at_utc=time,valid=True)
cases=0
def run(events,cov=coverage,freeze='2026-10-06T00:00:00Z'):
    return evaluate(a,events,cov,freeze)
assert [r['y'] for r in run([])['outcomes']]==[0,0];cases+=1
assert run([event('t','2026-10-02T00:00:00Z','start')])['outcomes'][1]['y']==1;cases+=1
assert run([event('t','2026-10-04T00:00:00Z','end')])['outcomes'][1]['y']==0;cases+=1
assert run([event('t','2026-10-01T23:59:59Z','D0')])['outcomes'][1]['y']==0;cases+=1
assert run([event('t','2026-10-03T23:59:59Z','last')])['outcomes'][1]['y']==1;cases+=1
assert all(r['y'] is None for r in run([],[],freeze='2026-10-06T00:00:00Z')['outcomes']);cases+=1
assert all(r['y'] is None for r in run([],freeze='2026-10-03T23:59:59Z')['outcomes']);cases+=1
# A treatment user without exposure is still in the denominator.
assert run([])['groups']['treatment']['n']==1;cases+=1
e=event('t','2026-10-02T10:00:00Z','late');e['received_at_utc']='2026-10-07T00:00:00Z'
assert run([e])['outcomes'][1]['y']==0;cases+=1
e=event('t','2026-10-02T10:00:00Z','dup');assert run([e,e])['outcomes'][1]['y']==1;cases+=1
try:evaluate(a+[a[0]],[],coverage,'2026-10-06T00:00:00Z');raise AssertionError('duplicate not rejected')
except ValueError:cases+=1
changed=dict(e,valid=False)
try:run([e,changed]);raise AssertionError('conflict not rejected')
except ValueError:cases+=1
assert run([],[])['difference_missing_bounds']==[-1,1] and run([],[])['primary_test'] is None;cases+=1
r=run([event('t','2026-10-02T01:00:00+01:00','tz')]);assert r['outcomes'][1]['y']==1;cases+=1
for freeze in ['2026-10-04T00:00:00Z','2026-10-05T23:59:59Z']:
    assert all(r['y'] is None for r in run([],freeze=freeze)['outcomes']);cases+=1
assert all(r['y']==0 for r in run([],freeze='2026-10-06T00:00:00Z')['outcomes']);cases+=1
future=[dict(c,checked_at_utc='2026-10-07T00:00:00Z') for c in coverage]
assert all(r['y'] is None for r in run([],future)['outcomes']);cases+=1
revised=coverage+[dict(coverage[0],version=2,complete=False,checked_at_utc='2026-10-05T00:00:00Z')]
assert all(r['y'] is None for r in run([],revised)['outcomes']);cases+=1
future_revision=coverage+[dict(coverage[0],version=2,complete=False,checked_at_utc='2026-10-07T00:00:00Z')]
assert all(r['y']==0 for r in run([],future_revision)['outcomes']);cases+=1
assert run([],list(reversed(revised)))['outcomes'][0]['y'] is None;cases+=1
for bad in [[dict(c,version=0) for c in coverage],coverage+[coverage[0]],[dict(c,checked_at_utc='2026-10-02T00:00:00Z') for c in coverage],[{k:v for k,v in c.items() if k!='checked_at_utc'} for c in coverage],coverage+[dict(coverage[0],version=2,checked_at_utc='2026-10-03T00:00:00Z')]]:
    try:run([],bad);raise AssertionError('invalid coverage accepted')
    except (ValueError,KeyError):cases+=1
for invalid in [-1,1.5,True]:
    try:evaluate(a,[],coverage,'2026-10-06T00:00:00Z',invalid);raise AssertionError('invalid lateness accepted')
    except ValueError:cases+=1
e=event('t','2026-10-02T12:00:00Z','within-lag');e['received_at_utc']='2026-10-05T23:59:59Z'
assert run([e])['outcomes'][1]['y']==1;cases+=1
seven=[dict(date_utc=f'2026-10-{i:02d}',version=1,checked_at_utc='2026-10-09T00:00:00Z',complete=True) for i in range(2,9)]
seven_events=[event('t',f'2026-10-{i:02d}T12:00:00Z',str(i)) for i in range(2,6)]
assert run(seven_events,seven,freeze='2026-10-10T23:59:59Z')['outcomes'][1]['secondary_nsm'] is None;cases+=1
r=run(seven_events,seven,freeze='2026-10-11T00:00:00Z')
assert r['outcomes'][1]['secondary_nsm']==1 and r['outcomes'][1]['secondary_active_days']==4 and r['secondary_groups']['control']['n']==1;cases+=1
assert run(seven_events[:-1],seven,freeze='2026-10-11T00:00:00Z')['outcomes'][1]['secondary_nsm']==0;cases+=1
assert run(seven_events+[event('c','2026-10-09T00:00:00Z','D8')],seven,freeze='2026-10-11T00:00:00Z')['outcomes'][0]['secondary_active_days']==0;cases+=1
assert run(seven_events,seven[:-1],freeze='2026-10-11T00:00:00Z')['outcomes'][1]['secondary_nsm'] is None;cases+=1
for timezone in ['Asia/Seoul','America/New_York','UTC']:
    options=allowed_plan_dates('2026-03-07T12:00:00Z',timezone)
    assert utc(options[0]['allowed_start_local'])==utc('2026-03-08T00:00:00Z')
    assert utc(options[-1]['allowed_end_exclusive_local'])==utc('2026-03-10T00:00:00Z')
    assert all(utc(x['allowed_end_exclusive_local'])==utc(y['allowed_start_local']) for x,y in zip(options,options[1:]));cases+=1
report=dict(synthetic_validation_only=True,boundary_and_integrity_cases_passed=cases,actual_experiment_assignments=0,actual_experiment_effect_estimated=False)
import sys
import hashlib
report['validated_source_hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['measurement_reference.py','verify_measurement_reference.py','experiment_config.json']}
if '--write-validation' in sys.argv:(ROOT/'measurement_validation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
