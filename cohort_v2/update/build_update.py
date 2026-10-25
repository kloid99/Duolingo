"""코호트 v3 보완 산출물 (2026-10-14).

기존 v3 결과 파일을 읽기만 하고, 새 폴더 update에 아래를 저장한다.
  1) user_daily_state.csv        사용자×날짜 학습 상태 4분류 + 요일
  2) daily_state_summary.csv     날짜×세그먼트(및 전체)별 상태 인원
  3) first_followup_users.csv    첫 후속 학습자 사용자 단위 A0/A1 구분과 D1·D2 결과
  4) a0_a1_comparison.csv        세그먼트×첫 후속 학습일×A0/A1 요약 (Wilson 95%)
  5) a0_a1_difference.csv        같은 날짜 A0-A1 차이 (Newcombe 95%, 두 비율 z검정)
  6) recency_segment_comparison.csv  세그먼트×최근성(마지막 기록일)별 추적 결과
  7) calendar.csv                추적 날짜의 요일과 전체 기록 비율
  8) update_validation.json      기존 결과와의 대조 결과

실행: python build_update.py  (cohort_v2 폴더 기준)
"""
from pathlib import Path
import json, math, os
import numpy as np
import pandas as pd

V = Path(os.environ.get('COHORT_V3') or Path(__file__).resolve().parents[1])
OUT = V / 'update'
OUT.mkdir(parents=True, exist_ok=True)
SEG_ORDER = ['꾸준형', '습관 형성형', '최근 단발형', '멈춤-꾸준형', '멈춤-몰입형', '멈춤-저활동형']
DATES = ['2013-03-08', '2013-03-09', '2013-03-10', '2013-03-11']
WEEKDAY = {'2013-03-06': '수', '2013-03-07': '목', '2013-03-08': '금', '2013-03-09': '토',
           '2013-03-10': '일', '2013-03-11': '월', '2013-03-12': '화', '2013-03-13': '수'}
Z = 1.959963984540054


def wilson(x, n):
    if not n or pd.isna(x):
        return (np.nan, np.nan)
    p = x / n; den = 1 + Z * Z / n
    c = (p + Z * Z / (2 * n)) / den
    hw = Z * math.sqrt(p * (1 - p) / n + Z * Z / (4 * n * n)) / den
    return (c - hw, c + hw)


u = pd.read_csv(V / 'user_retention_cohort.csv', low_memory=False)
ud = pd.read_csv(V / 'user_daily_retention.csv')
seg_daily = pd.read_csv(V / 'segment_daily_retention.csv')
overall_daily = pd.read_csv(V / 'overall_daily_retention.csv')
seg_sum = pd.read_csv(V / 'segment_retention_summary.csv')
cand = pd.read_csv(V / 'behavior_flow' / 'primary_candidate_eligibility.csv')
cand_out = pd.read_csv(V / 'behavior_flow' / 'primary_candidate_outcomes.csv')
checks = {}
assert len(u) == 82467 and u.user_id.is_unique
assert len(ud) == 82467 * 4

# 1) 날짜별 학습 상태
a = ud.active == 1
ud['weekday'] = ud.date.map(WEEKDAY)
ud['lifecycle_state'] = np.select(
    [a & (ud.inactive_days_before_date == 0),
     a & (ud.inactive_days_before_date >= 1),
     ~a & ud.inactive_days_end_of_date.between(1, 2),
     ~a & (ud.inactive_days_end_of_date >= 3)],
    ['연속 학습', '재개', '위험(1~2일 기록 없음)', '장기 비활동(3일 이상)'], default='미분류')
assert (ud.lifecycle_state == '미분류').sum() == 0
STATE_ORDER = ['연속 학습', '재개', '위험(1~2일 기록 없음)', '장기 비활동(3일 이상)']
ud[['user_id', 'segment', 'date', 'weekday', 'followup_day', 'active', 'inactive_days_before_date',
    'inactive_days_end_of_date', 'lifecycle_state']].to_csv(OUT / 'user_daily_state.csv', index=False, encoding='utf-8-sig')

rows = []
for level, grp in [('전체', ud.assign(segment='전체'))] + [('세그먼트', ud)]:
    g = grp.groupby(['segment', 'date', 'lifecycle_state']).size().unstack(fill_value=0).reindex(columns=STATE_ORDER, fill_value=0)
    for (seg, date), r in g.iterrows():
        n = int(r.sum())
        for st in STATE_ORDER:
            rows.append({'level': level, 'segment': seg, 'date': date, 'weekday': WEEKDAY[date], 'state': st,
                         'users': int(r[st]), 'cohort_users': n, 'share': r[st] / n})
dss = pd.DataFrame(rows)
dss['segment_order'] = dss.segment.map({s: i + 1 for i, s in enumerate(SEG_ORDER)}).fillna(0).astype(int)
dss.to_csv(OUT / 'daily_state_summary.csv', index=False, encoding='utf-8-sig')

