"""Follow-up inference from the saved v3 cohort; no raw-source reaggregation."""
from pathlib import Path
from itertools import combinations
from statistics import NormalDist
import hashlib
import json
import math
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'statistics'
SEGMENTS = ['꾸준형', '습관 형성형', '최근 단발형', '멈춤-꾸준형', '멈춤-몰입형', '멈춤-저활동형']
DATES = [f'2013-03-{d:02d}' for d in range(8, 12)]
LABELS = {'return_4d': '4일 내 재학습', 'repeat_4d': '4일 중 2일 이상 학습',
          'D1': '복귀 D+1 학습', 'D2': '복귀 D+2 학습', 'D3': '복귀 D+3 학습',
          'within2': '복귀 뒤 2일 내 추가 학습'}
Z = NormalDist().inv_cdf(.975)


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def wilson(x, n):
    p = x / n
    den = 1 + Z * Z / n
    mid = (p + Z * Z / (2 * n)) / den
    half = Z * math.sqrt(p * (1-p)/n + Z*Z/(4*n*n)) / den
    return max(0., mid-half), min(1., mid+half)


def newcombe(x1, n1, x2, n2):
    p1, p2 = x1/n1, x2/n2
    l1, u1 = wilson(x1, n1)
    l2, u2 = wilson(x2, n2)
    return (p1-p2-math.hypot(p1-l1, u2-p2), p1-p2+math.hypot(u1-p1, p2-l2))


def log_two_sided_normal_p(z):
    """erfc in the ordinary range; Mills expansion only after underflow."""
    z = abs(z)
    p = math.erfc(z/math.sqrt(2))
    if p > 0:
        return math.log(p)
    # Here z > 38: the successive terms decrease rapidly.
    term = series = 1.
    for k in range(1, 13):
        term *= -(2*k-1)/(z*z)
        series += term
    return math.log(2)-.5*z*z-.5*math.log(2*math.pi)-math.log(z)+math.log(series)


def holm_log(logps):
    order = np.argsort(logps)
    result = np.empty(len(logps))
    running = -math.inf
    for rank, i in enumerate(order):
        running = max(running, float(logps[i]) + math.log(len(logps)-rank))
        result[i] = min(0., running)
    return result


def plabel(logp):
    return '<1e-300' if logp < math.log(1e-300) else f'{math.exp(logp):.4g}'


