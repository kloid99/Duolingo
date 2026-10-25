from pathlib import Path
import json,csv,sys,os
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
import numpy
sys.path.append(str(PROJECT.parent/'cohort_v1/tmp/python_deps'))
os.environ['MPLCONFIGDIR']=str(PROJECT/'tmp/mplconfig')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
def main():
    metrics=json.loads((ROOT/'report_metrics.json').read_text(encoding='utf-8'))
    plan=json.loads((ROOT/'sample_size_results.json').read_text(encoding='utf-8'))
    b=json.loads((PROJECT/'behavior_flow/behavior_flow_results.json').read_text(encoding='utf-8'))
    cv=json.loads((PROJECT/'regularity/regularity_results.json').read_text(encoding='utf-8'))
    acc=json.loads((PROJECT/'accuracy_change/accuracy_results.json').read_text(encoding='utf-8'))
    word=json.loads((PROJECT/'word_performance/word_performance_results.json').read_text(encoding='utf-8'))
    robust=json.loads((PROJECT/'corrections/robustness_results.json').read_text(encoding='utf-8'))
    with (PROJECT/'review/a1_date_and_gap_coverage.csv').open(encoding='utf-8-sig',newline='') as f:coverage=list(csv.DictReader(f))
    with (PROJECT/'review/analysis_selection_profiles.csv').open(encoding='utf-8-sig',newline='') as f:selection=list(csv.DictReader(f))
    with (PROJECT/'behavior_flow/primary_candidate_outcomes.csv').open(encoding='utf-8-sig',newline='') as f:o=list(csv.DictReader(f))
    observed=[r for r in o if r['fully_observed']=='True']
    patterns={code:sum(int(float(r['first_outcome_date_active']))==int(code[0]) and int(float(r['second_outcome_date_active']))==int(code[1]) for r in observed) for code in ['00','10','01','11']}
    font=Path('C:/Windows/Fonts/malgun.ttf')
    if font.exists():font_manager.fontManager.addfont(str(font));plt.rcParams['font.family']=font_manager.FontProperties(fname=str(font)).get_name()
    plt.rcParams['axes.unicode_minus']=False
    fig,axes=plt.subplots(1,2,figsize=(14,6.3),gridspec_kw={'width_ratios':[1.55,1]})
    colors=['#DDE3E9','#8AA3BE','#334B68'];rows=b['flow'][1:];ys=list(range(len(rows)));left=[0]*len(rows)
    for key,label,color in zip(['no_learning_share','one_learning_day_share','two_plus_learning_days_share'],['기록 없음','1일 기록','2일 이상 기록'],colors):
        values=[100*r[key] for r in rows];axes[0].barh(ys,values,left=left,color=color,label=label,height=.62)
        for y,v,l in zip(ys,values,left):
            if v>=7:axes[0].text(l+v/2,y,f'{v:.1f}%',ha='center',va='center',fontsize=10,color='white' if color==colors[-1] else '#24364B')
        left=[x+y for x,y in zip(left,values)]
    axes[0].set_yticks(ys,[f"{r['segment']}  n={r['baseline_users']:,}" for r in rows]);axes[0].invert_yaxis();axes[0].set_xlim(0,100);axes[0].set_xlabel('고정 기준집단의 비율 (%)');axes[0].set_title('추적 4일의 관측 학습 날짜 수',loc='left',fontweight='bold');axes[0].legend(loc='upper center',bbox_to_anchor=(.5,-.14),ncol=3,frameon=False,fontsize=10)
    labels=['D1·D2 없음','D1만','D2만','양일'];values=[100*patterns[c]/len(observed) for c in ['00','10','01','11']]
    axes[1].barh(range(4),values,color=[colors[0],colors[1],colors[1],colors[2]],height=.6)
    axes[1].set_yticks(range(4),labels);axes[1].invert_yaxis();axes[1].set_xlim(0,70);axes[1].set_xlabel('A1 완전 관측 2,880명의 비율 (%)');axes[1].set_title('재개 후 다음 두 날짜의 행동',loc='left',fontweight='bold')
    for y,(v,c) in enumerate(zip(values,['00','10','01','11'])):axes[1].text(v+.8,y,f'{patterns[c]:,}명 · {v:.1f}%',va='center',fontsize=10)
    for ax in axes:
        ax.spines[['top','right','left']].set_visible(False);ax.tick_params(axis='y',length=0);ax.set_axisbelow(True);ax.grid(axis='x',color='#EEF1F4')
    fig.suptitle('기준 2013.03.01~07 UTC / 추적 03.08~11 UTC',x=.5,y=.985,fontsize=11,color='#56687B')
    fig.tight_layout(rect=[0,.025,1,.96]);fig.savefig(ROOT/'최종_행동흐름.png',dpi=180,bbox_inches='tight');plt.close(fig)
    def m(key):return metrics[key]['display']
    def link(name):return (ROOT/name).as_posix()
    table='\n'.join(f"| {r['segment']} | {r['baseline_users']:,} | {r['no_learning_users']:,} | {r['one_learning_day_users']:,} | {r['two_plus_learning_days_users']:,} | {r['two_plus_learning_days_share']:.1%} |" for r in b['flow'])
    pattern_table='\n'.join(f'| {label} | {patterns[c]:,} | {patterns[c]/len(observed):.1%} |' for c,label in zip(['00','10','01','11'],labels))
    sample_table='\n'.join(f"| +{r['mde']*100:.0f}%p | {r['target_power']:.0%} | {r['n_per_arm']:,} | {r['n_total']:,} |" for r in plan['scenarios'])
    report=f'''# 학습 재개 이후 반복학습을 연결하는 코호트 분석

최종 정리 2026-10-13. v3 고정 세그먼트, 역사적 학습 기록 분석과 실험 제안.

## 의사결정 요약

주후보는 하루 이상의 완전 UTC 날짜에 학습 기록이 없다가 재개한 습관 형성형 A1이다. 재개 다음 두 날짜를 모두 관측한 {m('a1_observed')}명 중 {m('a1_successes')}명({m('a1_rate')})이 추가 학습했다. 남은 54.4%에서 두 날짜의 추가 학습이 관측되지 않았다는 사실을 문제 지점으로 삼아, 재개 직후 다음 학습일 계획을 돕는 앱 안 안내를 제안한다. 이 비율은 개선 가능한 사용자 비율이나 안내의 효과를 뜻하지 않는다.

활동량을 고려한 세션 간격 변동성과 이후 반복학습에는 탐색적 연관성이 있었다. 같은 단어 성과 개선과 이후 반복학습의 뚜렷한 관계는 확인하지 못했다. 직접 단어 복습 간격 효과는 작고 가중 방식에 의존했다. 따라서 특정 복습 간격이나 정답률 개선 임계값으로 첫 실험 대상을 추가 선정하지 않는다.

현재 자료로 수행하기로 한 분석과 1~5번 마무리 산출물을 완성했다. 실제 서비스 실험은 배정·노출 로그와 최신 대상 데이터가 없어 미실행이다.

## 1. 문제와 측정 범위

NSM은 7일 중 4일 이상 학습한 사용자 수다. 기준 주간의 달성자는 {m('baseline_nsm')}명이다. 기준 주간 2013-03-01~07 UTC의 활성자 {m('overall_baseline_users')}명을 고정하고 03-08~11의 네 완전 날짜를 추적했다. 추적 중 1일 이상 학습자는 29,240명(35.5%), 2일 이상 학습자는 {m('overall_two_plus_learning_days_users')}명({m('overall_repeat_rate')})이다. 후속 7일 NSM·D7·D30은 이 추적으로 검증하지 않았다.

가입일은 없으며 첫 관측일을 가입일로 간주하지 않는다. 같은 사용자+timestamp는 추정 세션이다. session_seen은 노출·응답 시도 수이고 고유 문항·단어 수와 다르다. 완전 중복 81행을 제거한 기준 주간 집계는 기존 v3 사용자 집계와 일치했다.

## 2. 고정 기준집단의 행동 차이

| 집단 | 기준 인원(명) | 추적 기록 없음(명) | 1일 기록(명) | 2일 이상 기록(명) | 2일 이상 비율(%) |
|---|---:|---:|---:|---:|---:|
{table}

습관 형성형은 기준 주간 활동 2~3일이며 마지막 학습이 3/6 또는 3/7인 집단이다. 기존 세그먼트 차이 검정은 탐색적으로 수행했고, 습관 형성형 대 최근 단발형 차이와 습관 형성형 대 멈춤-꾸준형의 보정 후 비유의 결과를 구분했다. 행동 비율이 높다는 이유만으로 개입 효과가 가장 크다고 판단하지 않는다.

![고정 기준집단과 A1의 관측 행동]({link('최종_행동흐름.png')})

왼쪽은 같은 추적 네 날짜, 오른쪽은 A1의 첫 학습 다음 두 날짜를 모두 관측한 표본이다. 서로 다른 분모의 그림을 효과 비교로 사용하지 않는다.

## 3. 다음 학습이 끊기는 지점

기존 첫 후속 학습 전체 A에는 전날에도 학습한 사람이 포함된다. A의 3/8·9 첫 학습자 5,679명 중 2,704명(47.6%)이 D1·D2 중 학습했다. 전날 학습자 A0를 제외한 재개자 A1의 완전 관측 표본은 {m('a1_observed')}명이고 추가 학습은 {m('a1_successes')}명({m('a1_rate')}, 개별 Wilson 95% CI 43.7~47.4%)이다.

| A1 다음 두 날짜의 흐름 | 인원 | 비율 |
|---|---:|---:|
{pattern_table}

역사적 A1 전체 {m('a1_candidates')}명 중 3/10·11 재개자 1,929명은 두 날짜 결과가 미완전 관측이다. 결과 실패·0%로 바꾸지 않았다. 이번 마무리에서 원본의 A1 첫 학습 이벤트 timestamp와 직전 학습 timestamp를 전원 추출해 자격 날짜와 대조했다. 이는 실험 배정이나 레슨 완료 로그가 아니다.

## 4. 가설별 결과와 활용

| 질문 | 주요 근거 | 결론과 활용 |
|---|---|---|
| 세션 간격 변동성과 반복학습 | 습관 형성형 {cv['models'][1]['n']:,}명, log(1+CV) 1SD당 OR {m('cv_or')} (CI {m('cv_low')}~{m('cv_high')}). 30분 세션 정의 {cv['models'][3]['n']:,}명, OR {m('cv30_or')} | 작은 간격 변동과 반복학습의 탐색적 연관성. 표본·세션 정의·척도에 민감하며 인과 효과 아님 |
| 전체 초반·후반 정답률 변화 | 습관 형성형 {acc['models'][1]['n']:,}명, +10%p당 OR {m('allacc_or')} (CI {acc['models'][1]['ci_low']:.3f}~{acc['models'][1]['ci_high']:.3f}) | 뚜렷한 관계를 확인하지 못함. 같은 단어 개선과 별도 지표 |
| 같은 단어 성과 개선 | 습관 형성형 {word['models'][0]['n']:,}명, +10%p당 OR {m('word_or')} (CI {m('word_low')}~{m('word_high')}), Holm p=1.000 | 원래 지표 재현 완료. 개선 기반 대상 추가의 근거 부족, 효과 0 입증 아님 |
| 직접 단어 복습 간격 | {word['models'][4]['users']:,}명·{word['models'][4]['n']:,}쌍. 간격비 2배당 노출 가중 +{m('gap_weighted')}%p, 동일 가중 +{m('gap_unweighted')}%p | 노출 가중만 유의하고 효과가 작음. 최적 간격 제안 불가 |
| 비활동 2일·3일 | 3/11 종료 {m('inactive_2day_users')}명 대 {m('inactive_3day_users')}명, 추가 {m('added_exact2_users')}명 | 대상 규모 변화 확인. 과거 시점의 개입 대상이나 최적 기준으로 재사용하지 않음 |

지표마다 대상·기간·결과가 다르다. 서로 다른 표본의 OR나 p값으로 예측력 우열을 정하지 않는다. 같은 단어·언어를 맞추면 콘텐츠 구성을 제한하지만 난도·사용자 선택·반복 노출의 교란이 모두 사라지지는 않는다. 기존 검정군은 작업별 탐색 검정군이며 프로젝트 전체 확증 분석이 아니다.

## 5. 첫 실험 제안

A1 첫 학습 이벤트 직후 다음 학습일을 정하는 카드 1회를 제공한다. ‘다음 학습을 미리 정해볼까요?’와 ‘학습일 정하기 / 나중에’ 선택을 제안한다. 대조군은 기존 학습 화면을 사용한다. 사용자 단위 1:1 무작위 배정 후 안내 미노출·미선택자도 해당 군에 유지한다. 푸시·메일을 함께 추가하지 않는다.

주 지표는 D0 다음 두 완전 UTC 날짜 D1·D2의 추가 학습 비율이며, 분모는 모든 배정 사용자다. 두 군 비율 차이와 양측 검정·95% 구간을 제시한다. 학습 수집이 미확인이면 0으로 처리하거나 분모에서 제거하지 않는다. 상세 배정·화면·로그·경계·판정 규칙은 [A1 실험 명세]({link('A1_실험명세서.md')})와 [측정 명세]({link('측정과_로그_명세.md')})에 기록했다.

정확히 2일 비활동 이후 복귀 유도 B는 별도 후보로 남긴다. B의 22.6%와 A1의 {m('a1_rate')}는 대상·시점·결과 기간이 달라 효과 순위를 비교할 수 없다. A1/B 중복 3,298명에 대한 향후 교차 개입 방지가 필요하다.

## 6. 표본과 실행 가능성

기준률 {plan['historical_baseline']:.1%}, 양측 α=0.05, 1:1 배정의 정규근사 시나리오다. 블록 4명에 맞춰 올림했다.

| 최소 탐지 폭 가정 | 검정력 | 군별 표본 | 총 표본 |
|---|---:|---:|---:|
{sample_table}

초기 작성 가정 +3%p·80%에서는 군별 {plan['default']['n_per_arm']:,}명, 총 {plan['default']['n_total']:,}명이다. 이 개선 폭은 사업적 최소 의미 효과로 합의된 값이 아니다. 역사적 후보 4,809명만으로 새 실험 표본을 채우거나 효과를 측정할 수 없다.

모집 최소 14일·최대 28일, 마지막 배정자의 D1·D2 추적 뒤 2일 지연 대기를 제안한다. 일별 새 고유 A1 500명 가정이면 모집 18일·결과 확인 22일이며, 100명 가정은 28일 내 목표 표본에 미달한다. 실제 자격 모수·유입량·개시일은 미확인이므로 확정 실행 일정은 제시하지 않는다. 표본 미달이나 가드레일 문제가 있으면 그 사실을 보고하고 다른 지표의 유의성으로 성공 판정을 대체하지 않는다.

방법: [두 독립 비율의 정규근사 검정력](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.power_proportions_2indep.html). 계산과 입력 변경 검증은 [표본 수 산정 파일]({link('A1_실험표본수와_기간산정.xlsx')})에서 확인할 수 있다.

## 7. 완료 범위와 남은 실행 조건

기초 코호트·세그먼트·단기 행동·비활동·규칙성·성과·행동 흐름 분석, A1 대상 정의, 실험 제안, 측정 참조, 표본 수 시나리오, 최종 보고서와 재실행 안내를 완료했다. 후속 표본 수는 독립 정수 탐색과 이항 모의 검증을 수행했고, 모의 검증은 실제 실험 효과와 구분했다. 보고서 숫자는 원천 결과에 연결한 53개 주장 목록으로 추적한다.

실제 서비스에는 최신 기준집단·신규 자격 규모, 서버 배정·앱 카드·로그 연결, 사업적 MDE·운영 기준 확인이 필요하다. 현재 학습 데이터에 없는 배정·노출·장기 유지 결과를 생성하지 않았다. 실험을 시행한 뒤에만 개입 효과를 평가할 수 있다.

[읽는 순서와 산출물 인덱스]({(PROJECT/'최종_산출물_인덱스.md').as_posix()}) · [OneDrive 재실행 안내]({link('OneDrive_재실행_안내.md')})
'''
    (ROOT/'최종_코호트분석_보고서.md').write_text(report,encoding='utf-8')
    scope='''\n**해석 범위:** 학습·비활동·NSM은 공개 단어 lesson/practice 파일의 유효 기록 기준이다. 기록 없음은 앱 미사용·모든 학습 부재·영구 이탈을 뜻하지 않는다. 모든 세션 coverage와 최초 학습 포함 여부는 미검증이다. 45.6%는 초기 재개자의 조건부 비율이며 실제 모집 대상의 대조 기준률이 아니다.\n'''
    report=report.replace('## 의사결정 요약',scope+'\n## 의사결정 요약').replace('NSM은 7일 중 4일 이상 학습한 사용자 수다.','현재 NSM은 7일 중 4일 이상 관측 학습 기록이 있는 사용자 수다.')
    date_table='\n'.join(f"| {r['value']} | {int(r['candidate_users']):,} | {int(r['fully_observed_users']):,} | {int(float(r['successes'])):,} | {float(r['rate']):.1%} |" if r['rate'] else f"| {r['value']} | {int(r['candidate_users']):,} | {int(r['fully_observed_users']):,} | 미확인 | 미확인 |" for r in coverage if r['grouping']=='eligibility_date_utc')
    gap_table='\n'.join(f"| {r['value']} | {int(r['candidate_users']):,} | {int(r['fully_observed_users']):,} | {int(float(r['successes'])):,} | {float(r['rate']):.1%} |" if r['rate'] else f"| {r['value']} | {int(r['candidate_users']):,} | {int(r['fully_observed_users']):,} | 미확인 | 미확인 |" for r in coverage if r['grouping']!='eligibility_date_utc')
    selected=[]
    for name in ['세션 간격','전체 정답률','같은 단어 개선']:
        yes=next(r for r in selection if r['analysis']==name and r['eligible']=='True');no=next(r for r in selection if r['analysis']==name and r['eligible']=='False')
        selected.append(f"| {name} | {int(yes['users']):,} | {int(no['users']):,} | {float(yes['repeat_rate']):.1%} | {float(no['repeat_rate']):.1%} |")
    robust_table='\n'.join(f"| {r['model']} | {r['n']:,} / {r.get('users',r['n']):,} | {r.get('estimate',r.get('odds_ratio')):.3f} | {r['ci_low']:.3f}~{r['ci_high']:.3f} | {r['p_holm']:.3g} | {r['unit']} |" for r in robust['models'])
    profiles=robust['selection_profiles']
    def share(include,dimension,value):return next(r['share'] for r in profiles if r['analysis']=='CV' and r['included']==include and r['dimension']==dimension and r['value']==value)
    composition=f"CV 포함자의 주 학습 언어 영어 비중은 {share(True,'dominant_language','en'):.1%}, 제외자는 {share(False,'dominant_language','en'):.1%}; 최초 관측 3/1 비중은 {share(True,'first_active','2013-03-01'):.1%} 대 {share(False,'first_active','2013-03-01'):.1%}다. 전체 정답률 변화 표본은 양쪽 기간 노출 조건 때문에 최초 관측이 모두 3/1~3이며, 제외자는 3/4~6 최초 관측이 다수다. 이 선택 차이는 가입일이나 제외의 인과 효과로 해석하지 않는다."
    additions=f'''## 4-1. 기준률 적용 범위와 추가 강건성

A1의 첫 재개 날짜와 비활동 기간별 D1·D2 관측이다. 단위는 사용자 명·관측 비율 %이며, 미확인 결과를 0으로 대체하지 않는다.

| A1 재개 날짜(UTC) | 후보(명) | 완전 관측(명) | 추가 기록(명) | 완전 관측 중 비율(%) |
|---|---:|---:|---:|---:|
{date_table}

| 직전 비활동(완전 UTC 날짜 수) | 후보(명) | 완전 관측(명) | 추가 기록(명) | 완전 관측 중 비율(%) |
|---|---:|---:|---:|---:|
{gap_table}

완전 관측은 후보의 59.9%이며 미완전 관측은 40.1%다. 45.6%는 3/8·9 및 비활동 1~2일의 조건부 비율이다. 자격 1일 이상은 유지하되 신규 서비스에서 1일/2일/3일 이상·재개 날짜·지원 앱 구성과 기준률을 사전 관측으로 다시 확인한다. Wilson 구간에 따른 표본 시나리오 8,640~8,716명은 모집단 이동 오차를 포함하지 않는다.

습관 형성형 고정 14,583명 안에서 분석 표본 선택과 추적 2013-03-08~11 UTC 반복 기록(2일 이상)의 관계를 기술한다.

| 분석 | 포함(명) | 제외(명) | 포함자 반복률(%) | 제외자 반복률(%) |
|---|---:|---:|---:|---:|
{chr(10).join(selected)}

{composition}

원본 전체 기간 history_seen>1,000인 104명(기준 주간만 적용하면 92명)을 확인했다. 이 기준은 자동화 계정 판정이 아니며 미래 정보가 포함된 품질 민감도에만 사용했다. 주 분석 5개 재적합은 저장 추정값·구간·p와 일치했다. 사전 정한 제외·언어 보정의 추가 8개 모형을 한 탐색 검정군으로 Holm 보정했다.

| 보완 모형 | 분석행 / 사용자 | 추정값 | 개별 95% CI | Holm p | 단위 |
|---|---:|---:|---:|---:|---|
{robust_table}

가중 상위 1% {robust['top_users']}명의 노출 가중 비중은 {robust['top_weight_share']:.1%}였다. 이들을 제외해도 작은 가중 효과가 남으며, 동일 가중은 여전히 불명확하다. 특정 헤비 사용자 탓으로 단정하지 않는다. 104명 제외 후 CV OR≈0.706, 같은 단어 OR≈1.020으로 기존 해석은 유지한다. 언어·최초 관측 날짜별 포함/제외 구성은 [선택 표본 프로필]({(PROJECT/'corrections/selection_language_time_profiles.csv').as_posix()})에 전부 저장했다.

언어 보정 CV 제곱항 계수 {robust['shape_diagnostic']['estimate']:.4f}(CI {robust['shape_diagnostic']['ci_low']:.4f}~{robust['shape_diagnostic']['ci_high']:.4f}), 진단 p={robust['shape_diagnostic']['p']:.4f}로 선형 형태의 추가 검토가 필요하다. 주 분석의 단일 OR는 로그 선형 모형의 요약이며 모든 CV 범위의 일정한 효과·최적 규칙성 기준을 의미하지 않는다. 곡선 진단은 별도 형태 진단으로, 유의한 모형을 선택해 주 결과를 교체하지 않는다. 한 기준 주간뿐이므로 시간 외 검증과 가입/채널 보정은 새 데이터 대기다.

'''
    report=report.replace('## 5. 첫 실험 제안',additions+'## 5. 첫 실험 제안')
    report=report.replace('## 7. 완료 범위와 남은 실행 조건','''## 6-1. 보조 NSM과 실행 차단 조건

보조 NSM은 모든 배정자를 분모로 D1~D7 중 유효 서비스 학습 날짜 4일 이상을 측정한다. 구간 [D1 00:00,D8 00:00), 동결 판정 D8+48시간 이후다. 주 결과는 D3+48시간 이후이며 서로 별도로 확정한다. 미확인은 제외하거나 0으로 채우지 않는다. 단기 지표 개선이 NSM 개선을 뜻하지 않는다. 현재 추적 4일로 보조 NSM을 계산하지 않았다.

날짜 선택은 주 결과 UTC 구간과 겹치는 사용자 현지 날짜/가능 시간으로 한정한다. 실제 서비스 최초 학습을 포함한 완료 세션 계약·coverage·기준률 재산출·MDE/가드레일 사업 승인·자격 모수/유입량·카드 사용성·배정/노출 연결을 모두 검증해야 한다. 설정 gate는 현재 null이며 실행은 차단 상태다.

## 7. 완료 범위와 남은 실행 조건''')
    report=report.replace('보고서 숫자는 원천 결과에 연결한 53개 주장 목록으로 추적한다.','보고서 숫자는 원천 결과에 연결한 53개 주장과 표의 집단·분모·단위·기간 계약으로 대조한다. 기본 Verify는 기존 manifest와 최신 입력 해시를 읽기 전용으로 검사하며 Build에서만 새 manifest를 생성한다.')
    (ROOT/'최종_코호트분석_보고서.md').write_text(report,encoding='utf-8')
    summary=f'''# 코호트 분석 핵심 결론

2026-10-13. 역사적 데이터 분석과 실험 제안서 마무리 완료.

- 기준 주간 활성 사용자 {m('overall_baseline_users')}명, NSM 달성 {m('baseline_nsm')}명. 추적은 네 완전 UTC 날짜다.
- 습관 형성형 {m('habit_baseline_users')}명의 추적 학습 없음 {m('habit_no_learning_users')}명, 1일 학습 {m('habit_one_learning_day_users')}명, 2일 이상 학습 {m('habit_two_plus_learning_days_users')}명.
- 주후보 A1은 하루 이상 비활동 후 첫 후속 학습을 한 재개자다. 대상 {m('a1_candidates')}명 중 완전 관측 {m('a1_observed')}명에서 {m('a1_successes')}명({m('a1_rate')})이 다음 두 날짜 중 추가 학습했다.
- 세션 간격 변동성과 반복학습은 탐색적 연관성이 있다. 같은 단어 성과 개선과 반복학습의 뚜렷한 관계는 확인하지 못했고 직접 복습 간격 효과는 작고 가중 방식에 의존했다.
- 첫 실험은 재개 직후 다음 학습일 계획 카드 1회다. 주 지표는 D1·D2의 추가 학습 비율이고 모든 배정자를 분모에 포함한다.
- +3%p·80% 검정력 가정: 총 {plan['default']['n_total']:,}명. 실제 신규 자격 유입량·개시일이 없어 실행 일정은 미정이다.
- 실제 배정·노출·개입 효과 검증은 미실행이다. 실험 시스템·최신 데이터 연결이 후속 실행 조건이다.

[최종 보고서]({link('최종_코호트분석_보고서.md')}) · [실험 명세]({link('A1_실험명세서.md')})
'''
    (ROOT/'핵심결론_요약.md').write_text(summary,encoding='utf-8')
    summary=summary.replace('역사적 데이터 분석과 실험 제안서 마무리 완료.','공개 관측 기록 분석·검토 수정 완료. 실제 서비스 실행 조건 검증 대기.').replace('NSM 달성','관측 기록 NSM 달성')
    summary+='\n45.6%는 3/8·9 초기 재개·비활동 1~2일 표본의 조건부 비율이다. 실제 대상 기준률 재산출이 필요하다. 104명/가중 상위1% 제외에서도 주 해석은 유지됐으나 CV 곡률 진단 때문에 단일 OR를 전 범위에 적용하지 않는다. 서비스 coverage·사업 기준·모집 규모 gate는 미확인으로 실행 차단 상태다. 후속 D1~D7 4일 이상 NSM은 신규 로그에서 별도로 측정한다.\n'
    (ROOT/'핵심결론_요약.md').write_text(summary,encoding='utf-8')
    print('Final report, summary and source-backed behavior figure saved.')
if __name__=='__main__':main()
