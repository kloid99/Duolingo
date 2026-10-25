from pathlib import Path
from fractions import Fraction
import sys,json,math,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'accuracy_change'
sys.path.insert(0,str(ROOT/'tmp'/'python_deps'))
from scipy.optimize import minimize
from analyze_accuracy_change import design
d=json.loads((OUT/'accuracy_results.json').read_text(encoding='utf-8'))
u=pd.read_csv(OUT/'user_accuracy_change.csv')
daily=pd.read_csv(OUT/'baseline_daily_accuracy.csv')
assert u.user_id.is_unique and len(u)==82467
assert not daily.duplicated(['user_id','day']).any() and daily.day.between(1,7).all()
sample=u.user_id.sample(200,random_state=20261013)
for uid,g in daily[daily.user_id.isin(sample)].groupby('user_id'):
    r=u[u.user_id==uid].iloc[0]
    for prefix,days in [('early',{1,2,3}),('late',{5,6,7})]:
        seen=sum(row.seen for row in g.itertuples() if row.day in days)
        correct=sum(row.correct for row in g.itertuples() if row.day in days)
        assert seen==r[prefix+'_seen'] and correct==r[prefix+'_correct']
        if seen: assert math.isclose(r[prefix+'_accuracy'],correct/seen,rel_tol=1e-12)
        else: assert pd.isna(r[prefix+'_accuracy'])
assert u.loc[(u.early_seen==0)|(u.late_seen==0),'change'].isna().all()
for r in u[u.eligible].itertuples():
    change=Fraction(r.late_correct,r.late_seen)-Fraction(r.early_correct,r.early_seen)
    expected='5%p 초과 하락' if change<Fraction(-1,20) else '5%p 초과 상승' if change>Fraction(1,20) else '±5%p 이내'
    assert r.change_group==expected
valid=u[u.eligible];habit=valid[valid.segment=='습관 형성형']
groups=[habit,habit,valid,habit,habit[(habit.early_seen>=50)&(habit.late_seen>=50)],habit,habit]
errors=[]
for g,r in zip(groups,d['models']):
    X,names=design(g,r['adjusted'],r['categorical']);y=g[r['outcome']].to_numpy()
    assert names==[c['term'] for c in r['coefficients']]
    def fun(b): return float(np.sum(np.logaddexp(0,X@b)-y*(X@b)))
    def jac(b): return X.T@(1/(1+np.exp(-X@b))-y)
    opt=minimize(fun,np.zeros(X.shape[1]),jac=jac,method='BFGS',options={'gtol':1e-7,'maxiter':1000})
    expected=np.array([c['beta'] for c in r['coefficients']]);error=float(np.max(np.abs(opt.x-expected)))
    assert error<1e-5 and np.max(np.abs(jac(opt.x)))<1e-4,(r['model'],error,opt.message)
    assert len(g)==r['n'] and int(y.sum())==r['events'];errors.append(error)
for r in d['coverage']:
    assert r['baseline_users']==r['eligible_users']+r['missing_window_users']+r['low_volume_users']
    assert sum(s['n'] for s in d['groups'] if s['segment']==r['segment'])==r['eligible_users']
assert all(d['checks'].values())
assert hashlib.sha256((ROOT/'user_retention_cohort.csv').read_bytes()).hexdigest()==d['source_hashes']['user_retention_cohort.csv']
result={'unique_users':82467,'independent_window_aggregation_users':200,'missing_window_accuracy_preserved':True,'exact_fraction_category_checks':len(u[u.eligible]),'independent_BFGS_effect_rows':7,'distinct_models':6,'max_coefficient_difference':max(errors),'coverage_reconciled':True,'source_cohort_unchanged':True}
(OUT/'analysis_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
