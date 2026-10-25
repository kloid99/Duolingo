"""Historical behavior flow and candidate eligibility from information at each trigger."""
from pathlib import Path
import json, hashlib, math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'behavior_flow'
DATES=[f'2013-03-{d:02d}' for d in range(8,12)]
SEGS=['전체','꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형']
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def clean(f):return json.loads(f.to_json(orient='records',force_ascii=False,double_precision=15))
def wilson(k,n):
    if not n:return None,None
    z=1.959963984540054;p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return center-half,center+half

def main():
    OUT.mkdir(exist_ok=True)
    names=['user_retention_cohort.csv','user_daily_retention.csv','first_return_cohorts.csv','cohort_inputs/user_daily_activity.csv']
    hashes={n:sha(ROOT/n) for n in names}
    meta=json.loads((ROOT/'results_retention.json').read_text(encoding='utf-8'))
    for n in names[:3]:assert hashes[n]==meta['outputs'][n]['sha256']
    assert hashes[names[3]]==meta['source_files']['user_daily_activity.csv']['sha256']
    u=pd.read_csv(ROOT/names[0],low_memory=False);panel=pd.read_csv(ROOT/names[1]);source=pd.read_csv(ROOT/names[3])
    assert len(u)==82467 and u.user_id.is_unique
    assert len(panel)==len(u)*4 and not panel.duplicated(['user_id','date']).any()
    a=u[[f'active_{d}' for d in DATES]].to_numpy(int)
    assert np.isin(a,[0,1]).all()
    np.testing.assert_array_equal(source.pivot(index='user_id',columns='date',values='active').loc[u.user_id,DATES].to_numpy(),a)
    dates=np.array(DATES,dtype='datetime64[D]').astype(int)
    last0=pd.to_datetime(u.last_active).to_numpy(dtype='datetime64[D]').astype(int)
    last=last0.copy();before=np.empty_like(a);latest_before=np.empty_like(a)
    for j,num in enumerate(dates):
        latest_before[:,j]=last;before[:,j]=num-1-last
        assert np.all(before[:,j]>=0)
        check=panel[panel.date.eq(DATES[j])].set_index('user_id').loc[u.user_id]
        np.testing.assert_array_equal(check.inactive_days_before_date.to_numpy(),before[:,j])
        last=np.where(a[:,j],num,last)
    days=a.sum(axis=1);first=np.where(days>0,a.argmax(axis=1),-1)
    assert np.array_equal(days,u.followup_active_days.to_numpy())
    segments=u.segment.to_numpy();flows=[];returnrows=[];patterns=[]
    old=pd.read_csv(ROOT/'first_return_cohorts.csv').set_index(['segment','first_return_date'])
    for s in SEGS:
        mask=np.ones(len(u),bool) if s=='전체' else segments==s;n=int(mask.sum())
        r=dict(segment=s,baseline_users=n,no_learning_users=int((mask&(days==0)).sum()),one_learning_day_users=int((mask&(days==1)).sum()),two_plus_learning_days_users=int((mask&(days>=2)).sum()))
        r['returned_users']=r['one_learning_day_users']+r['two_plus_learning_days_users']
        for state in ['no_learning','one_learning_day','two_plus_learning_days']:r[state+'_share']=r[state+'_users']/n
        flows.append(r)
        for j,date in enumerate(DATES):
            ids=mask&(first==j);cnt=int(ids.sum());observed=j<=1
            d1=int(a[ids,j+1].sum()) if j<3 else None
            d2=int(a[ids,j+2].sum()) if observed else None
            k=int((a[ids,j+1:j+3].sum(axis=1)>0).sum()) if observed else None
            lo,hi=wilson(k,cnt) if observed else (None,None)
            row=dict(segment=s,first_learning_date=date,users=cnt,d1_observed=j<3,d2_observed=observed,d1_users=d1,d2_users=d2,within2_observed=observed,within2_users=k,within2_rate=k/cnt if observed and cnt else None,ci95_low=lo,ci95_high=hi)
            returnrows.append(row)
            prev=old.loc[(s,date)];assert cnt==prev.return_cohort_users
            if observed:assert k==prev.within_2days_repeat_users
            if observed:
                for code in ['00','10','01','11']:
                    q=ids&(a[:,j+1]==int(code[0]))&(a[:,j+2]==int(code[1]))
                    patterns.append(dict(segment=s,first_learning_date=date,pattern=code,users=int(q.sum()),cohort_users=cnt,share=int(q.sum())/cnt if cnt else None))
    # Candidate membership is generated chronologically, without outcome columns.
    baseline_cols=['user_id','segment','segment_asof_utc','active_days','recency','words_seen','sessions','last_active']
    candidates=[];usedA=np.zeros(len(u),bool);usedB=np.zeros(len(u),bool)
    cumulative=np.zeros(len(u),int)
    for j,date in enumerate(DATES):
        for candidate,ids in [('A',(segments=='습관 형성형')&~usedA&(a[:,j]==1)),('B',(segments=='습관 형성형')&~usedB&(before[:,j]==2))]:
            part=u.loc[ids,baseline_cols].copy()
            part['candidate']=candidate;part['eligibility_date_utc']=date
            part['trigger_rule']='첫 후속 학습 기록' if candidate=='A' else 'UTC 00:00, 직전 두 날짜 학습 기록 없음'
            part['trigger_time_resolution']='UTC 날짜; 첫 기록 timestamp 미추출' if candidate=='A' else 'UTC 00:00:00'
            part['snapshot_max_completed_date_utc']=str(np.datetime64(date,'D')-np.timedelta64(1,'D'))
            part['last_learning_date_before_trigger']=pd.to_datetime(latest_before[ids,j],unit='D').strftime('%Y-%m-%d')
            part['inactive_completed_dates_before_trigger']=before[ids,j]
            part['followup_active_days_before_trigger']=cumulative[ids]
            part['candidate_scope']=np.where(before[ids,j]>=1,'A1_재개후연결','A0_연속후속학습') if candidate=='A' else 'B_2일비활동복귀'
            part['primary_target']=(before[ids,j]>=1) if candidate=='A' else False
            part['candidate_id']=candidate+'|'+part.user_id
            candidates.append(part)
            if candidate=='A':usedA|=ids
            else:usedB|=ids
        cumulative+=a[:,j]
    c=pd.concat(candidates,ignore_index=True)
    assert not c.duplicated(['candidate','user_id']).any()
    # Outcomes do not enter the eligibility table; A uses D1/D2, B uses D0/D1.
    ix=pd.Series(np.arange(len(u)),index=u.user_id)
    outcome=[]
    for row in c.itertuples(index=False):
        i=int(ix[row.user_id]);j=DATES.index(row.eligibility_date_utc)
        start=j+1 if row.candidate=='A' else j;end=start+1;obs=end<4
        outcome.append(dict(candidate_id=row.candidate_id,user_id=row.user_id,candidate=row.candidate,eligibility_date_utc=row.eligibility_date_utc,
          outcome_start_utc=str(np.datetime64(DATES[j])+np.timedelta64(start-j,'D')),outcome_end_utc=str(np.datetime64(DATES[j])+np.timedelta64(end-j,'D')),
          fully_observed=obs,any_learning=int(a[i,start:end+1].any()) if obs else None,
          first_outcome_date_active=int(a[i,start]) if start<4 else None,
          second_outcome_date_active=int(a[i,end]) if obs else None,
          trigger_gap=row.inactive_completed_dates_before_trigger))
    o=pd.DataFrame(outcome);summ=[]
    def summarize(candidate,date,q,scope):
        obs=q[q.fully_observed];n=len(obs);k=int(obs.any_learning.sum()) if n else None;lo,hi=wilson(k,n)
        return dict(candidate=candidate,scope=scope,eligibility_date_utc=date,eligible_users=len(q),fully_observed_users=n,unobserved_users=len(q)-n,learning_users=k,rate=k/n if n else None,ci95_low=lo,ci95_high=hi)
    for cand in ['A','B']:
        q=o[o.candidate.eq(cand)]
        for date in DATES:summ.append(summarize(cand,date,q[q.eligibility_date_utc.eq(date)],'전체 해당 대상'))
        summ.append(summarize(cand,'합계',q,'전체 해당 대상'))
        if cand=='A':
            for label,sub in [('직전 비활동 0일',q[q.trigger_gap.eq(0)]),('직전 비활동 1일 이상',q[q.trigger_gap.ge(1)])]:
                summ.append(summarize(cand,'합계',sub,label))
    overlap=dict(both_candidates=int(len(set(c[c.candidate.eq('A')].user_id)&set(c[c.candidate.eq('B')].user_id))),A_users=int(usedA.sum()),B_users=int(usedB.sum()))
    pooled=[]
    rr=pd.DataFrame(returnrows);pf=pd.DataFrame(patterns)
    for s in SEGS:
        q=rr[rr.segment.eq(s)&rr.within2_observed];n=int(q.users.sum());k=int(q.within2_users.sum());lo,hi=wilson(k,n)
        p=dict(segment=s,eligible_returners=n,within2_users=k,within2_rate=k/n if n else None,ci95_low=lo,ci95_high=hi)
        for code in ['00','10','01','11']:p['pattern_'+code+'_users']=int(pf[pf.segment.eq(s)&pf.pattern.eq(code)].users.sum())
        assert sum(p['pattern_'+code+'_users'] for code in ['00','10','01','11'])==n
        pooled.append(p)
    assert len(c[c.candidate.eq('A')])==int(((segments=='습관 형성형')&(days>0)).sum())
    aobs=next(r for r in summ if r['candidate']=='A' and r['scope']=='전체 해당 대상' and r['eligibility_date_utc']=='합계')
    assert aobs['fully_observed_users']==5679 and aobs['learning_users']==2704
    checks=dict(source_hashes_match=True,source_panel_matches=True,chronological_gaps_match=True,baseline_flow_partitions=True,first_learning_matches_existing=True,candidates_unique_within_type=True,A_existing_denominator_reconciled=True,outcomes_separate_from_eligibility=True,late_followup_missing_preserved=True)
    frames={'baseline_behavior_flow.csv':pd.DataFrame(flows),'first_learning_followup.csv':rr,'aligned_behavior_patterns.csv':pf,'aligned_behavior_summary.csv':pd.DataFrame(pooled),'candidate_eligibility.csv':c,'candidate_outcomes.csv':o,'candidate_summary.csv':pd.DataFrame(summ)}
    frames['primary_candidate_eligibility.csv']=c[c.primary_target].copy()
    frames['primary_candidate_outcomes.csv']=o[o.candidate_id.isin(frames['primary_candidate_eligibility.csv'].candidate_id)].copy()
    for name,f in frames.items():f.to_csv(OUT/name,index=False,encoding='utf-8-sig')
    result=dict(analysis_date='2026-10-13',baseline='2013-03-01..07 UTC',followup='2013-03-08..11 UTC',source_hashes=hashes,checks=checks,flow=flows,first_learning=clean(rr),aligned=pooled,candidates=summ,overlap=overlap)
    (OUT/'behavior_flow_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(flow=flows[0],habit_flow=flows[2],habit_aligned=pooled[2],candidates=summ,overlap=overlap),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
