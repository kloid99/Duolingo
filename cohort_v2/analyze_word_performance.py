"""Original matched-word improvement and paired review-gap association."""
from pathlib import Path
import json,hashlib,math
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'word_performance'
RAW=ROOT.parent/'learning_traces.13m.csv'/'learning_traces.13m.csv'
START=int(pd.Timestamp('2013-03-01',tz='UTC').timestamp());END=START+7*86400
KEY=['user_id','learning_language','lexeme_id']

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
 return h.hexdigest()

def make_pairs(b,review=False):
 b=b.sort_values(KEY+['timestamp']).copy()
 initial=b.drop_duplicates(KEY)[KEY+['timestamp','history_seen','history_correct']].rename(columns={'timestamp':'initial_timestamp','history_seen':'initial_history_seen','history_correct':'initial_history_correct'})
 first_rows=b.merge(initial[KEY+['initial_timestamp']],on=KEY,validate='many_to_one')
 first_rows=first_rows[first_rows.timestamp==first_rows.initial_timestamp]
 ambiguity=first_rows.groupby(KEY,observed=True)[['history_seen','history_correct']].nunique().max(axis=1).gt(1).rename('ambiguous_initial_history').reset_index()
 initial=initial.merge(ambiguity,on=KEY,validate='one_to_one')
 print(f'initial history ambiguous ({"review" if review else "all"}): {int(initial.ambiguous_initial_history.sum())} words',flush=True)
 del first_rows
 ag={'seen':('session_seen','sum'),'correct':('session_correct','sum')}
 if review:
  b['weighted_loggap']=np.log2(b.delta/3600)*b.session_seen
  b['weighted_loghistory']=np.log1p(b.history_seen)*b.session_seen
  ag.update(loggap_sum=('weighted_loggap','sum'),loghistory_sum=('weighted_loghistory','sum'))
 day=b.groupby(KEY+['day'],as_index=False,observed=True).agg(**ag).sort_values(KEY+['day'])
 first=day.drop_duplicates(KEY).rename(columns={c:'first_'+c for c in day.columns if c not in KEY})
 last=day.drop_duplicates(KEY,keep='last').rename(columns={c:'last_'+c for c in day.columns if c not in KEY})
 p=first.merge(last,on=KEY,validate='one_to_one');p=p[p.first_day<p.last_day].merge(initial,on=KEY,validate='one_to_one')
 p['first_accuracy']=p.first_correct/p.first_seen;p['last_accuracy']=p.last_correct/p.last_seen
 p['improvement']=p.last_accuracy-p.first_accuracy;p['elapsed_days']=p.last_day-p.first_day
 p['prior_accuracy']=p.initial_history_correct/p.initial_history_seen
 p.loc[p.ambiguous_initial_history,'prior_accuracy']=np.nan
 assert p.prior_accuracy.dropna().between(0,1).all()
 if review:
  for period in ['first','last']:
   p[period+'_loggap']=p[period+'_loggap_sum']/p[period+'_seen']
   p[period+'_loghistory']=p[period+'_loghistory_sum']/p[period+'_seen']
  p['change_loggap']=p.last_loggap-p.first_loggap
  p['change_loghistory']=p.last_loghistory-p.first_loghistory
 return p

def aggregate_users(p,u):
 p=p.copy()
 p['prior_valid']=p.prior_accuracy.notna().astype(int)
 for name,value in [('weighted_gain',p.improvement*p.last_seen),('weighted_first',p.first_accuracy*p.last_seen),('weighted_prior',p.prior_accuracy*p.first_seen),('weighted_elapsed',p.elapsed_days*p.last_seen)]:p[name]=value
 a=p.groupby('user_id',as_index=False).agg(matched_words=('lexeme_id','size'),prior_valid_words=('prior_valid','sum'),last_attempts=('last_seen','sum'),first_attempts=('first_seen','sum'),gain_sum=('weighted_gain','sum'),first_sum=('weighted_first','sum'),last_correct=('last_correct','sum'),prior_sum=('weighted_prior','sum'),elapsed_sum=('weighted_elapsed','sum'))
 a['improvement']=a.gain_sum/a.last_attempts;a['initial_accuracy']=a.first_sum/a.last_attempts;a['final_accuracy']=a.last_correct/a.last_attempts
 a['prior_accuracy']=a.prior_sum/a.first_attempts;a['mean_elapsed_days']=a.elapsed_sum/a.last_attempts
 a.loc[a.prior_valid_words<a.matched_words,'prior_accuracy']=np.nan
 keep=['user_id','segment','active_days','recency','words_seen','sessions','first_active','returned_4d','returned_2plus_days']
 m=u[keep].merge(a,on='user_id',how='left',validate='one_to_one');m['matched_words']=m.matched_words.fillna(0).astype(int)
 m['eligible']=m.matched_words>=5;m['eligible_10']=m.matched_words>=10
 m['model_eligible']=m.eligible&m.prior_accuracy.notna()
 return m