def main():
    OUT.mkdir(exist_ok=True)
    metadata = json.loads((ROOT/'results_retention.json').read_text(encoding='utf-8'))
    sources = ['user_retention_cohort.csv', 'segment_retention_summary.csv', 'first_return_cohorts.csv']
    hashes = {name: digest(ROOT/name) for name in sources}
    assert all(hashes[n] == metadata['outputs'][n]['sha256'] for n in sources)
    u = pd.read_csv(ROOT/sources[0], low_memory=False)
    saved_summary = pd.read_csv(ROOT/sources[1]).set_index('segment')
    saved_cohorts = pd.read_csv(ROOT/sources[2]).set_index(['segment', 'first_return_date'])
    assert len(u) == 82467 and u.user_id.is_unique and set(u.segment) == set(SEGMENTS)
    active = u[[f'active_{d}' for d in DATES]].to_numpy(dtype=int)
    assert np.isin(active, [0, 1]).all()
    totals = active.sum(axis=1)
    returned = totals > 0
    repeated = totals >= 2
    first_idx = np.where(returned, active.argmax(axis=1), -1)
    reconstructed = pd.Series([DATES[i] if i >= 0 else '' for i in first_idx])
    assert reconstructed.equals(u.first_return_date.fillna(''))
    assert np.array_equal(returned.astype(int), u.returned_4d)
    assert np.array_equal(repeated.astype(int), u.returned_2plus_days)
    rows = []
    def add(scope, date, metric, segment, n, x):
        observable = x is not None
        low, high = wilson(x, n) if observable and n else (None, None)
        rows.append(dict(scope=scope, first_return_date=date, metric=metric,
                         metric_label=LABELS[metric], segment=segment, n=int(n),
                         successes=int(x) if observable else None, observable=observable,
                         rate=x/n if observable and n else None, ci95_low=low, ci95_high=high))
    for segment in ['전체'] + SEGMENTS:
        mask = np.ones(len(u), dtype=bool) if segment == '전체' else u.segment.eq(segment).to_numpy()
        n = mask.sum()
        for metric, outcome in [('return_4d', returned), ('repeat_4d', repeated)]:
            x = int(outcome[mask].sum())
            add('baseline', '', metric, segment, n, x)
            if segment != '전체':
                col = 'returned_users' if metric == 'return_4d' else 'repeat_users'
                assert x == saved_summary.loc[segment, col]
                assert n == saved_summary.loc[segment, 'cohort_users']
        for j, date in enumerate(DATES):
            group = mask & (first_idx == j)
            n = int(group.sum())
            source = saved_cohorts.loc[(segment, date)]
            assert n == source.return_cohort_users
            for k in [1, 2, 3]:
                x = int(active[group, j+k].sum()) if j+k < 4 else None
                add('same_return_date', date, f'D{k}', segment, n, x)
                if x is None:
                    assert pd.isna(source[f'D{k}_active_users'])
                else:
                    assert x == source[f'D{k}_active_users']
            x = int((active[group, j+1:j+3].sum(axis=1) > 0).sum()) if j <= 1 else None
            add('same_return_date', date, 'within2', segment, n, x)
            assert (x == source.within_2days_repeat_users) if x is not None else pd.isna(source.within_2days_repeat_users)
    pairs = []
    strata = sorted(set((r['scope'], r['first_return_date'], r['metric']) for r in rows if r['observable']))
    for scope, date, metric in strata:
        group = {r['segment']: r for r in rows if (r['scope'],r['first_return_date'],r['metric']) == (scope,date,metric)}
        for a, b in combinations(SEGMENTS, 2):
            ra, rb = group[a], group[b]
            x1,n1,x2,n2 = ra['successes'],ra['n'],rb['successes'],rb['n']
            pooled = (x1+x2)/(n1+n2)
            expected = [n1*pooled,n1*(1-pooled),n2*pooled,n2*(1-pooled)]
            assert min(expected) >= 5, 'Sparse comparison requires an exact test'
            z = (x1/n1-x2/n2)/math.sqrt(pooled*(1-pooled)*(1/n1+1/n2))
            low,high = newcombe(x1,n1,x2,n2)
            logp = log_two_sided_normal_p(z)
            pairs.append(dict(scope=scope,first_return_date=date,metric=metric,metric_label=LABELS[metric],
                              group_a=a,group_b=b,n_a=n1,n_b=n2,x_a=x1,x_b=x2,
                              rate_a=x1/n1,rate_b=x2/n2,diff_pp=100*(x1/n1-x2/n2),
                              ci95_diff_low_pp=100*low,ci95_diff_high_pp=100*high,
                              z=z,log_p_raw=logp,log10_p_raw=logp/math.log(10),p_raw=math.exp(logp),
                              p_raw_label=plabel(logp),min_expected=min(expected)))
    assert len(pairs) == 150
    adjusted = holm_log([r['log_p_raw'] for r in pairs])
    for r,logp in zip(pairs,adjusted):
        r.update(p_holm=math.exp(logp),log10_p_holm=logp/math.log(10),p_holm_label=plabel(logp),
                 significant_holm_005=bool(logp < math.log(.05)),family_size=len(pairs))
    # Numerical checks independent of the stored analysis: known reference and score inversion.
    assert np.allclose(newcombe(7,34,1,34), [.019, .340], atol=.001)
    assert np.allclose(np.exp(holm_log(np.log([.01,.04,.03]))), [.03,.06,.06])
    assert abs(math.exp(log_two_sided_normal_p(Z))-.05) < 1e-12
    for r in rows:
        if r['observable']:
            assert 0 <= r['ci95_low'] <= r['rate'] <= r['ci95_high'] <= 1
            for bound in [r['ci95_low'],r['ci95_high']]:
                if 0 < bound < 1:
                    assert abs((r['rate']-bound)**2/(bound*(1-bound)/r['n'])-Z*Z) < 1e-8
    for r in pairs:
        assert r['ci95_diff_low_pp'] <= r['diff_pp'] <= r['ci95_diff_high_pp']
        assert math.log(max(r['p_holm'],1e-300)) >= math.log(max(r['p_raw'],1e-300))-1e-12
        reverse = newcombe(r['x_b'],r['n_b'],r['x_a'],r['n_a'])
        assert np.allclose(reverse,[-r['ci95_diff_high_pp']/100,-r['ci95_diff_low_pp']/100])
    checks = dict(source_hashes_match=True,unique_baseline_users=True,binary_activity=True,
                  first_return_reconstructed=True,baseline_summary_reconciled=True,
                  all_return_date_counts_reconciled=True,unobserved_cells_preserved=True,
                  expected_cell_counts_at_least_5=True,wilson_score_inversion=True,
                  newcombe_reference_case=True,newcombe_antisymmetry=True,holm_reference_case=True,
                  normal_tail_reference=True,all_150_tests_in_one_holm_family=True)
    result = dict(analysis_date='2026-10-13',baseline_window='2013-03-01 through 2013-03-07 UTC',
                  followup_window='2013-03-08 through 2013-03-11 UTC',source_hashes=hashes,
                  methods={'proportions':'Wilson score 95% confidence interval',
                           'difference':'Newcombe unpaired score interval; 95% pointwise, not multiplicity adjusted',
                           'test':'Two-sided pooled two-proportion z test, equivalent to Pearson chi-square without continuity correction',
                           'multiplicity':'Holm correction over all 150 pairwise tests (30 baseline + 120 same-return-date)',
                           'interpretation':'Exploratory user-level association in this historical extract; conditional returner comparisons are not causal',
                           'p_underflow':'Numeric p may underflow to zero. Use log10_p fields and labels for extremely small p-values.'},
                  checks=checks,rates=rows,comparisons=pairs,
                  test_count=len(pairs),significant_count=sum(r['significant_holm_005'] for r in pairs))
    (OUT/'statistics_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    pd.DataFrame(rows).to_csv(OUT/'proportions_with_ci.csv',index=False,encoding='utf-8-sig',float_format='%.14g')
    pd.DataFrame(pairs).to_csv(OUT/'pairwise_tests_holm.csv',index=False,encoding='utf-8-sig',float_format='%.14g')
    pd.DataFrame([r for r in rows if r['scope']=='same_return_date']).to_csv(OUT/'same_return_date_with_ci.csv',index=False,encoding='utf-8-sig',float_format='%.14g')
    write_report(result)
    print(json.dumps({'checks':checks,'tests':len(pairs),'significant':result['significant_count'],
                      'min_expected':min(r['min_expected'] for r in pairs)},ensure_ascii=False,indent=2))


def write_report(result):
    def get_rate(segment, metric, date=''):
        return next(r for r in result['rates'] if r['segment']==segment and r['metric']==metric and r['first_return_date']==date)
    def rate_ci(r):
        return f"{r['rate']:.1%} ({r['ci95_low']:.1%}~{r['ci95_high']:.1%})"
    def comp(a,b,metric,date=''):
        return next(r for r in result['comparisons'] if r['group_a']==a and r['group_b']==b and r['metric']==metric and r['first_return_date']==date)
    lines = ['# 코호트 후속 분석: 같은 복귀일 비교와 통계 검증',
      '', '분석일: 2026-10-13. 기준: v3의 6개 세그먼트. 기준기간 2013-03-01~07, 추적기간 03-08~11, UTC.',
      '', '## 1. 결론', '',
      '- 습관 형성형은 최근 단발형보다 전체 반복학습률이 12.34%p 높았다. 같은 복귀일의 2일 내 추가 학습에서도 3/8은 9.11%p, 3/9는 10.08%p 높았고 Holm 보정 후 유의했다.',
      '- 습관 형성형과 멈춤-꾸준형의 전체 반복학습률 차이는 2.15%p였으나 Holm 보정 후 유의하지 않았다(p=0.1811). 두 집단이 동등하다는 증거는 아니다.',
      '- 3/8 복귀자만 비교하면 멈춤-꾸준형의 2일 내 추가 학습률은 56.0%, 습관 형성형은 47.3%였다. 멈춤-꾸준형이 8.74%p 높았고 보정 p=0.0006303이었다. 3/9의 같은 비교는 유의하지 않았다.',
      '- 멈춤-꾸준형은 멈춤-몰입형보다 전체 반복학습률이 13.24%p 높았다. 3/8 복귀자의 2일 내 추가 학습 차이도 17.48%p로 컸다.',
      '', '이 결과는 습관 형성형의 다음 학습 연결과 멈춤-꾸준형의 재진입을 서로 다른 실험 후보로 다룰 근거다. 어느 집단이 개입에 더 반응하는지, 비용 대비 효과가 큰지는 확인하지 않았다.',
      '', '## 2. 전체 기준집단: 비율과 95% 신뢰구간', '',
      '분모는 각 세그먼트의 3/1~7 기준 인원 전체다. 재학습하지 않은 사용자도 포함한다. 괄호는 Wilson 95% 신뢰구간이다.', '',
      '| 세그먼트 | 기준 인원 | 4일 내 재학습률 (95% CI) | 2일 이상 학습률 (95% CI) |',
      '|---|---:|---:|---:|']
    for s in ['전체']+SEGMENTS:
        a,b=get_rate(s,'return_4d'),get_rate(s,'repeat_4d')
        lines.append(f"| {s} | {a['n']:,} | {rate_ci(a)} | {rate_ci(b)} |")
    lines += ['', '## 3. 같은 복귀일의 D+1 비교', '',
              '각 셀은 학습률과 분모 n이다. 동일 날짜에 복귀한 집단 사이를 비교한다. 날짜 간 차이를 검정한 결과가 아니다.', '',
              '| 세그먼트 | 3/8 복귀 → 3/9 학습 | 3/9 복귀 → 3/10 학습 | 3/10 복귀 → 3/11 학습 |',
              '|---|---:|---:|---:|']
    for s in SEGMENTS:
        rr=[get_rate(s,'D1',d) for d in DATES[:3]]
        lines.append('| '+s+' | '+' | '.join(f"{r['rate']:.1%} (n={r['n']:,})" for r in rr)+' |')
    lines += ['', '습관 형성형 − 최근 단발형의 D+1 차이는 3/8 복귀자 +6.41%p(p=0.000001603), 3/9 +8.06%p(p=0.0004007)로 보정 후 유의했다. 3/10은 +2.91%p(p=1.0000)로 유의하지 않았다. 모든 날짜에서 차이가 검증됐다고 표현하지 않는다.',
              '', '## 4. 같은 복귀일의 2일 내 추가 학습', '',
              'D+1 또는 D+2에 한 번 이상 학습한 비율이다. D+1과 D+2가 모두 관측되는 3/8·3/9 복귀자만 포함한다.', '',
              '| 세그먼트 | 3/8 복귀 (95% CI) | 3/9 복귀 (95% CI) |', '|---|---:|---:|']
    for s in SEGMENTS:
        lines.append(f"| {s} | {rate_ci(get_rate(s,'within2',DATES[0]))} | {rate_ci(get_rate(s,'within2',DATES[1]))} |")
    lines += ['', '## 5. 주요 차이와 다중 비교 보정', '',
              '차이는 A − B, 단위 %p. 신뢰구간은 보정 전 개별 95% 구간이며, 유의성은 전체 150개 비교에 대한 Holm 보정 p<0.05로 판단한다.', '',
              '| 범위·지표 | 집단 A | 집단 B | 차이 %p | 차이의 95% CI | Holm p | 판단 |', '|---|---|---|---:|---:|---:|---|']
    contrasts=[('습관 형성형','최근 단발형'),('습관 형성형','멈춤-꾸준형'),('멈춤-꾸준형','멈춤-몰입형')]
    for date,metric in [('', 'repeat_4d'),(DATES[0],'within2'),(DATES[1],'within2')]:
        for a,b in contrasts:
            r=comp(a,b,metric,date)
            label=('전체 · 반복학습' if not date else date[5:]+' 복귀 · 2일 내 추가 학습')
            lines.append(f"| {label} | {a} | {b} | {r['diff_pp']:+.2f} | {r['ci95_diff_low_pp']:+.2f}~{r['ci95_diff_high_pp']:+.2f} | {r['p_holm_label']} | {'유의' if r['significant_holm_005'] else '유의하지 않음'} |")
    lines += ['', '3/9 멈춤-꾸준형 대 멈춤-몰입형의 보정 p=0.04996은 0.05 경계에 가까워 강한 재현 근거로 강조하지 않는다. 신뢰구간과 차이 크기를 함께 읽는다.',
      '', '## 6. 분석 방법과 해석 범위', '',
      '- 사용자 단위의 이항 결과를 사용했다. 각 비교에서 사용자는 서로 다른 세그먼트에 속하며, 날짜별 행을 독립 사용자처럼 중복 계산하지 않았다.',
      '- 비율 구간은 Wilson score 95%, 비율 차이 구간은 독립 두 비율의 Newcombe 방법이다. [비율 구간 공식 문서](https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.proportion_confint.html), [차이 구간 공식 문서](https://www.statsmodels.org/dev/generated/statsmodels.stats.proportion.confint_proportions_2indep.html).',
      '- 양측 pooled 두 비율 z 검정을 사용했다. 모든 2×2 표의 최소 기대빈도는 57.82로 5 이상이었다.',
      '- 검정군은 전체집단 2지표×15쌍=30개와 같은 복귀일의 8개 날짜·지표 조합×15쌍=120개, 총 150개다. D+1은 3/8~10, D+2는 3/8~9, D+3은 3/8, 2일 내 추가 학습은 3/8~9를 검정했다.',
      '- 150개를 한 묶음으로 Holm 보정했다. 결과를 확인한 뒤 유리한 비교만 남겨 보정하지 않았다. 기존 결과를 본 뒤 수행한 탐색적 분석이며 사전등록 확증 분석은 아니다. [Holm 공식 문서](https://www.statsmodels.org/stable/generated/statsmodels.stats.multitest.multipletests.html).',
      '- 신뢰구간은 개별 95%이며 150개 전체의 동시 신뢰구간이 아니다. 따라서 구간이 0을 제외해도 Holm 보정 후 비유의일 수 있다. 판정과 구간은 서로 다른 보정 기준을 사용한다.',
      '- 신뢰구간·p는 독립 사용자와 이항 모형을 가정한 추론이다. 이 공개 데이터가 전체 듀오링고 사용자의 무작위 표본임을 보장하지 않으며, 표본 선택 편향이나 날짜·환경의 공통 영향은 구간에 반영하지 않는다. 추출 데이터 내 관측 비율 자체는 확정 집계값이다.',
      '- 같은 복귀일로 맞추면 달력 날짜와 이후 관측 기회가 같아진다. 그러나 기존 최근성·활동일 수·학습량이 같아지는 것은 아니다. 복귀자 조건에 따른 선택 편향도 남는다.',
      '- 복귀자 중 학습률과 기준집단 전체의 학습률은 분모가 다르므로 직접 우열 비교하지 않는다. 복귀율이 낮은 집단에서도 실제 복귀한 사람의 추가 학습률은 높을 수 있다.',
      '- 미관측은 0%로 처리하지 않았다. D0=100%는 집단 정의로 고정되므로 검정하지 않았다. D7/D30, 장기 이탈, 다음 주 NSM 및 개입 효과는 검증 범위 밖이다.',
      '- 작은 p가 효과의 실무적 크기를 뜻하지 않는다. %p 차이·대상 규모·후속 실험의 비용과 효과를 함께 판단한다.',
      '', '## 7. 검증 및 재현', '',
      '- 원천 CSV 3개의 SHA256을 기존 v3 기록과 대조했다.',
      '- 사용자별 4개 날짜의 활동으로 재학습·반복학습·첫 복귀일·D+1~D+3·2일 내 추가 학습을 재계산하고 기존 집계와 전수 대조했다.',
      '- 관측 불가 셀 보존, 사용자 중복, 2×2 기대빈도, Wilson 구간의 score 방정식, Newcombe 참고 사례 및 방향 대칭, Holm 참고 사례 등 14개 검증을 통과했다.',
      '- p가 부동소수점 범위보다 작으면 CSV 숫자 열은 0이 될 수 있다. 이 경우 p 라벨(<1e-300)과 log10_p 열을 사용한다. 수학적으로 p=0이라고 해석하지 않는다.',
      '- 재실행: 현재 OneDrive 프로젝트의 analyze_cohort_statistics.py를 실행하고, statistics/build_statistics_workbook.mjs를 실행한다. 첫 스크립트는 Python 표준 라이브러리·pandas·NumPy만 사용한다.',
      '', '## 8. 이어서 할 작업', '',
      '요청한 1번(같은 복귀일 비교)과 2번(신뢰구간·비교 검정)은 완료했다. 다음은 2일·3일 비활동 기준의 민감도 비교다. 그 뒤 기준 주간의 활동일 수·학습량 등을 고려한 규칙성 분석과 개입 실험안을 진행한다.',
      '', '파일: 코호트_복귀일비교_통계검증.xlsx(요약·복귀일 비교·전체 검정), proportions_with_ci.csv, same_return_date_with_ci.csv, pairwise_tests_holm.csv, statistics_results.json.', '']
    (OUT/'코호트_통계검증_결과와해석.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__ == '__main__':
    main()
