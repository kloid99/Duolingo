"""Baseline-only interval variability; exploratory user-level logistic models."""
from pathlib import Path
import json, hashlib, math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'regularity'
RAW=ROOT.parent/'learning_traces.13m.csv'/'learning_traces.13m.csv'
START=int(pd.Timestamp('2013-03-01',tz='UTC').timestamp())
END=int(pd.Timestamp('2013-03-08',tz='UTC').timestamp())

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def fit(g,label,adjusted=True):
    z=np.log1p(g.cv.to_numpy()); sd=float(z.std())
    x=[np.ones(len(g)),(z-z.mean())/sd]; names=['intercept','log1p_cv_per_sd']
    if adjusted:
        for col in ['active_days','recency']:
            for level in sorted(g[col].unique())[1:]:
                x.append((g[col].to_numpy()==level).astype(float)); names.append(f'{col}_{level}')
        for col in ['words_seen','n_sessions']:
            a=np.log1p(g[col].to_numpy()); x.append((a-a.mean())/a.std()); names.append('log1p_'+col)
        a=g.first_hour.to_numpy(); x.append((a-a.mean())/a.std()); names.append('first_hour')
    X=np.column_stack(x); y=g.returned_2plus_days.to_numpy(dtype=float)
    assert np.linalg.matrix_rank(X)==X.shape[1]
    b=np.zeros(X.shape[1])
    for iteration in range(100):
        p=1/(1+np.exp(-np.clip(X@b,-35,35))); w=p*(1-p)
        step=np.linalg.solve(X.T@(w[:,None]*X),X.T@(y-p)); b+=step
        if np.max(np.abs(step))<1e-9: break
    assert iteration<99
    p=1/(1+np.exp(-np.clip(X@b,-35,35))); w=p*(1-p)
    bread=np.linalg.inv(X.T@(w[:,None]*X)); score=X*(y-p)[:,None]
    cov=bread@(score.T@score)@bread*len(g)/(len(g)-X.shape[1])
    se=np.sqrt(np.diag(cov)); beta=float(b[1]); stderr=float(se[1])
    pv=math.erfc(abs(beta/stderr)/math.sqrt(2))
    assert np.max(np.abs(X.T@(y-p)))<1e-5
    q25,q75=np.quantile(z,[.25,.75])
    # Do not assign a common CV to every user: feasible CV depends on gap count.
    return dict(model=label,n=len(g),events=int(y.sum()),adjusted=adjusted,odds_ratio=math.exp(beta),ci_low=math.exp(beta-1.95996398454*stderr),ci_high=math.exp(beta+1.95996398454*stderr),p=pv,logcv_sd=sd,cv_q25=math.expm1(q25),cv_q75=math.expm1(q75),iterations=iteration+1,condition_number=float(np.linalg.cond(X)),coefficients=[dict(term=n,beta=float(v),robust_se=float(s)) for n,v,s in zip(names,b,se)])