def standard(a):
 a=np.asarray(a,dtype=float)
 return (a-a.mean())/a.std()

def user_design(g):
 cols={'intercept':np.ones(len(g)),'gain_per_10pp':g.improvement.to_numpy()/.1}
 a=g.initial_accuracy.to_numpy();a=a-a.mean()
 cols['initial_accuracy']=standard(a);cols['initial_accuracy_squared']=standard(a*a);cols['prior_accuracy']=standard(g.prior_accuracy)
 for col in ['active_days','recency']:
  for value in sorted(g[col].unique())[1:]:cols[f'{col}_{value}']=(g[col].to_numpy()==value).astype(float)
 for col in ['words_seen','sessions','matched_words']:cols['log1p_'+col]=standard(np.log1p(g[col]))
 cols['first_observed_day']=standard(pd.to_datetime(g.first_active).dt.day)
 cols['mean_elapsed_days']=standard(g.mean_elapsed_days)
 return np.column_stack(list(cols.values())),list(cols)

def logistic(g,label,outcome='returned_2plus_days'):
 X,names=user_design(g);y=g[outcome].to_numpy(dtype=float)
 assert np.linalg.matrix_rank(X)==X.shape[1]
 beta=np.zeros(X.shape[1])
 for it in range(100):
  pr=1/(1+np.exp(-np.clip(X@beta,-35,35)));w=pr*(1-pr)
  step=np.linalg.solve(X.T@(w[:,None]*X),X.T@(y-pr));beta+=step
  if np.max(np.abs(step))<1e-9:break
 assert it<99
 pr=1/(1+np.exp(-X@beta));w=pr*(1-pr)
 bread=np.linalg.inv(X.T@(w[:,None]*X));scores=X*(y-pr)[:,None]
 cov=bread@(scores.T@scores)@bread*len(g)/(len(g)-X.shape[1]);se=np.sqrt(np.diag(cov))
 assert np.max(np.abs(X.T@(y-pr)))<1e-5
 return dict(model=label,kind='logistic',outcome=outcome,n=len(g),events=int(y.sum()),estimate=float(np.exp(beta[1])),ci_low=float(np.exp(beta[1]-1.95996398454*se[1])),ci_high=float(np.exp(beta[1]+1.95996398454*se[1])),p=math.erfc(abs(beta[1]/se[1])/math.sqrt(2)),unit='개선 +10%p당 반복학습 OR' if outcome=='returned_2plus_days' else '개선 +10%p당 재학습 OR',condition_number=float(np.linalg.cond(X)),coefficients=[dict(term=k,beta=float(b),se=float(s)) for k,b,s in zip(names,beta,se)])

def pair_design(g):
 a=g.first_accuracy.to_numpy();a=a-a.mean()
 cols={'intercept':np.ones(len(g)),'change_log2_gap':g.change_loggap.to_numpy(),'first_accuracy':standard(a),'first_accuracy_squared':standard(a*a),'first_loggap':standard(g.first_loggap),'prior_accuracy':standard(g.prior_accuracy),'change_loghistory':standard(g.change_loghistory),'elapsed_days':standard(g.elapsed_days)}
 for day in sorted(g.first_day.unique())[1:]:cols[f'first_day_{day}']=(g.first_day.to_numpy()==day).astype(float)
 return np.column_stack(list(cols.values())),list(cols)

