"""Fixed calendar-window accuracy change and subsequent user-level learning."""
from pathlib import Path
import hashlib,json,math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'accuracy_change'
RAW=ROOT.parent/'learning_traces.13m.csv'/'learning_traces.13m.csv'
START=int(pd.Timestamp('2013-03-01',tz='UTC').timestamp()); END=START+7*86400

def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''): h.update(b)
    return h.hexdigest()

def design(g,adjusted,categorical=False):
    cols={'intercept':np.ones(len(g))}
    if categorical:
        cols['decline_vs_stable']=(g.change_group.to_numpy()=='5%p 초과 하락').astype(float)
        cols['rise_vs_stable']=(g.change_group.to_numpy()=='5%p 초과 상승').astype(float)
    else:cols['change_per_10pp']=g.change.to_numpy()/.1
    if adjusted:
        a=g.early_accuracy.to_numpy(); cols['early_accuracy_centered']=a-a.mean();cols['early_accuracy_squared']=(a-a.mean())**2
        for col in ['active_days','recency']:
            for level in sorted(g[col].unique())[1:]: cols[f'{col}_{level}']=(g[col].to_numpy()==level).astype(float)
        for col in ['early_seen','late_seen','sessions']:
            a=np.log1p(g[col].to_numpy());cols['log1p_'+col]=(a-a.mean())/a.std()
        a=pd.to_datetime(g.first_active).astype('int64').to_numpy()/86400/1e9
        if a.std()>0:cols['first_observed_day']=(a-a.mean())/a.std()
    return np.column_stack(list(cols.values())),list(cols)

def fit(g,label,outcome='returned_2plus_days',adjusted=True,categorical=False,term_index=1):
    X,names=design(g,adjusted,categorical);y=g[outcome].to_numpy(dtype=float)
    assert np.linalg.matrix_rank(X)==X.shape[1]
    b=np.zeros(X.shape[1])
    for it in range(100):
        p=1/(1+np.exp(-np.clip(X@b,-35,35)));w=p*(1-p)
        step=np.linalg.solve(X.T@(w[:,None]*X),X.T@(y-p));b+=step
        if np.max(np.abs(step))<1e-9:break
    assert it<99
    p=1/(1+np.exp(-np.clip(X@b,-35,35)));w=p*(1-p)
    bread=np.linalg.inv(X.T@(w[:,None]*X));score=X*(y-p)[:,None]
    cov=bread@(score.T@score)@bread*len(g)/(len(g)-X.shape[1]);se=np.sqrt(np.diag(cov))
    assert np.max(np.abs(X.T@(y-p)))<1e-5
    j=term_index
    return dict(model=label,outcome=outcome,adjusted=adjusted,categorical=categorical,term=names[j],n=len(g),events=int(y.sum()),odds_ratio=float(np.exp(b[j])),ci_low=float(np.exp(b[j]-1.95996398454*se[j])),ci_high=float(np.exp(b[j]+1.95996398454*se[j])),p=math.erfc(abs(b[j]/se[j])/math.sqrt(2)),condition_number=float(np.linalg.cond(X)),iterations=it+1,coefficients=[dict(term=n,beta=float(v),robust_se=float(s)) for n,v,s in zip(names,b,se)])

