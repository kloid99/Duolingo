"""
Duolingo 학습일 퍼널 분석 (2013-03-01 ~ 03-07, UTC)

퍼널 단계: 한 주 동안 학습한 날 수
    1일 이상 → 2일 이상 → 3일 이상 → 4일 이상(= NSM 달성)
분석 대상
    전체 퍼널 : 첫 등장 3/1~3/4 유저 (3/5 이후 첫 등장자는 4일 달성이 불가능해 제외)
    그룹 비교 : 첫 등장 3/1 유저 (7일 전체 관찰 가능 → 공정 비교)

실행
    pip install duckdb pandas matplotlib
    python funnel_analysis.py
결과
    outputs/funnel/ 에 CSV 9개 + 차트 PNG 3개
"""
import os

import duckdb
import matplotlib.pyplot as plt
import pandas as pd

# ---------------------------------------------------------------------------
# 설정
# ---------------------------------------------------------------------------
from pathlib import Path
DATA = Path(__file__).resolve().parent / "learning_traces.13m.csv" / "learning_traces.13m.csv"
WEEK_START = "2013-03-01"          # 포함 (UTC)
WEEK_END = "2013-03-08"            # 미포함 (UTC) → 3/1~3/7, 7일
NSM_DAYS = 4                       # NSM: 7일 중 4일 이상
FUNNEL_LAST_D0 = "2013-03-04"      # 전체 퍼널: 이 날까지 첫 등장한 유저 (4일 달성 가능)
COHORT_DAY = "2013-03-01"          # 그룹 비교용: 7일을 모두 관찰할 수 있는 첫 등장일
MIN_GROUP_USERS = 1000             # 언어쌍 비교 최소 인원
OUT = "outputs/funnel"


def md(date_str):
    """'2013-03-04' → '3/4'"""
    return f"{int(date_str[5:7])}/{int(date_str[8:10])}"

# 차트 색상 (light 테마)
BLUE, ORANGE = "#2a78d6", "#eb6834"
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"

os.makedirs(OUT, exist_ok=True)
pd.set_option("display.width", 200)
plt.rcParams.update({
    "font.family": "Malgun Gothic", "axes.unicode_minus": False,
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
})


def save_csv(df, name, title):
    print(f"\n==={title} ===")
    print(df.to_string(index=False))
    df.to_csv(f"{OUT}/{name}.csv", index=False, encoding="utf-8-sig")


def funnel(days, max_step=7):
    """학습일 수 Series → 단계별 사용자 수 / 전체 대비 / 이전 단계 대비 전환율 / 이탈 인원"""
    rows, prev = [], len(days)
    for k in range(1, max_step + 1):
        n = int((days >= k).sum())
        rows.append({"step": f"{k}일 이상", "users": n,
                     "pct_of_total": round(n / len(days), 4),
                     "step_conversion": round(n / prev, 4) if prev else None,
                     "dropped": prev - n})
        prev = n
    return pd.DataFrame(rows)


