"""Prespecified audit; historical primary outputs are read-only."""
from pathlib import Path
import sys,json,math
import numpy as np
import pandas as pd
OUT=Path(__file__).resolve().parent;ROOT=OUT.parent
sys.path.insert(0,str(ROOT))
import analyze_regularity as cv
import analyze_accuracy_change as acc
import analyze_word_performance as word

def logistic_extra(g,language=False,quadratic=False):
    z=word.standard(np.log1p(g.cv.to_numpy()))
    cols={'intercept':np.ones(len(g)),'log1p_cv_per_sd':z}
    for col in ['active_days','recency']:
        for level in sorted(g[col].unique())[1:]:cols[f'{col}_{level}']=(g[col].to_numpy()==level).astype(float)
    for col in ['words_seen','n_sessions']:cols['log1p_'+col]=word.standard(np.log1p(g[col]))
    cols['first_hour']=word.standard(g.first_hour)
    if language:
        counts=g.dominant_language.value_counts();lang=g.dominant_language.where(g.dominant_language.map(counts)>=50,'other')
        for l in sorted(lang.unique())[1:]:cols['language_'+l]=(lang.to_numpy()==l).astype(float)
    if quadratic:cols['cv_squared']=z*z
    X=np.column_stack(list(cols.values()));names=list(cols);y=g.returned_2plus_days.to_numpy(dtype=float)
    assert np.linalg.matrix_rank(X)==X.shape[1]
    beta=np.zeros(X.shape[1])
    for it in range(100):
        p=1/(1+np.exp(-np.clip(X@beta,-35,35)));w=p*(1-p)
        step=np.linalg.solve(X.T@(w[:,None]*X),X.T@(y-p));beta+=step
        if np.max(abs(step))<1e-9:break
    assert it<99
    p=1/(1+np.exp(-np.clip(X@beta,-35,35)));w=p*(1-p)
    bread=np.linalg.inv(X.T@(w[:,None]*X));score=X*(y-p)[:,None]
    covariance=bread@(score.T@score)@bread*len(g)/(len(g)-X.shape[1]);se=np.sqrt(np.diag(covariance))
    assert np.max(abs(X.T@(y-p)))<1e-5
    j=names.index('cv_squared') if quadratic else 1
    return dict(model='CV 언어 보정 + 제곱항 진단' if quadratic else 'CV 언어 추가 보정',n=len(g),estimate=float(beta[j]) if quadratic else float(np.exp(beta[j])),ci_low=float(beta[j]-1.95996398454*se[j]) if quadratic else float(np.exp(beta[j]-1.95996398454*se[j])),ci_high=float(beta[j]+1.95996398454*se[j]) if quadratic else float(np.exp(beta[j]+1.95996398454*se[j])),p=math.erfc(abs(beta[j]/se[j])/math.sqrt(2)),unit='제곱항 log-odds 계수' if quadratic else 'log1p(CV) 1SD당 OR',logcv_sd=float(np.log1p(g.cv).std(ddof=0)),iterations=it+1,coefficients=[dict(term=k,beta=float(b),se=float(s)) for k,b,s in zip(names,beta,se)])

