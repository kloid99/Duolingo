"""Planning calculations and traceable report metrics; no simulated campaign effects."""
from pathlib import Path
from statistics import NormalDist
import math,json,csv,hashlib
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
N=NormalDist()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(name):return json.loads((PROJECT/name).read_text(encoding='utf-8'))
def power(p0,delta,n,alpha):
    p1=p0+delta;pb=(p0+p1)/2
    null=math.sqrt(2*pb*(1-pb));alt=math.sqrt(p0*(1-p0)+p1*(1-p1));z=N.inv_cdf(1-alpha/2)
    return N.cdf((delta*math.sqrt(n)-z*null)/alt)+N.cdf((-delta*math.sqrt(n)-z*null)/alt)
def size(p0,delta,target,alpha):
    assert 0<p0<p0+delta<1 and 0.5<target<1 and 0<alpha<1
    p1=p0+delta;pb=(p0+p1)/2
    raw=((N.inv_cdf(1-alpha/2)*math.sqrt(2*pb*(1-pb))+N.inv_cdf(target)*math.sqrt(p0*(1-p0)+p1*(1-p1)))/delta)**2
    n=2*math.ceil(raw/2)
    assert power(p0,delta,n,alpha)>=target
    return dict(p0=p0,p1=p1,mde=delta,target_power=target,n_per_arm_unrounded=raw,n_per_arm=n,n_total=2*n,achieved_approx_power=power(p0,delta,n,alpha))
def main():
    config=json.loads((ROOT/'experiment_config.json').read_text(encoding='utf-8'))
    from validate_experiment_config import validate,readiness
    validate(config)
    primary=PROJECT/'behavior_flow/primary_candidate_outcomes.csv'
    with primary.open(encoding='utf-8-sig',newline='') as f:q=list(csv.DictReader(f))
    observed=[r for r in q if r['fully_observed']=='True'];k=sum(int(float(r['any_learning'])) for r in observed)
    assert len(q)==4809 and len(observed)==2880 and k==1312
    p0=k/len(observed);scenarios=[size(p0,delta,pow,config['alpha_two_sided']) for pow in [0.8,0.9] for delta in [0.02,0.03,0.05]]
    default=size(p0,config['planning_mde_absolute'],config['target_power'],config['alpha_two_sided'])
    timing=[]
    for rate in [100,500,1000]:
        enroll=max(config['minimum_enrollment_utc_days'],math.ceil(default['n_total']/rate))
        timing.append(dict(assumed_daily_new_eligible=rate,required_enrollment_days=enroll,within_proposed_maximum=enroll<=config['maximum_enrollment_utc_days'],enrollment_days=min(enroll,config['maximum_enrollment_utc_days']),final_primary_result_days_from_start=min(enroll,config['maximum_enrollment_utc_days'])+2+config['data_lateness_allowance_days'],assumption_not_actual=True))
    robust=[size(base,config['planning_mde_absolute'],config['target_power'],config['alpha_two_sided']) for base in [0.4374381787439461,0.47379133797689077,0.5]]
    data=dict(historical_successes=k,historical_n=len(observed),historical_candidate_users=len(q),historical_baseline=p0,config=config,default=default,scenarios=scenarios,timing_scenarios=timing,baseline_sensitivity=robust,actual_enrollment_days=None,actual_launch_date=None,method='Normal approximation, pooled null variance and unpooled alternative variance; two-sided alpha; rounded to full randomized blocks of four total',source_hashes={'primary_candidate_outcomes.csv':sha(primary),'experiment_config.json':sha(ROOT/'experiment_config.json')})
    data['launch_readiness']=readiness(config)
    data['baseline_scope']='2013-03-08/09 early first observed returners; gaps 1/2 only; not a validated prospective control rate'
    (ROOT/'sample_size_results.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    for name,rows in [('sample_size_scenarios.csv',scenarios),('duration_scenarios.csv',timing),('baseline_sensitivity.csv',robust)]:
        with (ROOT/name).open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    sources={name:load(name) for name in ['behavior_flow/behavior_flow_results.json','regularity/regularity_results.json','accuracy_change/accuracy_results.json','word_performance/word_performance_results.json','sensitivity/sensitivity_results.json']}
    metrics=[]
    def add(key,name,pointer,unit,display_type):
        val=sources[name]
        for token in pointer.split('/'):val=val[int(token)] if isinstance(val,list) else val[token]
        display=f'{val:,}' if display_type=='count' else f'{val:.1%}' if display_type=='rate' else f'{val:.3f}'
        metrics.append(dict(metric_id=key,source=name,json_pointer=pointer,value=val,unit=unit,display=display))
    behavior='behavior_flow/behavior_flow_results.json'
    for i,s in enumerate(['overall','steady','habit','recent','paused_steady','paused_intense','paused_low']):
        for field in ['baseline_users','no_learning_users','one_learning_day_users','two_plus_learning_days_users']:add(f'{s}_{field}',behavior,f'flow/{i}/{field}','users','count')
        add(f'{s}_repeat_rate',behavior,f'flow/{i}/two_plus_learning_days_share','proportion','rate')
    add('a1_candidates',behavior,'candidates/6/eligible_users','users','count')
    add('a1_observed',behavior,'candidates/6/fully_observed_users','users','count')
    add('a1_successes',behavior,'candidates/6/learning_users','users','count')
    add('a1_rate',behavior,'candidates/6/rate','proportion','rate')
    for key,name,index,field in [('cv_or','regularity/regularity_results.json',1,'odds_ratio'),('cv_low','regularity/regularity_results.json',1,'ci_low'),('cv_high','regularity/regularity_results.json',1,'ci_high'),('cv30_or','regularity/regularity_results.json',3,'odds_ratio'),('allacc_or','accuracy_change/accuracy_results.json',1,'odds_ratio'),('word_or','word_performance/word_performance_results.json',0,'estimate'),('word_low','word_performance/word_performance_results.json',0,'ci_low'),('word_high','word_performance/word_performance_results.json',0,'ci_high'),('gap_weighted','word_performance/word_performance_results.json',4,'estimate'),('gap_unweighted','word_performance/word_performance_results.json',5,'estimate')]:add(key,name,f'models/{index}/{field}','OR' if not key.startswith('gap') else 'percentage_points','float')
    with (PROJECT/'user_retention_cohort.csv').open(encoding='utf-8-sig',newline='') as f:users=list(csv.DictReader(f))
    nsm=sum(int(r['active_days'])>=4 for r in users);assert nsm==9834
    metrics.append(dict(metric_id='baseline_nsm',source='user_retention_cohort.csv',json_pointer='derived:active_days>=4',value=nsm,unit='users',display=f'{nsm:,}'))
    final=sources['sensitivity/sensitivity_results.json']['final']
    ix=next(i for i,r in enumerate(final) if r['segment']=='전체')
    for field in ['inactive_2day_users','inactive_3day_users','added_exact2_users']:add(field,'sensitivity/sensitivity_results.json',f'final/{ix}/{field}','users','count')
    with (ROOT/'report_claims.csv').open('w',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fieldnames=metrics[0]);w.writeheader();w.writerows(metrics)
    (ROOT/'report_metrics.json').write_text(json.dumps({r['metric_id']:r for r in metrics},ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(default=default,timing=timing,baseline_sensitivity=robust,report_metrics=len(metrics)),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
