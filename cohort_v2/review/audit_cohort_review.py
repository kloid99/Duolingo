"""Read-only methodological diagnostics and synthetic counterexamples for review."""
from pathlib import Path
import csv,json,math,sys,hashlib,importlib.util
import pandas as pd
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
sys.dont_write_bytecode=True
def clean(frame):return json.loads(frame.to_json(orient='records',force_ascii=False,double_precision=15))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    source=PROJECT/'behavior_flow'
    c=pd.read_csv(source/'primary_candidate_eligibility.csv');o=pd.read_csv(source/'primary_candidate_outcomes.csv')
    a=c.merge(o,on=['candidate_id','user_id','candidate','eligibility_date_utc'],validate='one_to_one')
    grouped=[]
    for grouping in ['eligibility_date_utc','inactive_completed_dates_before_trigger']:
        for key,g in a.groupby(grouping):
            q=g[g.fully_observed];n=len(q);k=int(q.any_learning.sum()) if n else None
            n_d1=int(g.first_outcome_date_active.notna().sum())
            grouped.append(dict(grouping=grouping,value=str(key),candidate_users=len(g),fully_observed_users=n,successes=k,rate=k/n if n else None,d1_observed_users=n_d1,d1_learning_users=int(g.first_outcome_date_active.sum()) if n_d1 else None))
    frame=pd.DataFrame(grouped);frame.to_csv(ROOT/'a1_date_and_gap_coverage.csv',index=False,encoding='utf-8-sig')
    profiles=[]
    for status,g in a.groupby('fully_observed'):
        profiles.append(dict(fully_observed=bool(status),users=len(g),baseline_active_days_mean=float(g.active_days.mean()),baseline_recency_mean=float(g.recency.mean()),baseline_exposure_median=float(g.words_seen.median()),pretrigger_inactive_days_mean=float(g.inactive_completed_dates_before_trigger.mean())))
    pd.DataFrame(profiles).to_csv(ROOT/'a1_observation_profiles.csv',index=False,encoding='utf-8-sig')
    coverage=[]
    for name,relative,eligibility in [('세션 간격','regularity/user_regularity.csv','eligible'),('전체 정답률','accuracy_change/user_accuracy_change.csv','eligible'),('같은 단어 개선','word_performance/user_word_improvement.csv','model_eligible')]:
        m=pd.read_csv(PROJECT/relative);m=m[m.segment.eq('습관 형성형')]
        if 'definition' in m:m=m[m.definition.eq('timestamp')]
        for flag,g in m.groupby(eligibility):
            coverage.append(dict(analysis=name,eligible=bool(flag),users=len(g),repeat_users=int(g.returned_2plus_days.sum()),repeat_rate=float(g.returned_2plus_days.mean()),baseline_days_mean=float(g.active_days.mean()),baseline_exposure_median=float(g.words_seen.median())))
    pd.DataFrame(coverage).to_csv(ROOT/'analysis_selection_profiles.csv',index=False,encoding='utf-8-sig')
    # The official analysis includes clear-history users with >=5 matched review pairs.
    rp=pd.read_csv(PROJECT/'word_performance/review_word_pairs.csv',usecols=['user_id','prior_accuracy','last_seen'])
    rp=rp[rp.prior_accuracy.notna()];counts=rp.groupby('user_id').size();ids=counts[counts>=5].index;rp=rp[rp.user_id.isin(ids)]
    weights=rp.groupby('user_id').last_seen.sum().sort_values(ascending=False)
    influence=dict(users=len(weights),pairs=len(rp),last_exposure_weight_total=int(weights.sum()),largest_user_weight_share=float(weights.iloc[0]/weights.sum()),top_one_percent_users=math.ceil(len(weights)*.01),top_one_percent_weight_share=float(weights.iloc[:math.ceil(len(weights)*.01)].sum()/weights.sum()))
    spec=importlib.util.spec_from_file_location('measurement_review',PROJECT/'final_delivery/measurement_reference.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assignments=[dict(assignment_id='synthetic-a',experiment_id='synthetic-review-only',user_id='synthetic-user',variant='control',eligibility_at_utc='2013-03-08T12:00:00Z',assigned_at_utc='2013-03-08T12:00:01Z')]
    cov=[dict(date_utc=date,complete=True,checked_at_utc='2013-03-11T00:00:00Z') for date in ['2013-03-09','2013-03-10']]
    early=module.evaluate(assignments,[],cov,'2013-03-11T00:00:00Z')
    future_cov=[dict(x,checked_at_utc='2013-03-15T00:00:00Z') for x in cov]
    future=module.evaluate(assignments,[],future_cov,'2013-03-13T00:00:00Z')
    cases=dict(synthetic_inputs_only=True,end_of_D2_without_48h_wait=dict(returned_fully_observed=early['outcomes'][0]['fully_observed'],returned_y=early['outcomes'][0]['y'],required_by_spec='pending until 2013-03-13T00:00:00Z'),coverage_checked_after_freeze=dict(returned_fully_observed=future['outcomes'][0]['fully_observed'],returned_y=future['outcomes'][0]['y'],coverage_checked_at='2013-03-15T00:00:00Z',freeze_at='2013-03-13T00:00:00Z',required_by_contract='coverage unavailable at this freeze'))
    report=(PROJECT/'final_delivery/최종_코호트분석_보고서.md').read_text(encoding='utf-8')
    with (PROJECT/'final_delivery/report_claims.csv').open(encoding='utf-8-sig',newline='') as f:claims=list(csv.DictReader(f))
    mutated=report.replace('| 꾸준형 | 8,882 |','| __SWAP__ | 8,882 |').replace('| 최근 단발형 | 15,402 |','| 꾸준형 | 15,402 |').replace('| __SWAP__ | 8,882 |','| 최근 단발형 | 8,882 |')
    assert mutated!=report
    report_gap=dict(original_display_presence_check_passes=all(r['display'] in report for r in claims),mislabelled_in_memory_table_also_passes=all(r['display'] in mutated for r in claims),actual_report_was_not_modified=True,conclusion='substring presence does not verify row identity/metric-period association')
    with (PROJECT/'final_delivery/sample_size_results.json').open(encoding='utf-8') as f:plan=json.load(f)
    result=dict(a1=dict(candidate_users=len(a),observed_users=int(a.fully_observed.sum()),observed_share=float(a.fully_observed.mean()),unobserved_users=int((~a.fully_observed).sum()),observed_pretrigger_gaps=sorted(int(x) for x in a[a.fully_observed].inactive_completed_dates_before_trigger.unique()),unobserved_pretrigger_gaps=sorted(int(x) for x in a[~a.fully_observed].inactive_completed_dates_before_trigger.unique()),date_gap_groups=clean(frame),profiles=profiles),analysis_selection=coverage,paired_weight_concentration=influence,measurement_counterexamples=cases,report_validation_counterexample=report_gap,planning_default=plan['default'],source_hashes={str(p.relative_to(PROJECT)):sha(p) for p in [source/'primary_candidate_eligibility.csv',source/'primary_candidate_outcomes.csv',PROJECT/'final_delivery/measurement_reference.py',PROJECT/'final_delivery/verify_final_delivery.py',PROJECT/'final_delivery/최종_코호트분석_보고서.md']})
    (ROOT/'review_diagnostics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