def main():
    OUT.mkdir(exist_ok=True)
    u=pd.read_csv(ROOT/'user_retention_cohort.csv',low_memory=False)
    daily_path=OUT/'baseline_daily_accuracy.csv'
    raw_hash=sha(RAW)
    prior_regular=json.loads((ROOT/'regularity'/'regularity_results.json').read_text(encoding='utf-8'))
    assert raw_hash==prior_regular['source_hashes']['raw_csv']
    if daily_path.exists():
        daily=pd.read_csv(daily_path)
        extraction=json.loads((OUT/'extraction.json').read_text(encoding='utf-8'))
        assert extraction['raw_sha256']==raw_hash and extraction['daily_sha256']==sha(daily_path)
    else:
        parts=[];read=0
        for c in pd.read_csv(RAW,chunksize=750000,dtype={'user_id':'str','learning_language':'str','ui_language':'str','lexeme_id':'str','lexeme_string':'str'}):
            read+=len(c); c=c[(c.timestamp>=START)&(c.timestamp<END)].copy()
            c['row_hash']=pd.util.hash_pandas_object(c,index=False)
            parts.append(c[['user_id','timestamp','session_seen','session_correct','row_hash']])
            print(f'read {read:,}',flush=True)
        baseline=pd.concat(parts,ignore_index=True);before=len(baseline)
        baseline=baseline.drop_duplicates('row_hash');removed=before-len(baseline)
        assert (baseline.session_seen>0).all() and (baseline.session_correct.between(0,baseline.session_seen)).all()
        baseline['day']=((baseline.timestamp-START)//86400+1).astype(int)
        daily=baseline.groupby(['user_id','day'],as_index=False).agg(seen=('session_seen','sum'),correct=('session_correct','sum'),sessions=('timestamp','nunique'))
        daily.to_csv(daily_path,index=False)
        extraction=dict(raw_rows=read,baseline_rows_before_dedup=before,baseline_duplicates_removed=removed,raw_sha256=raw_hash,daily_sha256=sha(daily_path),dedup='64-bit full-row pandas hash; existing user totals crosschecked')
        (OUT/'extraction.json').write_text(json.dumps(extraction,ensure_ascii=False,indent=2),encoding='utf-8')
    total=daily.groupby('user_id').agg(words_seen=('seen','sum'),words_correct=('correct','sum'),sessions=('sessions','sum'),active_days=('day','size')).reindex(u.user_id)
    for col in total.columns:np.testing.assert_array_equal(total[col],u[col])
    for name,mask in [('early',daily.day<=3),('late',daily.day>=5)]:
        part=daily[mask].groupby('user_id').agg(**{name+'_seen':('seen','sum'),name+'_correct':('correct','sum'),name+'_days':('day','size')})
        u=u.merge(part,on='user_id',how='left',validate='one_to_one')
        for col in part.columns:u[col]=u[col].fillna(0).astype(int)
        u[name+'_accuracy']=u[name+'_correct']/u[name+'_seen'].replace(0,np.nan)
    u['change']=u.late_accuracy-u.early_accuracy
    u['eligible']=(u.early_seen>=20)&(u.late_seen>=20)
    u['eligibility_reason']=np.select([(u.early_seen==0)|(u.late_seen==0),~u.eligible],['한쪽 기간 기록 없음','한쪽 기간 20문항 미만'],default='포함')
    # Exact integer cross-products avoid floating-point mistakes at +/-5pp.
    numerator=20*(u.late_correct*u.early_seen-u.early_correct*u.late_seen)
    denominator=u.early_seen*u.late_seen
    u['change_group']=np.select([~u.eligible,numerator < -denominator,numerator > denominator],['분석 제외','5%p 초과 하락','5%p 초과 상승'],default='±5%p 이내')
    keep=['user_id','segment','first_active','active_days','recency','sessions','words_seen','early_seen','early_correct','early_days','early_accuracy','late_seen','late_correct','late_days','late_accuracy','change','eligible','eligibility_reason','change_group','returned_4d','returned_2plus_days']
    u[keep].to_csv(OUT/'user_accuracy_change.csv',index=False)
    coverage=[];desc=[]
    for seg,g in [('전체',u)]+list(u.groupby('segment',sort=False)):
        valid=g[g.eligible]
        coverage.append(dict(segment=seg,baseline_users=len(g),eligible_users=len(valid),missing_window_users=int((g.eligibility_reason=='한쪽 기간 기록 없음').sum()),low_volume_users=int((g.eligibility_reason=='한쪽 기간 20문항 미만').sum()),eligible_50_users=int(((g.early_seen>=50)&(g.late_seen>=50)).sum())))
        for label in ['5%p 초과 하락','±5%p 이내','5%p 초과 상승']:
            s=valid[valid.change_group==label]
            desc.append(dict(segment=seg,change_group=label,n=len(s),returned=int(s.returned_4d.sum()),repeated=int(s.returned_2plus_days.sum()),return_rate=float(s.returned_4d.mean()) if len(s) else None,repeat_rate=float(s.returned_2plus_days.mean()) if len(s) else None,early_accuracy_mean=float(s.early_accuracy.mean()) if len(s) else None,late_accuracy_mean=float(s.late_accuracy.mean()) if len(s) else None,early_seen_median=float(s.early_seen.median()) if len(s) else None,late_seen_median=float(s.late_seen.median()) if len(s) else None))
    valid=u[u.eligible];habit=valid[valid.segment=='습관 형성형'];strict=habit[(habit.early_seen>=50)&(habit.late_seen>=50)]
    models=[fit(habit,'습관 형성형 · 반복학습 · 미보정',adjusted=False),fit(habit,'습관 형성형 · 반복학습 · 보정'),fit(valid,'전체 분석 가능자 · 반복학습 · 보정'),fit(habit,'습관 형성형 · 재학습 · 보정','returned_4d'),fit(strict,'습관 형성형 · 양쪽 50문항 · 반복학습 보정')]
    models.extend([fit(habit,'습관 형성형 · 하락 vs 유지 · 반복학습',categorical=True),fit(habit,'습관 형성형 · 상승 vs 유지 · 반복학습',categorical=True,term_index=2)])
    adjusted=models[1:];running=0
    for rank,i in enumerate(sorted(range(len(adjusted)),key=lambda i:adjusted[i]['p'])):
        running=max(running,adjusted[i]['p']*(len(adjusted)-rank));adjusted[i]['p_holm']=min(1.,running)
    pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False)
    pd.DataFrame(desc).to_csv(OUT/'change_groups.csv',index=False)
    pd.DataFrame([{k:v for k,v in r.items() if k!='coefficients'} for r in models]).to_csv(OUT/'adjusted_models.csv',index=False)
    result=dict(analysis_date='2026-10-13',early_window='2013-03-01..03 UTC',late_window='2013-03-05..07 UTC',followup='2013-03-08..11 UTC',excluded_middle_day='2013-03-04',minimum_attempts_each_window=20,coverage=coverage,groups=desc,models=models,extraction=extraction,source_hashes={'raw_csv':raw_hash,'user_retention_cohort.csv':sha(ROOT/'user_retention_cohort.csv'),'baseline_daily_accuracy.csv':sha(daily_path)},checks={'all_user_words_seen_match':True,'all_user_words_correct_match':True,'all_user_sessions_match':True,'all_user_active_days_match':True,'baseline_only':True,'models_full_rank_converged':True,'model_score_near_zero':True})
    (OUT/'accuracy_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'coverage':coverage,'models':[{k:v for k,v in r.items() if k!='coefficients'} for r in models],'habit_groups':[r for r in desc if r['segment']=='습관 형성형']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