# 대조: 상태 합계 = 기존 활동자·3일 비활동 인원
for d in DATES:
    ov = overall_daily.set_index('date').loc[d]
    t = dss[(dss.level == '전체') & (dss.date == d)].set_index('state').users
    assert t['연속 학습'] + t['재개'] == ov.active_users, d
    assert t['장기 비활동(3일 이상)'] == ov.inactive_3day_users, d
    assert t.sum() == 82467
    for s in SEG_ORDER:
        sd = seg_daily[(seg_daily.segment == s) & (seg_daily.date == d)].iloc[0]
        ts = dss[(dss.level == '세그먼트') & (dss.segment == s) & (dss.date == d)].set_index('state').users
        assert ts['연속 학습'] + ts['재개'] == sd.active_users
        assert ts['장기 비활동(3일 이상)'] == sd.inactive_3day_users
checks['daily_state'] = '4개 날짜 × (전체+6세그먼트): 활동자 수와 3일 이상 비활동 인원이 기존 결과와 일치, 미분류 0명'

# 2) 첫 후속 학습자 A0/A1
f = u[u.first_return_date.notna()].copy()
prev = pd.to_datetime(f.first_return_date) - pd.Timedelta(days=1)
# 전날 학습 여부: 3/8 첫 학습자는 기준 주간 마지막 학습일이 3/7인지, 3/9 이후 첫 학습자는 정의상 전날(추적 기간) 학습 없음
f['prev_day_active'] = (f.first_return_date == '2013-03-08') & (f.last_active == '2013-03-07')
f['group'] = np.where(f.prev_day_active, 'A0 이어서 학습(전날도 기록)', 'A1형 쉬었다 재개(전날 기록 없음)')
f['weekday'] = f.first_return_date.map(WEEKDAY)
f['next_two_days'] = f.first_return_date.map({'2013-03-08': '토·일', '2013-03-09': '일·월', '2013-03-10': '월·화', '2013-03-11': '화·수'})
f['outcome_observed'] = f.first_return_date.isin(['2013-03-08', '2013-03-09'])
f['d1_d2_learning'] = f.relearned_within_2days_after_first_return.where(f.outcome_observed)
f[['user_id', 'segment', 'first_return_date', 'weekday', 'next_two_days', 'last_active', 'prev_day_active', 'group',
   'outcome_observed', 'd1_d2_learning']].to_csv(OUT / 'first_followup_users.csv', index=False, encoding='utf-8-sig')

# A1 대조: 습관 형성형 A1형 = primary_candidate 4,809명
h1 = f[(f.segment == '습관 형성형') & ~f.prev_day_active]
assert set(h1.user_id) == set(cand.user_id) and len(h1) == 4809
m = h1.merge(cand_out[['user_id', 'any_learning']], on='user_id')
assert ((m.d1_d2_learning.fillna(-1)) == (m.any_learning.fillna(-1))).all()
checks['a1_match'] = '습관 형성형 A1형 4,809명이 primary_candidate 대상자와 동일, D1·D2 결과(미관측 포함) 전원 일치'

rows = []
for level, grp in [('전체', f.assign(segment='전체')), ('세그먼트', f)]:
    for (seg, d, gname), g in grp.groupby(['segment', 'first_return_date', 'group']):
        obs = bool(g.outcome_observed.iloc[0])
        x = int(g.d1_d2_learning.sum()) if obs else np.nan
        lo, hi = wilson(x, len(g)) if obs else (np.nan, np.nan)
        rows.append({'level': level, 'segment': seg, 'first_return_date': d, 'weekday': WEEKDAY[d],
                     'next_two_days': g.next_two_days.iloc[0], 'group': gname, 'users': len(g),
                     'outcome_observed': obs, 'd1_d2_learning_users': x,
                     'rate': x / len(g) if obs else np.nan, 'ci95_low': lo, 'ci95_high': hi})
cmp_ = pd.DataFrame(rows)
cmp_['segment_order'] = cmp_.segment.map({s: i + 1 for i, s in enumerate(SEG_ORDER)}).fillna(0).astype(int)
cmp_.to_csv(OUT / 'a0_a1_comparison.csv', index=False, encoding='utf-8-sig')

# 같은 날짜(3/8)에서만 A0와 A1을 비교할 수 있다
diff_rows = []
for seg in ['전체'] + SEG_ORDER:
    c = cmp_[(cmp_.segment == seg) & (cmp_.first_return_date == '2013-03-08')].set_index('group')
    if len(c) < 2:
        continue
    r0, r1 = c.loc['A0 이어서 학습(전날도 기록)'], c.loc['A1형 쉬었다 재개(전날 기록 없음)']
    x0, n0, x1, n1 = r0.d1_d2_learning_users, r0.users, r1.d1_d2_learning_users, r1.users
    p0, p1 = x0 / n0, x1 / n1; d_ = p0 - p1
    l0, u0 = wilson(x0, n0); l1, u1 = wilson(x1, n1)
    pp = (x0 + x1) / (n0 + n1); z = d_ / math.sqrt(pp * (1 - pp) * (1 / n0 + 1 / n1))
    diff_rows.append({'segment': seg, 'first_return_date': '2013-03-08', 'next_two_days': '토·일',
                      'a0_users': int(n0), 'a0_rate': p0, 'a1_users': int(n1), 'a1_rate': p1,
                      'diff_pp': d_ * 100,
                      'diff_ci95_low_pp': (d_ - math.sqrt((p0 - l0) ** 2 + (u1 - p1) ** 2)) * 100,
                      'diff_ci95_high_pp': (d_ + math.sqrt((u0 - p0) ** 2 + (p1 - l1) ** 2)) * 100,
                      'z': z, 'p_two_sided': math.erfc(abs(z) / math.sqrt(2))})