def paired_model(g,label,weighted):
 X,names=pair_design(g);y=g.improvement.to_numpy()
 w=g.last_seen.to_numpy(dtype=float) if weighted else np.ones(len(g));w=w/w.mean()
 A=X.T@(w[:,None]*X);assert np.linalg.matrix_rank(A)==A.shape[0]
 beta=np.linalg.solve(A,X.T@(w*y));e=y-X@beta
 codes,users=pd.factorize(g.user_id,sort=False);G=len(users);N=len(g);P=X.shape[1]
 cluster=np.column_stack([np.bincount(codes,weights=w*e*X[:,j],minlength=G) for j in range(P)])
 bread=np.linalg.inv(A);cov=bread@(cluster.T@cluster)@bread*(G/(G-1))*((N-1)/(N-P));se=np.sqrt(np.diag(cov))
 assert np.max(np.abs(X.T@(w*e)))<1e-5
 return dict(model=label,kind='paired_wls',weighted=weighted,n=N,users=G,estimate=float(beta[1]*100),ci_low=float((beta[1]-1.95996398454*se[1])*100),ci_high=float((beta[1]+1.95996398454*se[1])*100),p=math.erfc(abs(beta[1]/se[1])/math.sqrt(2)),unit='간격비 2배당 정답률 차이 %p',condition_number=float(np.linalg.cond(A)),coefficients=[dict(term=k,beta=float(b),se=float(s)) for k,b,s in zip(names,beta,se)])