def segment_funnel(df, col):
    """그룹별 1→2, 2→3, 3→4 전환율과 4일 달성률"""
    rows = []
    for key, g in df.groupby(col, observed=True):
        f = funnel(g.days, NSM_DAYS)
        rows.append({col: key, "users": len(g),
                     "conv_1to2": f.step_conversion[1], "conv_2to3": f.step_conversion[2],
                     "conv_3to4": f.step_conversion[3], "reach_nsm": f.pct_of_total[3]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 1. 데이터 로드 (UTC 기준 3/1~3/7) → 사용자-일 → 사용자 테이블
# ---------------------------------------------------------------------------
con = duckdb.connect()
con.execute("SET TimeZone='UTC'")   # DuckDB 기본값은 PC 시간대(한국시간)이므로 반드시 UTC로 고정
raw_rows = con.sql(f"SELECT count(*) FROM read_csv_auto('{DATA}')").fetchone()[0]
con.execute(f"CREATE TABLE raw AS SELECT DISTINCT * FROM read_csv_auto('{DATA}')")   # 완전 중복 행 제거
print(f"중복 제거:{raw_rows - con.sql('SELECT count(*) FROM raw').fetchone()[0]:,}행")
con.execute(f"""
    CREATE TABLE t AS
    SELECT user_id, CAST(to_timestamp("timestamp") AS DATE) AS d,
           learning_language || '←' || ui_language AS lang, session_seen, session_correct
    FROM raw
    WHERE to_timestamp("timestamp") >= TIMESTAMPTZ '{WEEK_START} 00:00:00+00'
      AND to_timestamp("timestamp") <  TIMESTAMPTZ '{WEEK_END} 00:00:00+00'
""")
con.execute("DROP TABLE raw")
con.execute("""
    CREATE TABLE user_day AS
    SELECT user_id, d, sum(session_seen) AS items, sum(session_correct) / sum(session_seen) AS acc
    FROM t GROUP BY 1, 2
""")
# 여러 언어를 학습한 사용자는 이번 주 학습량이 가장 많은 언어쌍으로 지정 (동률이면 이름순)
con.execute("""
    CREATE TABLE user_lang AS
    SELECT user_id, lang FROM (
        SELECT user_id, lang,
               row_number() OVER (PARTITION BY user_id ORDER BY sum(session_seen) DESC, lang) AS rn
        FROM t GROUP BY 1, 2
    ) WHERE rn = 1
""")
users = con.sql("""
    WITH f AS (SELECT user_id, min(d) AS d0 FROM user_day GROUP BY 1)
    SELECT f.user_id, f.d0, any_value(ul.lang) AS lang,
           count(*) AS days,
           max((ud.d = f.d0 + 1)::INT) AS next_day_return,
           max(CASE WHEN ud.d = f.d0 THEN ud.items END) AS d0_items,
           max(CASE WHEN ud.d = f.d0 THEN ud.acc END) AS d0_acc
    FROM f JOIN user_day ud USING (user_id) JOIN user_lang ul USING (user_id)
    GROUP BY 1, 2
""").df()
users["d0"] = pd.to_datetime(users.d0)

# ---------------------------------------------------------------------------
# 2. 전체 퍼널
# ---------------------------------------------------------------------------
funnel_users = users[users.d0 <= pd.Timestamp(FUNNEL_LAST_D0)]
overall = funnel(funnel_users.days)
save_csv(overall, "01_funnel_overall", f"전체 학습일 퍼널 (첫 등장 ~{md(FUNNEL_LAST_D0)} 유저{len(funnel_users):,}명)")

# 참고: 대상 범위에 따른 퍼널 비교 (4일 이상 인원은 A·B 동일)
pops = {"A. 기간 내 전체 활동 유저": users,
        f"B. 첫 등장 3/1~{md(FUNNEL_LAST_D0)} (본 분석)": funnel_users,
        f"C. 첫 등장{md(COHORT_DAY)} (그룹 비교)": users[users.d0 == pd.Timestamp(COHORT_DAY)]}
pop_rows = []
for name, g in pops.items():
    f = funnel(g.days, NSM_DAYS)
    pop_rows.append({"population": name, **dict(zip(f.step, f.users)),
                     "conv_1to2": f.step_conversion[1], "conv_2to3": f.step_conversion[2],
                     "conv_3to4": f.step_conversion[3], "reach_nsm": f.pct_of_total[3]})
save_csv(pd.DataFrame(pop_rows), "01b_funnel_by_population", "대상 범위별 퍼널 비교")

# ---------------------------------------------------------------------------
# 3. 첫 등장일별 4일 달성률 — 관찰 기회 차이 확인
# ---------------------------------------------------------------------------
by_d0 = (users.groupby("d0")
         .agg(users=("days", "size"), reach_nsm=("days", lambda x: round((x >= NSM_DAYS).mean(), 4)))
         .reset_index())
by_d0["d0"] = by_d0.d0.dt.strftime("%m-%d")
save_csv(by_d0, "02_reach_by_first_day", "첫 등장일별 4일 달성률 (3/5 이후 첫 등장자는 4일 달성 불가)")

# ---------------------------------------------------------------------------
# 4. 세분화 비교 — 3/1 첫 등장자만 (모두 7일 관찰 가능하므로 공정 비교)
# ---------------------------------------------------------------------------
cohort = users[users.d0 == pd.Timestamp(COHORT_DAY)].copy()
print(f"\n비교 코호트:{COHORT_DAY} 첫 등장자{len(cohort):,}명, 4일 달성률{(cohort.days >= NSM_DAYS).mean():.4f}")

cohort["first_day_items"] = pd.cut(cohort.d0_items, [0, 20, 60, 120, float("inf")],
                                   labels=["20문제 미만", "20~59", "60~119", "120 이상"], right=False)
cohort["first_day_accuracy"] = pd.cut(cohort.d0_acc, [0, 0.84, 0.97, 1.0001],
                                      labels=["84% 미만", "84~97%", "97% 초과"], right=False)
cohort["next_day"] = cohort.next_day_return.map({1: "다음날 재학습 O", 0: "다음날 재학습 X"})

seg_items = segment_funnel(cohort, "first_day_items")
seg_acc = segment_funnel(cohort, "first_day_accuracy")
seg_lang = segment_funnel(cohort, "lang").query("users >= @MIN_GROUP_USERS").sort_values("reach_nsm", ascending=False)
seg_next = segment_funnel(cohort, "next_day")
save_csv(seg_items, "03_segment_first_day_items", "첫날 학습량별 퍼널 (3/1 코호트)")
save_csv(seg_acc, "04_segment_first_day_accuracy", "첫날 정답률별 퍼널 (3/1 코호트)")
save_csv(seg_lang, "05_segment_language", f"언어쌍별 퍼널 (3/1 코호트,{MIN_GROUP_USERS:,}명 이상)")
save_csv(seg_next, "06_segment_next_day", "다음날 재학습 여부별 퍼널 (3/1 코호트)")

# 4-1. 정답률 효과가 학습량 차이 때문인지 확인 (교란 점검)
acc_items = (cohort.groupby("first_day_accuracy", observed=True)
             .agg(users=("days", "size"), median_first_day_items=("d0_items", "median"),
                  reach_nsm=("days", lambda x: round((x >= NSM_DAYS).mean(), 4)))
             .reset_index())
save_csv(acc_items, "07_accuracy_vs_items", "첫날 정답률 그룹별 첫날 학습량 중앙값")
cross = (cohort.groupby(["first_day_items", "first_day_accuracy"], observed=True)
         .agg(users=("days", "size"), reach_nsm=("days", lambda x: round((x >= NSM_DAYS).mean(), 4)))
         .reset_index())
save_csv(cross, "08_reach_by_items_x_accuracy", "학습량 구간 안에서 정답률별 4일 달성률")

# 4-2. 보강: 3/2~3/4 시작자에서도 첫날 학습량 효과가 유지되는지 (시작일별 비교)
#      그룹 비교를 3/1 시작자로 한정했으므로, 다른 시작일에서도 같은 경향인지 확인
fu = funnel_users.copy()
fu["first_day_items"] = pd.cut(fu.d0_items, [0, 20, 60, 120, float("inf")],
                               labels=["20문제 미만", "20~59", "60~119", "120 이상"], right=False)
fu["start"] = fu.d0.dt.strftime("%m-%d")
by_start = (fu.groupby(["start", "first_day_items"], observed=True)
              .agg(users=("days", "size"),
                   conv_1to2=("days", lambda x: round((x >= 2).mean(), 4)),
                   reach_nsm=("days", lambda x: round((x >= NSM_DAYS).mean(), 4)))
              .reset_index())
save_csv(by_start, "09_items_by_start_day", "시작일별 첫날 학습량 효과 (보강)")

# ---------------------------------------------------------------------------
# 5. 차트
# ---------------------------------------------------------------------------
# 5-1. 전체 퍼널 (1~4일)
f4 = overall.head(NSM_DAYS)
fig, ax = plt.subplots(figsize=(8, 4.6))
bars = ax.bar(f4.step, f4.users, width=0.56, color=BLUE)
for b, (_, r) in zip(bars, f4.iterrows()):
    ax.text(b.get_x() + b.get_width() / 2, b.get_height() + f4.users[0] * 0.015,
            f"{r.users:,}명\n({r.pct_of_total:.1%})", ha="center", va="bottom", fontsize=10, color=INK)
for i in range(1, len(f4)):
    x = i - 0.5
    y = f4.users[i - 1] * 0.55
    color = ORANGE if i == 1 else INK_2
    ax.annotate(f"→{f4.step_conversion[i]:.1%}", (x, y), ha="center", fontsize=10,
                color=color, fontweight="bold" if i == 1 else "normal")
ax.text(0.5, f4.users[0] * 0.47, "병목", ha="center", fontsize=9, color=ORANGE)
ax.set_title(f"학습 습관 퍼널 · 첫 등장 3/1~{md(FUNNEL_LAST_D0)} 유저{len(funnel_users):,}명 (UTC) ·{NSM_DAYS}일 이상 = NSM",
             loc="left", fontsize=12, pad=14)
ax.set_ylim(0, f4.users[0] * 1.22)
ax.yaxis.set_major_formatter(lambda v, _: f"{v/1000:.0f}k")
ax.grid(axis="y", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.tick_params(axis="x", colors=INK_2, length=0)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_01_funnel_overall.png", dpi=200)
plt.close(fig)

# 5-2. 세분화별 4일 달성률 (small multiples)
avg = (cohort.days >= NSM_DAYS).mean()
panels = [("첫날 학습량", seg_items, "first_day_items"),
          ("첫날 정답률", seg_acc, "first_day_accuracy"),
          ("언어쌍 (학습←사용 언어)", seg_lang, "lang")]
fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharex=True)
for ax, (title, df, col) in zip(axes, panels):
    labels = df[col].astype(str).tolist()[::-1]
    vals = df.reach_nsm.tolist()[::-1]
    ax.barh(labels, vals, height=0.56, color=BLUE)
    for y, v in enumerate(vals):
        ax.text(v + 0.008, y, f"{v:.1%}", va="center", fontsize=9, color=INK,
                bbox=dict(facecolor=SURFACE, edgecolor="none", pad=1.5), zorder=3)
    ax.axvline(avg, color=MUTED, linestyle="--", linewidth=1)
    ax.set_title(title, loc="left", fontsize=11)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", colors=INK_2, length=0)
axes[0].text(avg, -0.9, f"코호트 평균{avg:.1%}", fontsize=8, color=MUTED, ha="left")
fig.suptitle(f"그룹별{NSM_DAYS}일 이상 학습 달성률 (3/1 첫 등장자{len(cohort):,}명)", x=0.01, ha="left", fontsize=12)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_02_reach_by_segment.png", dpi=200)
plt.close(fig)

# 5-3. 첫 등장일별 달성률 (관찰 기회 편향)
fig, ax = plt.subplots(figsize=(8, 3.8))
bars = ax.bar(by_d0.d0, by_d0.reach_nsm, width=0.56, color=BLUE)
for b, v in zip(bars, by_d0.reach_nsm):
    ax.text(b.get_x() + b.get_width() / 2, v + 0.006, f"{v:.1%}", ha="center", fontsize=9, color=INK)
ax.set_title(f"첫 등장일별{NSM_DAYS}일 달성률 — 늦게 등장할수록 기회가 적음", loc="left", fontsize=12, pad=12)
ax.set_ylim(0, by_d0.reach_nsm.max() * 1.18)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0%}")
ax.grid(axis="y", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.tick_params(axis="x", colors=INK_2, length=0)
fig.tight_layout()
fig.savefig(f"{OUT}/chart_03_reach_by_first_day.png", dpi=200)
plt.close(fig)

print(f"\n저장 위치:{OUT}/")