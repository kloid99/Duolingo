from pathlib import Path
import json, sys, statistics, math, hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parent/'tmp'/'python_deps'))
from scipy.optimize import minimize

d=json.loads((ROOT/'regularity_results.json').read_text(encoding='utf-8'))
m=pd.read_csv(ROOT/'user_regularity.csv')
t=pd.read_csv(ROOT/'baseline_unique_timestamps.csv')
assert len(m)==2*82467 and not m.duplicated(['user_id','definition']).any()
assert np.isfinite(m.loc[m.eligible,'cv']).all()
assert (m.loc[m.n_gaps<2,'cv'].isna()).all()
sample=m.user_id.drop_duplicates().sample(150,random_state=20261013)
for uid, g in t[t.user_id.isin(sample)].groupby('user_id'):
    ts=sorted(set(g.timestamp))
    for definition in ['timestamp','30min']:
        starts=ts if definition=='timestamp' else [v for i,v in enumerate(ts) if i==0 or v-ts[i-1]>1800]
        gaps=[(b-a)/3600 for a,b in zip(starts,starts[1:])]
        r=m[(m.user_id==uid)&(m.definition==definition)].iloc[0]
        assert r.n_sessions==len(starts)
        if len(gaps)>=2:
            assert math.isclose(r.cv,statistics.stdev(gaps)/statistics.mean(gaps),rel_tol=1e-10)
h=m[(m.segment=='습관 형성형')&m.eligible]
p=h[h.definition=='timestamp']; merged=h[h.definition=='30min']
groups=[p,p,p[p.n_sessions>=6],merged,p[p.user_id.isin(merged.user_id)]]
max_error=0
for g,r in zip(groups,d['models']):
    z=np.log1p(g.cv.to_numpy()); cols={'intercept':np.ones(len(g)),'log1p_cv_per_sd':(z-z.mean())/z.std()}
    if r['adjusted']:
        for col in ['active_days','recency']:
            for level in sorted(g[col].unique())[1:]: cols[f'{col}_{level}']=(g[col].to_numpy()==level).astype(float)
        for col in ['words_seen','n_sessions']:
            a=np.log1p(g[col].to_numpy()); cols['log1p_'+col]=(a-a.mean())/a.std()
        a=g.first_hour.to_numpy(); cols['first_hour']=(a-a.mean())/a.std()
    X=np.column_stack([cols[c['term']] for c in r['coefficients']]); y=g.returned_2plus_days.to_numpy()
    def fun(b): return float(np.sum(np.logaddexp(0,X@b)-y*(X@b)))
    def jac(b): return X.T@(1/(1+np.exp(-X@b))-y)
    opt=minimize(fun,np.zeros(X.shape[1]),jac=jac,method='BFGS',options={'gtol':1e-7,'maxiter':1000})
    expected=np.array([c['beta'] for c in r['coefficients']])
    error=float(np.max(np.abs(opt.x-expected))); max_error=max(max_error,error)
    assert error<1e-5 and np.max(np.abs(jac(opt.x)))<1e-4,(r['model'],error,opt.message)
    assert len(g)==r['n'] and int(y.sum())==r['events']
assert sum(r['users'] for r in d['quartiles'])==10633
assert sum(r['repeat_users'] for r in d['quartiles'])==2887
assert all(d['checks'].values())
assert hashlib.sha256((ROOT.parent/'user_retention_cohort.csv').read_bytes()).hexdigest()==d['source_hashes']['user_retention_cohort.csv']
result={'sampled_users_interval_reconstruction':150,'sampled_metric_rows':300,'independent_BFGS_models':5,'max_coefficient_difference':max_error,'missing_cv_preserved':True,'source_cohort_unchanged':True,'quartiles_reconciled':True}
(ROOT/'analysis_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