dif = pd.DataFrame(diff_rows)
dif.to_csv(OUT / 'a0_a1_difference.csv', index=False, encoding='utf-8-sig')
hd = dif.set_index('segment').loc['습관 형성형']
assert (hd.a0_users, hd.a1_users) == (2799, 1307)
assert round(hd.a0_rate * 100, 1) == 49.7 and round(hd.a1_rate * 100, 1) == 42.0
checks['a0_a1_habit'] = {k: (round(float(v), 4) if isinstance(v, (float, np.floating)) else v) for k, v in hd.to_dict().items()}

# 3) 최근성(마지막 기록일)을 맞춘 비교
u['last_active_weekday'] = u.last_active.map(WEEKDAY)
rows = []
for (seg, rec), g in u.groupby(['segment', 'recency']):
    n = len(g); x2 = int(g.returned_2plus_days.sum()); x1 = int(g.returned_4d.sum())
    lo, hi = wilson(x2, n)
    rows.append({'segment': seg, 'segment_order': SEG_ORDER.index(seg) + 1, 'recency_days': int(rec),
                 'last_active': g.last_active.iloc[0], 'users': n,
                 'return_1plus_users': x1, 'return_1plus_rate': x1 / n,
                 'repeat_2plus_users': x2, 'repeat_2plus_rate': x2 / n, 'repeat_ci95_low': lo, 'repeat_ci95_high': hi})
for rec, g in u.groupby('recency'):
    n = len(g); x2 = int(g.returned_2plus_days.sum()); x1 = int(g.returned_4d.sum()); lo, hi = wilson(x2, n)
    rows.append({'segment': '전체', 'segment_order': 0, 'recency_days': int(rec), 'last_active': g.last_active.iloc[0],
                 'users': n, 'return_1plus_users': x1, 'return_1plus_rate': x1 / n, 'repeat_2plus_users': x2,
                 'repeat_2plus_rate': x2 / n, 'repeat_ci95_low': lo, 'repeat_ci95_high': hi})
rc = pd.DataFrame(rows).sort_values(['segment_order', 'recency_days'])
assert rc.groupby('last_active').recency_days.nunique().max() == 1
rc.to_csv(OUT / 'recency_segment_comparison.csv', index=False, encoding='utf-8-sig')
for s in SEG_ORDER:
    t = rc[rc.segment == s]; ss = seg_sum.set_index('segment').loc[s]
    assert t.users.sum() == ss.cohort_users and t.repeat_2plus_users.sum() == ss.repeat_users
checks['recency'] = '세그먼트별 최근성 칸 합계가 기존 세그먼트 인원·2일 이상 학습자와 일치'

# 4) 요일 달력
cal = overall_daily[['date', 'cohort_users', 'active_users', 'daily_relearning_rate']].copy()
cal['weekday'] = cal.date.map(WEEKDAY); cal['is_weekend'] = cal.weekday.isin(['토', '일'])
cal.to_csv(OUT / 'calendar.csv', index=False, encoding='utf-8-sig')

(OUT / 'update_validation.json').write_text(json.dumps(
    {'created': '2026-10-14', 'inputs_read_only': ['user_retention_cohort.csv', 'user_daily_retention.csv',
     'segment_daily_retention.csv', 'overall_daily_retention.csv', 'segment_retention_summary.csv',
     'behavior_flow/primary_candidate_eligibility.csv', 'behavior_flow/primary_candidate_outcomes.csv'],
     'checks': checks,
     'notes': ['A0는 구조상 3/8 첫 후속 학습자에만 존재한다(3/9 이후 첫 학습자는 전날이 추적 기간이라 기록이 없다).',
               'A0-A1 비교는 같은 날짜(3/8, 다음 두 날 토·일) 안의 탐색적 관측 비교이며 개입 효과가 아니다.',
               '미관측 결과(3/10·11 첫 학습자의 D1·D2)는 빈 값으로 두었다.',
               'level 열로 전체 행과 세그먼트 행을 구분한다. 전체를 세그먼트 합으로 다시 더하지 않는다.']},
    ensure_ascii=False, indent=2, default=str), encoding='utf-8')
print(json.dumps(checks, ensure_ascii=False, indent=1, default=str))
print(sorted(p.name for p in OUT.iterdir()))