def main():
    OUT.mkdir(exist_ok=True)
    u=pd.read_csv(ROOT/'user_retention_cohort.csv',low_memory=False)
    cache=OUT/'baseline_unique_timestamps.csv'
    previous=OUT/'regularity_results.json'
    raw_hash=sha(RAW)
    if cache.exists() and previous.exists():
        old=json.loads(previous.read_text(encoding='utf-8'))
        assert raw_hash==old['source_hashes']['raw_csv'], 'Raw source changed; use a new analysis output folder.'
        assert sha(cache)==old['source_hashes']['baseline_unique_timestamps.csv'], 'Timestamp cache changed.'
    if not cache.exists():
        parts=[]; rows=0
        for c in pd.read_csv(RAW,usecols=['user_id','timestamp'],chunksize=1000000):
            rows+=len(c); c=c[(c.timestamp>=START)&(c.timestamp<END)]
            parts.append(c.drop_duplicates())
            print(f'read {rows:,} rows',flush=True)
        t=pd.concat(parts).drop_duplicates().sort_values(['user_id','timestamp'])
        t.to_csv(cache,index=False)
    else: t=pd.read_csv(cache).sort_values(['user_id','timestamp'])
    assert not t.duplicated().any() and t.timestamp.between(START,END-1).all()
    t['day']=t.timestamp//86400
    agg=t.groupby('user_id').agg(sessions=('timestamp','size'),active_days=('day','nunique'),first=('timestamp','min'),last=('timestamp','max')).reindex(u.user_id)
    assert agg.notna().all().all() and len(agg)==82467
    for c in ['sessions','active_days']: np.testing.assert_array_equal(agg[c],u[c])
    np.testing.assert_array_equal(pd.to_datetime(agg['first'],unit='s').dt.strftime('%Y-%m-%d'),u.first_active)
    np.testing.assert_array_equal(pd.to_datetime(agg['last'],unit='s').dt.strftime('%Y-%m-%d'),u.last_active)
    records=[]
    for uid,g in t.groupby('user_id',sort=False):
        ts=g.timestamp.to_numpy()
        for definition in ['timestamp','30min']:
            starts=ts if definition=='timestamp' else ts[np.r_[True,np.diff(ts)>1800]]
            gaps=np.diff(starts)/3600
            records.append(dict(user_id=uid,definition=definition,n_sessions=len(starts),n_gaps=len(gaps),first_hour=(starts[0]-START)/3600,last_hour=(starts[-1]-START)/3600,mean_gap_hours=float(gaps.mean()) if len(gaps) else np.nan,cv=float(gaps.std(ddof=1)/gaps.mean()) if len(gaps)>=2 else np.nan))
    m=pd.DataFrame(records).merge(u[['user_id','segment','active_days','words_seen','recency','returned_2plus_days']],on='user_id',validate='many_to_one')
    m['eligible']=(m.n_sessions>=4)&(m.active_days>=2)
    m.to_csv(OUT/'user_regularity.csv',index=False)
    coverage=m.groupby(['definition','segment']).agg(users=('user_id','size'),eligible_users=('eligible','sum')).reset_index()
    coverage['excluded_users']=coverage.users-coverage.eligible_users
    coverage.to_csv(OUT/'coverage.csv',index=False)
    habit=m[(m.segment=='습관 형성형')&m.eligible].copy()
    primary=habit[habit.definition=='timestamp'].copy()
    primary['cv_group']=pd.qcut(primary.cv,4,labels=['Q1 낮은 변동','Q2','Q3','Q4 높은 변동'])
    descriptive=primary.groupby('cv_group',observed=True).agg(users=('user_id','size'),repeat_users=('returned_2plus_days','sum'),cv_min=('cv','min'),cv_max=('cv','max'),active_days_mean=('active_days','mean'),words_median=('words_seen','median'),sessions_median=('n_sessions','median')).reset_index()
    descriptive['repeat_rate']=descriptive.repeat_users/descriptive.users
    descriptive.to_csv(OUT/'habit_quartiles.csv',index=False)
    merged=habit[habit.definition=='30min']
    models=[fit(primary,'고유 시각 4회 이상 · 미보정',False),fit(primary,'고유 시각 4회 이상 · 보정'),fit(primary[primary.n_sessions>=6],'고유 시각 6회 이상 · 보정'),fit(merged,'30분 세션 4회 이상 · 보정'),fit(primary[primary.user_id.isin(merged.user_id)],'30분 세션 대상과 동일인 · 고유 시각 보정')]
    adjusted=models[1:]; order=sorted(range(len(adjusted)),key=lambda i:adjusted[i]['p']); running=0
    for rank,i in enumerate(order):
        running=max(running,adjusted[i]['p']*(len(adjusted)-rank)); adjusted[i]['p_holm']=min(1.,running)
    primary['volume_tertile']=pd.qcut(primary.words_seen,3,labels=False)
    strata=[]
    for key,g in primary.groupby(['active_days','recency','n_sessions','volume_tertile']):
        low=g[g.cv<=g.cv.median()]; high=g[g.cv>g.cv.median()]
        if min(len(low),len(high))<10: continue
        strata.append(dict(active_days=int(key[0]),recency=int(key[1]),n_sessions=int(key[2]),volume_tertile=int(key[3]),low_n=len(low),high_n=len(high),low_events=int(low.returned_2plus_days.sum()),high_events=int(high.returned_2plus_days.sum()),low_rate=float(low.returned_2plus_days.mean()),high_rate=float(high.returned_2plus_days.mean())))
    st=pd.DataFrame(strata); st.to_csv(OUT/'within_strata_comparison.csv',index=False)
    weights=(st.low_n+st.high_n)/(st.low_n+st.high_n).sum()
    stratified=dict(strata=len(st),users=int((st.low_n+st.high_n).sum()),low_rate=float((weights*st.low_rate).sum()),high_rate=float((weights*st.high_rate).sum()),difference_pp=float((weights*(st.high_rate-st.low_rate)).sum()*100))
    pd.DataFrame([{k:v for k,v in r.items() if k!='coefficients'} for r in models]).to_csv(OUT/'adjusted_models.csv',index=False)
    result=dict(baseline='2013-03-01..07 UTC',followup='2013-03-08..11 UTC',outcome='4일 중 2일 이상 학습',metric='간격의 표본 표준편차 / 평균; 낮을수록 간격 변동이 작음',source_hashes={'user_retention_cohort.csv':sha(ROOT/'user_retention_cohort.csv'),'baseline_unique_timestamps.csv':sha(cache)},coverage=coverage.to_dict('records'),quartiles=descriptive.to_dict('records'),models=models,checks={'unique_timestamps':True,'baseline_only':True,'baseline_user_count':True,'session_counts_match':True,'active_days_match':True,'first_last_dates_match':True,'all_models_full_rank_and_converged':True,'model_score_near_zero':True})
    result['within_strata']=stratified
    result['source_hashes']['raw_csv']=raw_hash
    (OUT/'regularity_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'models':[{k:v for k,v in r.items() if k!='coefficients'} for r in models],'within_strata':stratified},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()