def main():
    rawhash=cv.sha(cv.RAW)
    prior=json.loads((cv.OUT/'regularity_results.json').read_text(encoding='utf-8'))
    assert rawhash==prior['source_hashes']['raw_csv']
    cache=OUT/'baseline_language_profiles.csv';extreme_path=OUT/'extreme_users.csv'
    if cache.exists():
        meta=json.loads((OUT/'raw_profile_extraction.json').read_text(encoding='utf-8'))
        assert meta['raw_sha256']==rawhash and meta['profile_sha256']==cv.sha(cache) and meta['extreme_sha256']==cv.sha(extreme_path)
        profiles=pd.read_csv(cache);extreme=set(pd.read_csv(extreme_path).user_id)
    else:
        extreme=set();baseline_extreme=set();parts=[];rows=0
        for c in pd.read_csv(cv.RAW,chunksize=750000,dtype={'user_id':'str','learning_language':'str','ui_language':'str','lexeme_id':'str','lexeme_string':'str'}):
            rows+=len(c);extreme.update(c.loc[c.history_seen>1000,'user_id'])
            c=c[(c.timestamp>=cv.START)&(c.timestamp<cv.END)].copy()
            baseline_extreme.update(c.loc[c.history_seen>1000,'user_id']);c['row_hash']=pd.util.hash_pandas_object(c,index=False)
            parts.append(c[['user_id','learning_language','session_seen','row_hash']]);print(f'raw profile read {rows:,}',flush=True)
        b=pd.concat(parts,ignore_index=True);before=len(b);b=b.drop_duplicates('row_hash')
        assert before-len(b)==81 and len(b)==7782042 and len(extreme)==104
        language=b.groupby(['user_id','learning_language'],as_index=False).session_seen.sum()
        dominant=language.sort_values(['user_id','session_seen','learning_language'],ascending=[True,False,True]).drop_duplicates('user_id').rename(columns={'learning_language':'dominant_language','session_seen':'dominant_attempts'})
        profiles=dominant.merge(language.groupby('user_id').agg(total_attempts=('session_seen','sum'),languages=('learning_language','size')),on='user_id',validate='one_to_one')
        profiles['dominant_share']=profiles.dominant_attempts/profiles.total_attempts
        assert len(profiles)==82467
        profiles.to_csv(cache,index=False)
        pd.DataFrame({'user_id':sorted(extreme),'baseline_history_over1000':[u in baseline_extreme for u in sorted(extreme)]}).to_csv(extreme_path,index=False)
        meta=dict(raw_sha256=rawhash,raw_rows=rows,extreme_users=len(extreme),baseline_extreme_users=len(baseline_extreme),dedup_removed=81,profile_sha256=cv.sha(cache),extreme_sha256=cv.sha(extreme_path))
        (OUT/'raw_profile_extraction.json').write_text(json.dumps(meta,indent=2),encoding='utf-8');del b,parts,language
    u=pd.read_csv(ROOT/'user_retention_cohort.csv');np.testing.assert_array_equal(profiles.set_index('user_id').loc[u.user_id,'total_attempts'],u.words_seen)
    r=pd.read_csv(cv.OUT/'user_regularity.csv');g=r[(r.segment=='습관 형성형')&r.eligible&(r.definition=='timestamp')].merge(profiles,on='user_id',validate='one_to_one')
    a=pd.read_csv(acc.OUT/'user_accuracy_change.csv');ag=a[(a.segment=='습관 형성형')&a.eligible]
    w=pd.read_csv(word.OUT/'user_word_improvement.csv');wg=w[(w.segment=='습관 형성형')&w.model_eligible]
    extraction=json.loads((word.OUT/'extraction.json').read_text(encoding='utf-8'))
    assert cv.sha(word.OUT/'review_word_pairs.csv')==extraction['cache_hashes']['review_word_pairs.csv']
    pairs=pd.read_csv(word.OUT/'review_word_pairs.csv');pairs=pairs[pairs.prior_accuracy.notna()]
    counts=pairs.groupby('user_id').size();pairs=pairs[pairs.user_id.isin(counts[counts>=5].index)]
    assert len(pairs)==745195 and pairs.user_id.nunique()==23019
    weights=pairs.groupby('user_id',as_index=False).last_seen.sum().sort_values(['last_seen','user_id'],ascending=[False,True]);ntop=math.ceil(len(weights)*.01);top=set(weights.head(ntop).user_id)
    weights['excluded_top1pct']=weights.user_id.isin(top);weights.to_csv(OUT/'pair_user_weights.csv',index=False)
    bases=[cv.fit(g,'CV 주 분석 재현'),acc.fit(ag,'전체 정확도 주 분석 재현'),word.logistic(wg,'같은 단어 주 분석 재현'),word.paired_model(pairs,'가중 간격 주 분석 재현',True),word.paired_model(pairs,'동일 가중 주 분석 재현',False)]
    oldacc=json.loads((acc.OUT/'accuracy_results.json').read_text(encoding='utf-8'));oldword=json.loads((word.OUT/'word_performance_results.json').read_text(encoding='utf-8'))
    originals=[prior['models'][1],oldacc['models'][1],oldword['models'][0],oldword['models'][4],oldword['models'][5]]
    for new,old in zip(bases,originals):
        for field in ['ci_low','ci_high','p']:
            assert math.isclose(new[field],old[field],rel_tol=1e-7,abs_tol=1e-10),(new['model'],field)
        assert math.isclose(new.get('estimate',new.get('odds_ratio')),old.get('estimate',old.get('odds_ratio')),rel_tol=1e-9)
    models=[cv.fit(g[~g.user_id.isin(extreme)],'CV · 104명 제외'),acc.fit(ag[~ag.user_id.isin(extreme)],'전체 정확도 · 104명 제외'),word.logistic(wg[~wg.user_id.isin(extreme)],'같은 단어 · 104명 제외')]
    models[0]['unit']='log1p(CV) 1SD당 OR';models[1]['unit']='정답률 변화 +10%p당 OR'
    for weighted in [True,False]:models.append(word.paired_model(pairs[~pairs.user_id.isin(extreme)],'간격 · 104명 제외 · '+('노출 가중' if weighted else '동일 가중'),weighted))
    for weighted in [True,False]:models.append(word.paired_model(pairs[~pairs.user_id.isin(top)],'간격 · 상위1% 제외 · '+('노출 가중' if weighted else '동일 가중'),weighted))
    models.append(logistic_extra(g,language=True));shape=logistic_extra(g,language=True,quadratic=True)
    running=0
    for rank,i in enumerate(sorted(range(len(models)),key=lambda i:models[i]['p'])):
        running=max(running,models[i]['p']*(len(models)-rank));models[i]['p_holm']=min(1.,running)
    profiles_out=[]
    for name,ids in [('CV',set(g.user_id)),('전체 정확도',set(ag.user_id)),('같은 단어',set(wg.user_id))]:
        hu=u[u.segment=='습관 형성형'].merge(profiles,on='user_id');hu['included']=hu.user_id.isin(ids)
        for include,group in hu.groupby('included'):
            for dim in ['dominant_language','first_active']:
                for value,s in group.groupby(dim):profiles_out.append(dict(analysis=name,included=bool(include),dimension=dim,value=value,users=len(s),share=len(s)/len(group),repeat_rate=float(s.returned_2plus_days.mean())))
    pd.DataFrame(profiles_out).to_csv(OUT/'selection_language_time_profiles.csv',index=False)
    overlap=[dict(analysis=name,n=len(group),extreme_users=int(group.user_id.isin(extreme).sum())) for name,group in [('CV',g),('전체 정확도',ag),('같은 단어',wg),('간격 사용자',weights)]]
    result=dict(protocol_sha256=cv.sha(OUT/'민감도_추가설계.md'),raw_extraction=meta,baseline_models=bases,models=models,shape_diagnostic=shape,extreme_overlap=overlap,top_users=ntop,top_weight_share=float(weights.head(ntop).last_seen.sum()/weights.last_seen.sum()),selection_profiles=profiles_out,external_validation='time-out replication, signup/channel and complete-service coverage require new data',checks=dict(primary_refits_match=True,all_models_full_rank_converged_score_checked=True,baseline_language_attempts_match=True))
    (OUT/'robustness_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    pd.DataFrame([{k:v for k,v in r.items() if k!='coefficients'} for r in models]).to_csv(OUT/'robustness_models.csv',index=False)
    sources=[cv.OUT/'user_regularity.csv',acc.OUT/'user_accuracy_change.csv',word.OUT/'user_word_improvement.csv',word.OUT/'review_word_pairs.csv',ROOT/'user_retention_cohort.csv',Path(__file__)]
    manifest=dict(source_hashes={str(p.relative_to(ROOT)):cv.sha(p) for p in sources},files={p.name:cv.sha(p) for p in OUT.iterdir() if p.is_file() and p.name not in ['robustness_manifest.json','prior_final_delivery_manifest.json']})
    (OUT/'robustness_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(models=[{k:v for k,v in r.items() if k!='coefficients'} for r in models],shape={k:v for k,v in shape.items() if k!='coefficients'},overlap=overlap),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
