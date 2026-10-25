from pathlib import Path
from collections import defaultdict
import json,math,sys,hashlib
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'word_performance'
sys.path.insert(0,str(ROOT/'tmp'/'python_deps'))
from scipy.optimize import minimize
from analyze_word_performance import user_design,pair_design
d=json.loads((OUT/'word_performance_results.json').read_text(encoding='utf-8'))
m=pd.read_csv(OUT/'user_word_improvement.csv');p=pd.read_csv(OUT/'matched_word_pairs.csv');review=pd.read_csv(OUT/'review_word_pairs.csv');sample=pd.read_csv(OUT/'validation_sample_rows.csv')
assert m.user_id.is_unique and len(m)==82467
sample_users=set(sample.user_id)
checked=0
for mode,frame in [('all',p),('review',review)]:
 records=defaultdict(list)
 for r in sample.itertuples():
  if mode=='review' and r.delta<60:continue
  records[(r.user_id,r.learning_language,r.lexeme_id)].append(r)
 expected={}
 for key,rs in records.items():
  days=sorted({r.day for r in rs})
  if len(days)<2:continue
  aa=[r for r in rs if r.day==days[0]];bb=[r for r in rs if r.day==days[-1]]
  first=sum(r.session_correct for r in aa)/sum(r.session_seen for r in aa);last=sum(r.session_correct for r in bb)/sum(r.session_seen for r in bb)
  initial=min(rs,key=lambda r:r.timestamp)
  val={'improvement':last-first,'first_seen':sum(r.session_seen for r in aa),'last_seen':sum(r.session_seen for r in bb),'prior_accuracy':initial.history_correct/initial.history_seen}
  if mode=='review':
   val['change_loggap']=sum(math.log2(r.delta/3600)*r.session_seen for r in bb)/val['last_seen']-sum(math.log2(r.delta/3600)*r.session_seen for r in aa)/val['first_seen']
  expected[key]=val
 got=frame[frame.user_id.isin(sample_users)]
 assert len(got)==len(expected)
 for r in got.itertuples():
  for k,v in expected[(r.user_id,r.learning_language,r.lexeme_id)].items():assert math.isclose(getattr(r,k),v,rel_tol=1e-10,abs_tol=1e-12),(mode,k)
  checked+=1
 if mode=='all':
  for uid,rs in got.groupby('user_id'):
   vals=[expected[(r.user_id,r.learning_language,r.lexeme_id)] for r in rs.itertuples()]
   improvement=sum(v['improvement']*v['last_seen'] for v in vals)/sum(v['last_seen'] for v in vals)
   saved=m[m.user_id==uid].iloc[0]
   assert saved.matched_words==len(vals) and math.isclose(improvement,saved.improvement,abs_tol=1e-12)
assert m.loc[m.matched_words.eq(0),'improvement'].isna().all()
assert np.allclose(m.loc[m.matched_words.gt(0),'final_accuracy']-m.loc[m.matched_words.gt(0),'initial_accuracy'],m.loc[m.matched_words.gt(0),'improvement'],atol=1e-12)
valid=m[m.model_eligible];h=valid[valid.segment=='습관 형성형'];groups=[h,valid,h[h.eligible_10],h];errors=[]
for g,r in zip(groups,d['models'][:4]):
 X,names=user_design(g);y=g[r['outcome']].to_numpy()
 def fun(b):return float(np.sum(np.logaddexp(0,X@b)-y*(X@b)))
 def jac(b):return X.T@(1/(1+np.exp(-X@b))-y)
 opt=minimize(fun,np.zeros(X.shape[1]),jac=jac,method='BFGS',options={'gtol':1e-7,'maxiter':1000})
 b=np.array([c['beta'] for c in r['coefficients']]);err=float(np.max(np.abs(b-opt.x)))
 assert err<1e-5 and np.max(np.abs(jac(opt.x)))<1e-4,(r['model'],err,opt.message)
 assert len(g)==r['n'] and int(y.sum())==r['events'];errors.append(err)
review=review[review.prior_accuracy.notna()];counts=review.groupby('user_id').size();g=review[review.user_id.isin(counts[counts>=5].index)]
X,names=pair_design(g);y=g.improvement.to_numpy();pair_errors=[];se_errors=[]
for r in d['models'][4:]:
 w=g.last_seen.to_numpy(dtype=float) if r['weighted'] else np.ones(len(g));w=w/w.mean();sw=np.sqrt(w)
 b=np.linalg.lstsq(X*sw[:,None],y*sw,rcond=None)[0]
 err=float(np.max(np.abs(b-np.array([c['beta'] for c in r['coefficients']]))));assert err<1e-8;pair_errors.append(err)
 scores=pd.DataFrame(X*(w*(y-X@b))[:,None]);scores['user_id']=g.user_id.to_numpy()
 sums=scores.groupby('user_id').sum().to_numpy();G=len(sums);N=len(g);P=X.shape[1]
 bread=np.linalg.inv(X.T@(w[:,None]*X));cov=bread@(sums.T@sums)@bread*(G/(G-1))*((N-1)/(N-P))
 se=np.sqrt(np.diag(cov));err=float(np.max(np.abs(se-np.array([c['se'] for c in r['coefficients']]))));assert err<1e-9;se_errors.append(err)
 assert G==r['users'] and N==r['n']
for r in d['coverage']:assert r['baseline_users']==r['no_matched_words']+r['one_to_four_words']+r['eligible_users']
assert all(d['checks'].values())
assert hashlib.sha256((ROOT/'user_retention_cohort.csv').read_bytes()).hexdigest()==d['source_hashes']['user_retention_cohort.csv']
result={'sample_users':len(sample_users),'independent_pair_rows':checked,'user_formula_reconciled':True,'missing_scores_preserved':True,'logistic_models_BFGS':4,'logistic_max_error':max(errors),'paired_models_SVD':2,'paired_coefficient_max_error':max(pair_errors),'cluster_se_max_error':max(se_errors),'coverage_reconciled':True,'source_cohort_unchanged':True}
(OUT/'analysis_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