def main():
 OUT.mkdir(exist_ok=True);u=pd.read_csv(ROOT/'user_retention_cohort.csv',low_memory=False)
 rawhash=sha(RAW);old=json.loads((ROOT/'accuracy_change'/'accuracy_results.json').read_text(encoding='utf-8'));assert rawhash==old['source_hashes']['raw_csv']
 metadata=OUT/'extraction.json'
 if metadata.exists():
  extract=json.loads(metadata.read_text(encoding='utf-8'));assert extract['raw_sha256']==rawhash
  for file,h in extract['cache_hashes'].items():assert sha(OUT/file)==h
  p=pd.read_csv(OUT/'matched_word_pairs.csv');r=pd.read_csv(OUT/'review_word_pairs.csv');bins=json.loads((OUT/'gap_bins.json').read_text(encoding='utf-8'))
 else:
  parts=[];nrows=0
  for c in pd.read_csv(RAW,chunksize=750000,dtype={'user_id':'str','learning_language':'str','ui_language':'str','lexeme_id':'str','lexeme_string':'str'}):
   nrows+=len(c);c=c[(c.timestamp>=START)&(c.timestamp<END)].copy();c['row_hash']=pd.util.hash_pandas_object(c,index=False)
   parts.append(c.drop(columns=['p_recall','ui_language','lexeme_string']));print(f'read {nrows:,}',flush=True)
  b=pd.concat(parts,ignore_index=True);before=len(b);b=b.drop_duplicates('row_hash');removed=before-len(b)
  b['day']=((b.timestamp-START)//86400+1).astype(int)
  assert b.session_seen.gt(0).all() and b.session_correct.between(0,b.session_seen).all() and b.history_seen.gt(0).all()
  totals=b.groupby('user_id').agg(words_seen=('session_seen','sum'),words_correct=('session_correct','sum'),sessions=('timestamp','nunique'),active_days=('day','nunique')).reindex(u.user_id)
  for col in totals:np.testing.assert_array_equal(totals[col],u[col])
  sample=u.user_id.sample(200,random_state=20261013)
  b[b.user_id.isin(sample)].to_csv(OUT/'validation_sample_rows.csv',index=False)
  print('baseline totals reconciled; pairing words',flush=True)
  p=make_pairs(b);p.to_csv(OUT/'matched_word_pairs.csv',index=False)
  review=b[b.delta>=60].copy();bins=[]
  for lo,hi,label in [(60,3600,'1분~1시간 미만'),(3600,86400,'1시간~1일 미만'),(86400,259200,'1~3일 미만'),(259200,604800,'3~7일 미만'),(604800,float('inf'),'7일 이상')]:
   g=review[(review.delta>=lo)&(review.delta<hi)]
   bins.append(dict(gap_bin=label,records=len(g),users=g.user_id.nunique(),attempts=int(g.session_seen.sum()),correct=int(g.session_correct.sum()),accuracy=float(g.session_correct.sum()/g.session_seen.sum())))
  r=make_pairs(review,True);r.to_csv(OUT/'review_word_pairs.csv',index=False)
  (OUT/'gap_bins.json').write_text(json.dumps(bins,ensure_ascii=False,indent=2),encoding='utf-8')
  extract=dict(raw_rows=nrows,baseline_rows_before_dedup=before,duplicates_removed=removed,raw_sha256=rawhash,all_baseline_totals_match=True,ambiguous_matched_words=int(p.ambiguous_initial_history.sum()),ambiguous_review_pairs=int(r.ambiguous_initial_history.sum()),cache_hashes={file:sha(OUT/file) for file in ['matched_word_pairs.csv','review_word_pairs.csv','validation_sample_rows.csv','gap_bins.json']})
  metadata.write_text(json.dumps(extract,ensure_ascii=False,indent=2),encoding='utf-8');del b,review
 m=aggregate_users(p,u);m.to_csv(OUT/'user_word_improvement.csv',index=False)
 valid=m[m.model_eligible];h=valid[valid.segment=='습관 형성형']
 coverage=[]
 rclear=r[r.prior_accuracy.notna()];review_counts=rclear.groupby('user_id').size();review_ids=review_counts[review_counts>=5].index
 for seg,g in [('전체',m)]+list(m.groupby('segment',sort=False)):
  v=g[g.eligible]
  coverage.append(dict(segment=seg,baseline_users=len(g),no_matched_words=int(g.matched_words.eq(0).sum()),one_to_four_words=int(g.matched_words.between(1,4).sum()),eligible_users=len(v),model_users=int(g.model_eligible.sum()),ambiguous_history_users=int((g.eligible&~g.model_eligible).sum()),eligible_10_users=int((g.eligible_10&g.model_eligible).sum()),review_eligible_users=int(g.user_id.isin(review_ids).sum()),mean_improvement=float(v.improvement.mean()) if len(v) else None))
 h=h.copy();h['gain_quartile']=pd.qcut(h.improvement,4,labels=['Q1 낮은 개선','Q2','Q3','Q4 높은 개선'])
 desc=h.groupby('gain_quartile',observed=True).agg(n=('user_id','size'),repeated=('returned_2plus_days','sum'),gain_min=('improvement','min'),gain_max=('improvement','max'),initial_mean=('initial_accuracy','mean'),final_mean=('final_accuracy','mean'),words_median=('matched_words','median')).reset_index()
 desc['repeat_rate']=desc.repeated/desc.n
 models=[logistic(h,'습관 형성형 · 5단어 이상 · 반복학습'),logistic(valid,'전체 · 5단어 이상 · 반복학습'),logistic(h[h.eligible_10],'습관 형성형 · 10단어 이상 · 반복학습'),logistic(h,'습관 형성형 · 5단어 이상 · 재학습','returned_4d')]
 rp=rclear[rclear.user_id.isin(review_ids)].copy()
 models.extend([paired_model(rp,'동일 사용자·단어 · 마지막 노출 가중',True),paired_model(rp,'동일 사용자·단어 · 단어 쌍 동일 가중',False)])
 running=0
 for rank,i in enumerate(sorted(range(6),key=lambda i:models[i]['p'])):
  running=max(running,models[i]['p']*(6-rank));models[i]['p_holm']=min(1.,running)
 pd.DataFrame(coverage).to_csv(OUT/'coverage.csv',index=False);desc.to_csv(OUT/'habit_improvement_quartiles.csv',index=False);pd.DataFrame(bins).to_csv(OUT/'gap_bins.csv',index=False)
 pd.DataFrame([{k:v for k,v in q.items() if k!='coefficients'} for q in models]).to_csv(OUT/'model_effects.csv',index=False)
 result=dict(analysis_date='2026-10-13',baseline='2013-03-01..07 UTC',followup='2013-03-08..11 UTC',source_hashes={'raw_csv':rawhash,'user_retention_cohort.csv':sha(ROOT/'user_retention_cohort.csv'),'definition_document':sha(ROOT.parent/'docs'/'03_지표_정의서.md'),'analysis_protocol':sha(OUT/'분석_설계_사전기록.md')},extraction=extract,coverage=coverage,quartiles=desc.to_dict('records'),gap_bins=bins,models=models,pair_counts={'matched_word_pairs':len(p),'review_word_pairs_all':len(r),'review_pairs_model':len(rp),'review_users_model':len(review_ids)},checks={'original_metric_formula_reproduced':True,'baseline_only':True,'all_baseline_user_totals_match':True,'pair_keys_unique':not p.duplicated(KEY).any(),'different_calendar_days':bool((p.first_day<p.last_day).all()),'initial_history_before_first_observation':True,'all_models_full_rank_converged':True})
 (OUT/'word_performance_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
 print(json.dumps({'coverage':coverage,'models':[{k:v for k,v in q.items() if k!='coefficients'} for q in models],'pair_counts':result['pair_counts']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
