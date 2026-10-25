"""Independently reconcile all users and candidate events with stdlib CSV/date sets."""
from pathlib import Path
from collections import defaultdict,Counter
from datetime import date,timedelta
import csv,json,hashlib,math
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def day(x):return date.fromisoformat(x)
u={r['user_id']:r for r in read(ROOT/'user_retention_cohort.csv')}
active=defaultdict(set)
for r in read(ROOT/'cohort_inputs/user_daily_activity.csv'):
    if r['active']=='1':active[r['user_id']].add(day(r['date']))
c=read(OUT/'candidate_eligibility.csv');o={r['candidate_id']:r for r in read(OUT/'candidate_outcomes.csv')}
d=json.loads((OUT/'behavior_flow_results.json').read_text(encoding='utf-8'))
dates=[date(2013,3,x) for x in range(8,12)]
expected={};flows=defaultdict(Counter);patterns=defaultdict(Counter)
for uid,r in u.items():
    acts=active[uid];s=r['segment'];state='no_learning' if not acts else 'one_learning_day' if len(acts)==1 else 'two_plus_learning_days'
    for seg in ['전체',s]:flows[seg][state]+=1
    if acts:
        first=min(acts)
        if first<=dates[1]:
            code=''.join('1' if first+timedelta(days=k) in acts else '0' for k in [1,2])
            for seg in ['전체',s]:patterns[seg][code]+=1
    if s!='습관 형성형':continue
    prior=day(r['last_active'])
    if acts:
        first=min(acts);expected['A|'+uid]=(first,(first-prior).days-1,0,prior)
    # Definition via date sets, independent of array state updates.
    for dt in dates:
        previous=sorted(a for a in acts if a<dt)
        last=previous[-1] if previous else prior
        if (dt-last).days-1==2:
            expected['B|'+uid]=(dt,2,len(previous),last);break
assert set(expected)==set(o)==set(r['candidate_id'] for r in c)
for r in c:
    dt,gap,n,latest=expected[r['candidate_id']]
    assert day(r['eligibility_date_utc'])==dt
    assert int(r['inactive_completed_dates_before_trigger'])==gap
    assert int(r['followup_active_days_before_trigger'])==n
    assert day(r['last_learning_date_before_trigger'])==latest
    assert day(r['snapshot_max_completed_date_utc'])==dt-timedelta(days=1)
    assert (r['primary_target']=='True')==(r['candidate']=='A' and gap>=1)
    assert day(r['segment_asof_utc'][:10])<=dt
    for col in ['active_days','recency','words_seen','sessions','last_active','segment']:assert r[col]==u[r['user_id']][col]
    out=o[r['candidate_id']];start=dt+timedelta(days=1) if r['candidate']=='A' else dt;end=start+timedelta(days=1)
    observed=end<=dates[-1]
    assert (out['fully_observed']=='True')==observed
    assert day(out['outcome_start_utc'])==start and day(out['outcome_end_utc'])==end
    if observed:assert int(float(out['any_learning']))==int(bool(active[r['user_id']]&{start,end}))
    else:assert out['any_learning']==''
for r in d['flow']:
    for key in ['no_learning','one_learning_day','two_plus_learning_days']:assert r[key+'_users']==flows[r['segment']][key]
    assert sum(flows[r['segment']].values())==r['baseline_users']
for r in d['aligned']:
    for code in ['00','10','01','11']:assert r['pattern_'+code+'_users']==patterns[r['segment']][code]
    assert r['within2_users']==sum(patterns[r['segment']][code] for code in ['10','01','11'])
for r in d['candidates']:
    q=[x for x in o.values() if x['candidate']==r['candidate'] and (r['eligibility_date_utc']=='합계' or x['eligibility_date_utc']==r['eligibility_date_utc'])]
    if r['scope']=='직전 비활동 0일':q=[x for x in q if int(x['trigger_gap'])==0]
    if r['scope']=='직전 비활동 1일 이상':q=[x for x in q if int(x['trigger_gap'])>=1]
    obs=[x for x in q if x['fully_observed']=='True'];k=sum(int(float(x['any_learning'])) for x in obs) if obs else None
    assert (len(q),len(obs),k)==(r['eligible_users'],r['fully_observed_users'],r['learning_users'])
    if obs:assert math.isclose(r['rate'],k/len(obs),abs_tol=1e-14)
    else:assert r['rate'] is None and r['learning_users'] is None
# Prefix audit: membership up to each date depends only on activity observed up to that date.
for cutoff in dates:
    keys=set()
    for uid,r in u.items():
        if r['segment']!='습관 형성형':continue
        acts={dt for dt in active[uid] if dt<=cutoff};prior=day(r['last_active'])
        if acts:keys.add('A|'+uid)
        for dt in dates:
            if dt>cutoff:break
            last=max([prior]+[a for a in acts if a<dt])
            if (dt-last).days-1==2:keys.add('B|'+uid);break
    assert keys=={key for key,value in expected.items() if value[0]<=cutoff}
assert not ({'any_learning','fully_observed','followup_state','inactive_days_at_followup_end','followup_active_days','first_return_date'} & set(c[0]))
primary=read(OUT/'primary_candidate_eligibility.csv')
assert len(primary)==4809 and {r['candidate_id'] for r in primary}=={r['candidate_id'] for r in c if r['primary_target']=='True'}
assert set(r['candidate_id'] for r in read(OUT/'primary_candidate_outcomes.csv'))=={r['candidate_id'] for r in primary}
for name,h in d['source_hashes'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h
validation=dict(all_users_recomputed=len(u),candidate_events_verified=len(c),date_prefixes_without_future_activity_verified=4,baseline_flows_verified=7,aligned_patterns_verified=28,candidate_summary_rows_verified=len(d['candidates']),unobserved_results_blank=True,eligibility_has_no_outcome_columns=True,source_hashes_unchanged=True)
(OUT/'analysis_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False,indent=2))
