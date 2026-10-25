"""Compare structured report rows against independent historical source outputs."""
from pathlib import Path
import json,csv,re,hashlib
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
def load(path):return json.loads((PROJECT/path).read_text(encoding='utf-8'))
def rows(path):
    with (PROJECT/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def table(report,header):
    lines=report.splitlines();assert lines.count(header)==1,('missing/duplicate table header',header)
    i=lines.index(header);assert lines[i+1].startswith('|---')
    out=[]
    for line in lines[i+2:]:
        if not line.startswith('|'):break
        out.append([x.strip() for x in line.strip('|').split('|')])
    return out
def verify(report):
    b=load('behavior_flow/behavior_flow_results.json');cv=load('regularity/regularity_results.json');acc=load('accuracy_change/accuracy_results.json');w=load('word_performance/word_performance_results.json');sens=load('sensitivity/sensitivity_results.json');rb=load('corrections/robustness_results.json')
    plan=json.loads((ROOT/'sample_size_results.json').read_text(encoding='utf-8'))
    contracts={}
    contracts['| 집단 | 기준 인원(명) | 추적 기록 없음(명) | 1일 기록(명) | 2일 이상 기록(명) | 2일 이상 비율(%) |']=[[r['segment'],f"{r['baseline_users']:,}",f"{r['no_learning_users']:,}",f"{r['one_learning_day_users']:,}",f"{r['two_plus_learning_days_users']:,}",f"{r['two_plus_learning_days_share']:.1%}"] for r in b['flow']]
    primary=rows('behavior_flow/primary_candidate_outcomes.csv');observed=[r for r in primary if r['fully_observed']=='True']
    labels=['D1·D2 없음','D1만','D2만','양일'];counts=[]
    for code in ['00','10','01','11']:counts.append(sum(int(float(r['first_outcome_date_active']))==int(code[0]) and int(float(r['second_outcome_date_active']))==int(code[1]) for r in observed))
    contracts['| A1 다음 두 날짜의 흐름 | 인원 | 비율 |']=[[label,f'{n:,}',f'{n/len(observed):.1%}'] for label,n in zip(labels,counts)]
    contracts['| 최소 탐지 폭 가정 | 검정력 | 군별 표본 | 총 표본 |']=[[f"+{r['mde']*100:.0f}%p",f"{r['target_power']:.0%}",f"{r['n_per_arm']:,}",f"{r['n_total']:,}"] for r in plan['scenarios']]
    coverage=rows('review/a1_date_and_gap_coverage.csv')
    for grouping,header in [('eligibility_date_utc','| A1 재개 날짜(UTC) | 후보(명) | 완전 관측(명) | 추가 기록(명) | 완전 관측 중 비율(%) |'),('inactive_completed_dates_before_trigger','| 직전 비활동(완전 UTC 날짜 수) | 후보(명) | 완전 관측(명) | 추가 기록(명) | 완전 관측 중 비율(%) |')]:
        contracts[header]=[[r['value'],f"{int(r['candidate_users']):,}",f"{int(r['fully_observed_users']):,}",f"{int(float(r['successes'])):,}" if r['rate'] else '미확인',f"{float(r['rate']):.1%}" if r['rate'] else '미확인'] for r in coverage if r['grouping']==grouping]
    selection=rows('review/analysis_selection_profiles.csv');expected=[]
    for name in ['세션 간격','전체 정답률','같은 단어 개선']:
        yes=next(r for r in selection if r['analysis']==name and r['eligible']=='True');no=next(r for r in selection if r['analysis']==name and r['eligible']=='False')
        expected.append([name,f"{int(yes['users']):,}",f"{int(no['users']):,}",f"{float(yes['repeat_rate']):.1%}",f"{float(no['repeat_rate']):.1%}"])
    contracts['| 분석 | 포함(명) | 제외(명) | 포함자 반복률(%) | 제외자 반복률(%) |']=expected
    contracts['| 보완 모형 | 분석행 / 사용자 | 추정값 | 개별 95% CI | Holm p | 단위 |']=[[r['model'],f"{r['n']:,} / {r.get('users',r['n']):,}",f"{r.get('estimate',r.get('odds_ratio')):.3f}",f"{r['ci_low']:.3f}~{r['ci_high']:.3f}",f"{r['p_holm']:.3g}",r['unit']] for r in rb['models']]
    # Check the full labeled hypothesis cells rather than searching for numbers anywhere.
    x,y,z=cv['models'][1],cv['models'][3],acc['models'][1];a,c,d=w['models'][0],w['models'][4],w['models'][5];s=next(r for r in sens['final'] if r['segment']=='전체')
    q=table(report,'| 질문 | 주요 근거 | 결론과 활용 |')
    expected_evidence=[['세션 간격 변동성과 반복학습',f"습관 형성형 {x['n']:,}명, log(1+CV) 1SD당 OR {x['odds_ratio']:.3f} (CI {x['ci_low']:.3f}~{x['ci_high']:.3f}). 30분 세션 정의 {y['n']:,}명, OR {y['odds_ratio']:.3f}"],['전체 초반·후반 정답률 변화',f"습관 형성형 {z['n']:,}명, +10%p당 OR {z['odds_ratio']:.3f} (CI {z['ci_low']:.3f}~{z['ci_high']:.3f})"],['같은 단어 성과 개선',f"습관 형성형 {a['n']:,}명, +10%p당 OR {a['estimate']:.3f} (CI {a['ci_low']:.3f}~{a['ci_high']:.3f}), Holm p=1.000"],['직접 단어 복습 간격',f"{c['users']:,}명·{c['n']:,}쌍. 간격비 2배당 노출 가중 +{c['estimate']:.3f}%p, 동일 가중 +{d['estimate']:.3f}%p"],['비활동 2일·3일',f"3/11 종료 {s['inactive_2day_users']:,}명 대 {s['inactive_3day_users']:,}명, 추가 {s['added_exact2_users']:,}명"]]
    assert [r[:2] for r in q]==expected_evidence,'hypothesis labels/units/values mismatch'
    for header,expected in contracts.items():assert table(report,header)==expected,('semantic row mismatch',header)
    required=['기준 주간 2013-03-01~07 UTC','03-08~11의 네 완전 날짜','습관 형성형 고정 14,583명','45.6%는 3/8·9 및 비활동 1~2일의 조건부 비율','분모는 모든 배정 사용자','[D1 00:00,D8 00:00), 동결 판정 D8+48시간 이후','기록 없음은 앱 미사용·모든 학습 부재·영구 이탈을 뜻하지 않는다']
    for text in required:assert text in report,('scope/period/denominator contract missing',text)
    users=rows('user_retention_cohort.csv');nsm=sum(int(r['active_days'])>=4 for r in users)
    assert f'기준 주간의 달성자는 {nsm:,}명이다.' in report,'NSM label/value mismatch'
    a1=next(r for r in b['candidates'] if r.get('eligible_users')==4809)
    assert f"재개 다음 두 날짜를 모두 관측한 {a1['fully_observed_users']:,}명 중 {a1['learning_users']:,}명({a1['rate']:.1%})" in report,'A1 numerator/denominator mismatch'
    return dict(tables_verified=len(contracts)+1,labeled_rows_verified=sum(map(len,contracts.values()))+len(q),scope_period_and_denominator_contracts_verified=len(required))
def freshness(plan,config=None,config_hash=None):
    if config is None:config=json.loads((ROOT/'experiment_config.json').read_text(encoding='utf-8'))
    if config_hash is None:config_hash=sha(ROOT/'experiment_config.json')
    assert plan['config']==config,'stored planning config is stale'
    assert plan['source_hashes']['experiment_config.json']==config_hash,'stored config hash is stale'
    assert plan['source_hashes']['primary_candidate_outcomes.csv']==sha(PROJECT/'behavior_flow/primary_candidate_outcomes.csv'),'primary input changed'
