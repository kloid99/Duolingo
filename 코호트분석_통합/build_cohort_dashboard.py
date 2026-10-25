"""듀오링고 코호트 분석 최종 통합본 (대시보드 구성용).

기준: 노션 3팀 프로젝트(문제정의·분석 질문·NSM·지표 정의서·가설) + '세그먼트 기본' 문서(세그먼트 분석 최신 코드,
지표 체계: Input Metrics 4개·보류 지표, 세그먼트 요약표, 세그먼트별 액션).
통합 대상: 코호트분석.pdf, 코호트분석2.pdf.
산출: 통합 보고서 PDF(장 = 대시보드 탭) + 대시보드용 집계 CSV 패키지.

실행: python build_cohort_dashboard.py <원본 csv 또는 csv.gz> <출력 폴더>
환경변수 KR_FONT, KR_FONT_BOLD로 한글 TTF 지정(기본: 맑은 고딕).
"""
import sys, os, re, json
from math import sqrt
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from pypdf import PdfReader

SRC, OUTDIR = sys.argv[1], sys.argv[2]
DATA = os.path.join(OUTDIR, "dashboard_data"); os.makedirs(DATA, exist_ok=True)
PDF = os.path.join(OUTDIR, "코호트분석_최종통합본.pdf")
T = pd.Timestamp

# =============================================================== 1. 세그먼트 분석 최신 코드 재현 + 지표 원재료
df = pd.read_csv(SRC, dtype={"user_id": "category", "learning_language": "category", "ui_language": "category",
                             "lexeme_id": "category", "lexeme_string": "category"})
N_RAW = len(df); df = df.drop_duplicates(); N_DUP = N_RAW - len(df)
df = df[["user_id", "timestamp", "delta", "history_seen", "session_seen", "session_correct"]]
df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
df = df[(df["dt"] >= "2013-03-01") & (df["dt"] < "2013-03-12")].copy()
df["date"] = df["dt"].dt.normalize()
df["user_id"] = df["user_id"].astype(str)
N_USERS_311 = df["user_id"].nunique()
ud = df.groupby(["user_id", "date"]).agg(seen=("session_seen", "sum"), correct=("session_correct", "sum"),
                                         sessions=("timestamp", "nunique")).reset_index()
o = df[df.dt < "2013-03-08"]
# 세션 단위(사용자+timestamp)와 복습 행 (세그먼트 기본의 Input Metrics 정의용)
ss = o.groupby(["user_id", "timestamp"]).agg(seen=("session_seen", "sum"), corr=("session_correct", "sum")).reset_index().sort_values(["user_id", "timestamp"])
rv = o[o.history_seen >= 1].assign(ok=lambda x: x.delta.between(43200, 172800)).groupby("user_id").ok.mean()
del df, o

obs = ud[ud.date < T("2013-03-08")]; fol = ud[ud.date >= T("2013-03-08")]
u = obs.groupby("user_id").agg(first_active=("date", "min"), last_active=("date", "max"), active_days=("date", "nunique"),
                               words_seen=("seen", "sum"), words_correct=("correct", "sum"), sessions=("sessions", "sum"))
u["recency"] = (T("2013-03-08") - u.last_active).dt.days
u["F"] = pd.cut(u.active_days, [0, 1, 2, 3, 4, 7], labels=[1, 2, 3, 4, 5]).astype(int)
u["M"], M_EDGES = pd.qcut(u.words_seen, 5, labels=[1, 2, 3, 4, 5], retbins=True); u["M"] = u.M.astype(int)
u["R"] = pd.cut(u.recency, [0, 1, 2, 4, 6, 7], labels=[5, 4, 3, 2, 1]).astype(int)
SEG = ["꾸준형", "습관 형성형", "최근 단발형", "멈춤-꾸준형", "멈춤-몰입형", "멈춤-저활동형"]
cond = [(u.R >= 4) & (u.F >= 4), (u.R >= 4) & u.F.isin([2, 3]), (u.R >= 4) & (u.F == 1), (u.R <= 3) & (u.F >= 3), (u.R <= 3) & (u.M >= 4)]
u["segment"] = np.select(cond, SEG[:5], default=SEG[5])
DATES = list(pd.date_range("2013-03-08", "2013-03-11"))
act = set(zip(fol.user_id, fol.date))
for d in DATES: u[f"a{d.day}"] = [int((i, d) in act) for i in u.index]
u["fdays"] = u[[f"a{d.day}" for d in DATES]].sum(axis=1)
u["ret1"] = (u.fdays >= 1).astype(int); u["ret2"] = (u.fdays >= 2).astype(int)
u["acc"] = u.words_correct / u.words_seen

# ---- 세그먼트 기본의 Input Metrics (관측 주간, 세션 3개 이상 사용자)
ns = ss.groupby("user_id").size(); u["n_sessions_obs"] = ns
ss["gap"] = ss.groupby("user_id").timestamp.diff() / 3600
g = ss.dropna(subset=["gap"]).groupby("user_id").gap.agg(["mean", "std"])
u["gap_cv"] = g["std"] / g["mean"]
def halves(x):
    n = len(x); h = n // 2; a = x.iloc[:h]; b = x.iloc[n - h:]
    return pd.Series({"acc_early": a["corr"].sum() / a.seen.sum(), "acc_late": b["corr"].sum() / b.seen.sum()})
el = ns[ns >= 3].index
hv = ss[ss.user_id.isin(el)].groupby("user_id")[["seen", "corr"]].apply(halves)
u = u.join(hv); u["review_ok"] = rv
u["eligible3"] = u.n_sessions_obs >= 3
u.loc[~u.eligible3, ["gap_cv", "acc_early", "acc_late", "review_ok"]] = np.nan
u["regular"] = np.where(u.eligible3, (u.gap_cv < 1).astype(float), np.nan)
u["improved"] = np.where(u.eligible3, (u.acc_late > u.acc_early).astype(float), np.nan)

# ---- 대조
assert N_DUP == 81 and N_USERS_311 == 109504 and len(u) == 82467
assert (u.active_days >= 4).sum() == 9834 and u.ret1.sum() == 29240 and u.ret2.sum() == 13466
assert [int(x) for x in M_EDGES] == [1, 24, 53, 108, 239, 11501]
assert u.segment.value_counts().reindex(SEG).tolist() == [8882, 14583, 15402, 3627, 9303, 30670]

def rate(k, n): return k / n * 100 if n else float("nan")
def pct(k, n, d=1): return f"{rate(k, n):.{d}f}%"
def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c0 = (p + z * z / (2 * n)) / den
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c0 - h) * 100, (c0 + h) * 100

# ---- 학습 일수 / NSM (코호트분석2)
days = u.groupby("active_days").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
TEAM = {1: (47087, 10278, 3214), 2: (17134, 6675, 2711), 3: (8412, 4633, 2276), 4: (4748, 3310, 1931),
        5: (2723, 2189, 1521), 6: (1532, 1352, 1096), 7: (831, 803, 717)}
for d_, v in TEAM.items(): assert tuple(days.loc[d_]) == v
NSMG = {}
for key, sub in [("hit", u[u.active_days >= 4]), ("miss", u[u.active_days < 4])]:
    NSMG[key] = dict(n=len(sub), k1=int(sub.ret1.sum()), k2=int(sub.ret2.sum()), daily=[int(sub[f"a{d.day}"].sum()) for d in DATES],
                     cum=[int((sub[[f"a{x.day}" for x in DATES if x <= d]].sum(axis=1) > 0).sum()) for d in DATES])
assert NSMG["hit"]["daily"] == [4869, 4067, 3887, 4286] and NSMG["miss"]["cum"] == [9977, 14801, 18301, 21586]
rec1_days = u[u.recency == 1].groupby("active_days").agg(n=("F", "size"), k2=("ret2", "sum"))

# ---- 세그먼트 (코호트분석 + 세그먼트 기본 요약표)
WS = u.words_seen.sum()
seg = u.groupby("segment").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"), ws=("words_seen", "sum"), fd=("fdays", "mean"),
                               **{f"d{d.day}": (f"a{d.day}", "sum") for d in DATES}).reindex(SEG)
seg["cust"] = seg.n / len(u) * 100; seg["vol"] = seg.ws / WS * 100; seg["per"] = seg.ws / seg.n; seg["conc"] = seg.vol / seg.cust
CHI2 = chi2_contingency(pd.crosstab(u.segment, u.ret2))
seg_rec = u[u.recency.isin([1, 2])].groupby(["recency", "segment"]).agg(n=("F", "size"), k2=("ret2", "sum"))

# ---- 노션 Input metric: 다음날 재학습률 (사용자-활동일, d=3/1~3/6)
key = set(zip(obs.user_id, obs.date))
ad6 = obs[obs.date <= T("2013-03-06")][["user_id", "date"]].copy()
ad6["nxt"] = [(a, b + pd.Timedelta(days=1)) in key for a, b in zip(ad6.user_id, ad6.date)]
ad6 = ad6.merge(u[["segment"]], left_on="user_id", right_index=True)
NEXT_ALL = (int(ad6.nxt.sum()), len(ad6)); NEXT_SEG = ad6.groupby("segment").nxt.agg(["sum", "size"]).reindex(SEG)
fa = obs.merge(u[["first_active"]], left_on="user_id", right_index=True)
u["first_vol"] = fa[fa.date == fa.first_active].groupby("user_id").seen.sum()
u["spd"] = u.sessions / u.active_days

# ---- 첫 학습일 코호트
allact = set(zip(ud.user_id, ud.date))
TRI = []
for f in pd.date_range("2013-03-01", "2013-03-07"):
    ids = u.index[u.first_active == f]; row = {"first": f, "n": len(ids), "D": {}}
    for k in range(1, 11):
        d = f + pd.Timedelta(days=k)
        if d > T("2013-03-11"): break
        row["D"][k] = sum((i, d) in allact for i in ids)
    TRI.append(row)

# ---- 비활동 (분석 질문 3)
rec_curve = u[u.active_days <= 2].groupby(["active_days", "recency"]).agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
rc1 = rec_curve.loc[1]
RESUME = {}
for sg in ["꾸준형", "습관 형성형", "최근 단발형"]:
    s = u[(u.segment == sg) & (u.a8 == 1)]
    for r, lab in [(1, "cont"), (2, "rest")]:
        t = s[s.recency == r]; RESUME[(sg, lab)] = (len(t), int(((t.a9 + t.a10) > 0).sum()))
assert RESUME[("습관 형성형", "cont")] == (2799, 1392) and RESUME[("습관 형성형", "rest")] == (1307, 549)
(na, ka), (nb, kb) = RESUME[("습관 형성형", "cont")], RESUME[("습관 형성형", "rest")]
pa, pb = ka / na, kb / nb; pp = (ka + kb) / (na + nb)
RES_Z = (pa - pb) / sqrt(pp * (1 - pp) * (1 / na + 1 / nb)); RES_CI = 1.96 * sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb) * 100

# ---- Input metric × 가설
e = u[u.eligible3].copy()
IM = {"elig": len(e), "regular": e.regular.mean() * 100, "improved": e.improved.mean() * 100, "review_med": e.review_ok.median() * 100,
      "next": rate(*NEXT_ALL)}
im_seg = e.groupby("segment").agg(n=("F", "size"), reg=("regular", "mean"), imp=("improved", "mean"), rev=("review_ok", "median")).reindex(SEG)
reg_tab = e.groupby("regular").agg(n=("F", "size"), k2=("ret2", "sum"))
imp_tab = e.groupby("improved").agg(n=("F", "size"), k2=("ret2", "sum"))
reg_by_days = e.groupby("active_days").regular.agg(["mean", "size"])
reg_habit = e[e.segment == "습관 형성형"].groupby("regular").agg(n=("F", "size"), k2=("ret2", "sum"))
imp_habit = e[e.segment == "습관 형성형"].groupby("improved").agg(n=("F", "size"), k2=("ret2", "sum"))
e["rvq"] = pd.cut(e.review_ok, [-0.001, 0, 0.1, 0.25, 1.0], labels=["0%", "0~10%", "10~25%", "25% 초과"])
rv_tab = e.groupby("rvq", observed=True).agg(n=("F", "size"), k2=("ret2", "sum"))
rv_habit = e[e.segment == "습관 형성형"].groupby("rvq", observed=True).agg(n=("F", "size"), k2=("ret2", "sum"))

# ---- 액션 성공 지표 기준값 (세그먼트 기본 4️⃣)
s1 = u[u.segment == "최근 단발형"]; s1y = s1[s1.recency == 1]
BASE = {"habit_all4": rate((u[u.segment == "습관 형성형"].fdays == 4).sum(), seg.loc["습관 형성형", "n"]),
        "habit_ret2": rate(seg.loc["습관 형성형", "k2"], seg.loc["습관 형성형", "n"]),
        "pk_ret1": rate(seg.loc["멈춤-꾸준형", "k1"], seg.loc["멈춤-꾸준형", "n"]),
        "pm_fd": seg.loc["멈춤-몰입형", "fd"], "steady_ret2": rate(seg.loc["꾸준형", "k2"], seg.loc["꾸준형", "n"]),
        "single_next": rate(s1y.a8.sum(), len(s1y)), "single_next_n": len(s1y), "low_ret1": rate(seg.loc["멈춤-저활동형", "k1"], seg.loc["멈춤-저활동형", "n"])}
two3 = u[u.active_days.isin([2, 3])]; T23H = two3[two3.segment == "습관 형성형"]; T23P = two3[two3.segment != "습관 형성형"]

# =============================================================== 2. 대시보드 데이터 패키지
def save(df_, name): df_.to_csv(os.path.join(DATA, name), index=False, encoding="utf-8-sig")
kpi = pd.DataFrame([
    ("주간 활성 학습자 수", "count(사용자 | 3/1~3/7 활동일 ≥ 1)", len(u), None, "노션 지표 정의서"),
    ("주간 지속 학습 사용자 수(NSM)", "count(사용자 | 3/1~3/7 활동일 ≥ 4)", int((u.active_days >= 4).sum()), rate((u.active_days >= 4).sum(), len(u)), "노션 NSM"),
    ("다음날 재학습률", "활동일 d 중 d+1에도 활동 ÷ 활동일 d (d=3/1~3/6)", NEXT_ALL[0], IM["next"], "노션·세그먼트 기본 Input metric"),
    ("규칙적 학습자 비율", "세션 간 간격 변동계수 < 1 ÷ 세션 3개 이상 사용자", int(e.regular.sum()), IM["regular"], "세그먼트 기본 Input metric(가설 1)"),
    ("학습 성과 개선율", "후반 정답률 > 초반 정답률 ÷ 세션 3개 이상 사용자", int(e.improved.sum()), IM["improved"], "세그먼트 기본 Input metric(가설 2)"),
    ("적정 간격 복습 비율(중앙값)", "사용자별 delta 12~48시간 복습 행 비율의 중앙값, 세션 3개 이상 사용자", None, IM["review_med"], "세그먼트 기본 Input metric(가설 3)"),
    ("활동일당 세션 수(중앙값)", "사용자별 세션 수 ÷ 활동일 수의 중앙값", None, float(u.spd.median()), "세그먼트 기본 보류 지표"),
    ("첫 학습일 학습량(중앙값)", "관측 주 첫 활동일 session_seen 합의 중앙값", None, float(u.first_vol.median()), "세그먼트 기본 보류 지표"),
    ("후속 4일 재학습률", "3/8~3/11 중 1일 이상 학습 ÷ 주간 활성", int(u.ret1.sum()), rate(u.ret1.sum(), len(u)), "두 코호트 파일 공통"),
    ("후속 4일 반복학습률", "3/8~3/11 중 2일 이상 학습 ÷ 주간 활성", int(u.ret2.sum()), rate(u.ret2.sum(), len(u)), "두 코호트 파일 공통")],
    columns=["지표", "정의", "인원_또는_분자", "값(%)_또는_중앙값", "출처"])
save(kpi, "01_kpi_summary.csv")
save(pd.DataFrame({"active_days": days.index, "users": days.n, "ret1_users": days.k1, "ret1_rate": days.k1 / days.n * 100, "ret2_users": days.k2,
                   "ret2_rate": days.k2 / days.n * 100, "nsm_group": np.where(days.index >= 4, "달성", "미달성"),
                   "last3_7_users": rec1_days.n.reindex(days.index).values, "last3_7_ret2_rate": (rec1_days.k2 / rec1_days.n * 100).reindex(days.index).values}), "02_cohort_active_days.csv")
rows = []
for kname, gname in [("hit", "NSM 달성"), ("miss", "NSM 미달성")]:
    gg = NSMG[kname]
    for i, d in enumerate(DATES):
        rows.append([gname, str(d.date()), gg["n"], gg["daily"][i], gg["daily"][i] / gg["n"] * 100, gg["cum"][i], gg["cum"][i] / gg["n"] * 100])
save(pd.DataFrame(rows, columns=["group", "date", "users", "active_users", "daily_rate", "cum_users", "cum_rate"]), "03_cohort_nsm_daily.csv")
sg = seg.copy(); sg["segment"] = sg.index
sg["ret1_rate"] = sg.k1 / sg.n * 100; sg["ret2_rate"] = sg.k2 / sg.n * 100
sg["ret2_ci_low"], sg["ret2_ci_high"] = zip(*[wilson(k, n) for k, n in zip(sg.k2, sg.n)])
sg["next_day_rate"] = (NEXT_SEG["sum"] / NEXT_SEG["size"] * 100).values
sg["eligible3_users"] = im_seg.n.values; sg["regular_rate"] = im_seg.reg.values * 100; sg["improved_rate"] = im_seg.imp.values * 100
sg["review_ok_median"] = im_seg.rev.values * 100
sg["sessions_per_day_median"] = u.groupby("segment").spd.median().reindex(SEG).values
sg["first_day_volume_median"] = u.groupby("segment").first_vol.median().reindex(SEG).values
sg["accuracy_mean"] = u.groupby("segment").acc.mean().reindex(SEG).values * 100
save(sg[["segment", "n", "cust", "ws", "vol", "per", "conc", "k1", "ret1_rate", "k2", "ret2_rate", "ret2_ci_low", "ret2_ci_high", "fd",
         "next_day_rate", "eligible3_users", "regular_rate", "improved_rate", "review_ok_median", "sessions_per_day_median",
         "first_day_volume_median", "accuracy_mean"]].rename(columns={"n": "users", "cust": "user_share", "ws": "words_seen", "vol": "volume_share",
         "per": "words_per_user", "conc": "concentration", "k1": "ret1_users", "k2": "ret2_users", "fd": "followup_days_mean"}), "04_segment_summary.csv")
save(pd.DataFrame([[s, str(d.date()), int(seg.loc[s, "n"]), int(seg.loc[s, f"d{d.day}"]), seg.loc[s, f"d{d.day}"] / seg.loc[s, "n"] * 100] for s in SEG for d in DATES],
                  columns=["segment", "date", "users", "active_users", "daily_rate"]), "05_segment_daily.csv")
save(pd.DataFrame([[str(r["first"].date()), r["n"], k, (r["D"].get(k)), (r["D"][k] / r["n"] * 100 if k in r["D"] else None), k in r["D"]]
                   for r in TRI for k in range(1, 11)], columns=["first_active", "users", "day_k", "active_users", "rate", "observed"]), "06_first_active_cohort.csv")
rcv = rec_curve.reset_index(); rcv["ret1_rate"] = rcv.k1 / rcv.n * 100; rcv["ret2_rate"] = rcv.k2 / rcv.n * 100
save(rcv.rename(columns={"n": "users", "k1": "ret1_users", "k2": "ret2_users"}), "07_recency_curve.csv")
save(pd.DataFrame([[sg_, "이어서 학습(3/7 학습)" if lab == "cont" else "하루 쉬고 재개(3/6 마지막)", n_, k_, k_ / n_ * 100]
                   for (sg_, lab), (n_, k_) in RESUME.items()], columns=["segment", "group", "users", "d1d2_users", "d1d2_rate"]), "08_resume_compare.csv")
hrows = []
for mname, tab, lab in [("규칙적 학습자", reg_tab, {0.0: "불규칙(CV≥1)", 1.0: "규칙(CV<1)"}), ("학습 성과 개선", imp_tab, {0.0: "개선 없음", 1.0: "개선"})]:
    for k_, r_ in tab.iterrows(): hrows.append([mname, "전체", lab[k_], int(r_.n), int(r_.k2), r_.k2 / r_.n * 100])
for mname, tab, lab in [("규칙적 학습자", reg_habit, {0.0: "불규칙(CV≥1)", 1.0: "규칙(CV<1)"}), ("학습 성과 개선", imp_habit, {0.0: "개선 없음", 1.0: "개선"})]:
    for k_, r_ in tab.iterrows(): hrows.append([mname, "습관 형성형", lab[k_], int(r_.n), int(r_.k2), r_.k2 / r_.n * 100])
for nm, tab in [("전체", rv_tab), ("습관 형성형", rv_habit)]:
    for k_, r_ in tab.iterrows(): hrows.append(["적정 간격 복습 비율", nm, str(k_), int(r_.n), int(r_.k2), r_.k2 / r_.n * 100])
save(pd.DataFrame(hrows, columns=["metric", "scope", "group", "users", "ret2_users", "ret2_rate"]), "09_input_metric_hypothesis.csv")
act_rows = [["1", "습관 형성형", "4일 이상 학습 전환율", "후속 4일 모두 학습", BASE["habit_all4"], "후속 4일 중 2일 이상", BASE["habit_ret2"]],
            ["2", "멈춤-꾸준형", "4일 내 복귀율", "후속 4일 중 1일 이상", BASE["pk_ret1"], "", None],
            ["2", "멈춤-몰입형", "재학습일 수", "후속 4일 평균 학습일", BASE["pm_fd"], "", None],
            ["3", "꾸준형", "NSM 유지율", "측정 불가(다음 7일 필요) · 대체: 후속 2일 이상", BASE["steady_ret2"], "", None],
            ["4", "최근 단발형", "다음 날 복귀율", "3/7 학습자의 3/8 학습", BASE["single_next"], "", None],
            ["5", "멈춤-저활동형", "알림 반응률", "측정 불가(알림 로그 없음) · 대체: 4일 내 복귀율", BASE["low_ret1"], "", None]]
save(pd.DataFrame(act_rows, columns=["priority", "segment", "success_metric", "baseline_definition", "baseline_value", "extra_definition", "extra_value"]), "10_action_baselines.csv")
cols = ["segment", "active_days", "recency", "R", "F", "M", "first_active", "last_active", "words_seen", "acc", "sessions", "first_vol",
        "a8", "a9", "a10", "a11", "fdays", "ret1", "ret2", "n_sessions_obs", "gap_cv", "regular", "acc_early", "acc_late", "improved", "review_ok"]
uu = u[cols].reset_index().rename(columns={"index": "user_id"})
uu["first_active"] = uu.first_active.dt.date; uu["last_active"] = uu.last_active.dt.date
save(uu, "11_user_level.csv")

# =============================================================== 3. PDF
FR = os.environ.get("KR_FONT", "C:/Windows/Fonts/malgun.ttf"); FB = os.environ.get("KR_FONT_BOLD", "C:/Windows/Fonts/malgunbd.ttf")
pdfmetrics.registerFont(TTFont("KR", FR)); pdfmetrics.registerFont(TTFont("KR-B", FB))
pdfmetrics.registerFontFamily("KR", normal="KR", bold="KR-B", italic="KR", boldItalic="KR-B")
TOTAL = 10
W, H = 595.276, 841.89; M = 38; CW = W - 2 * M
INK = HexColor("#152A3A"); MUTED = HexColor("#536674"); TEAL = HexColor("#117C7A"); PALE = HexColor("#EAF5F3")
LINE = HexColor("#DCE5E8"); GRAY = HexColor("#E2E7EA"); MID = HexColor("#8FC6BE"); ORANGE = HexColor("#BA713B"); BG = HexColor("#F5F7F8")
RED = HexColor("#B4483B")
c = canvas.Canvas(PDF, pagesize=(W, H), pageCompression=1)
c.setTitle("듀오링고 코호트 분석 | 최종 통합본"); c.setAuthor("3팀 프로젝트")
c.setSubject("노션·세그먼트 기본 기준으로 두 코호트 분석을 통합하고 대시보드 탭 구조로 정리")

def rect(x, y, w, h, fill=BG, stroke=None, r=0):
    c.setFillColor(fill); c.setStrokeColor(stroke or fill); c.roundRect(x, H - y - h, w, h, r, stroke=bool(stroke), fill=1)
def line(x1, y1, x2, y2, color=LINE, width=0.7):
    c.setStrokeColor(color); c.setLineWidth(width); c.line(x1, H - y1, x2, H - y2)
def txt(s, x, y, size=10, color=INK, bold=False, align="left"):
    c.setFont("KR-B" if bold else "KR", size); c.setFillColor(color)
    {"left": c.drawString, "right": c.drawRightString, "center": c.drawCentredString}[align](x, H - y - size * 0.85, str(s))
def p(s, x, y, w, size=10.3, leading=None, color=INK, bold=False):
    st = ParagraphStyle("b", fontName="KR-B" if bold else "KR", fontSize=size, leading=leading or size * 1.57, textColor=color, wordWrap="CJK")
    obj = Paragraph(s, st); ow, oh = obj.wrap(w, 1000); obj.drawOn(c, x, H - y - oh)
    if y + oh > 792: raise RuntimeError(f"overflow p{c.getPageNumber()} {y + oh:.0f} {s[:50]}")
    return y + oh
def base(num, cat):
    rect(0, 0, W, 8, TEAL); txt("3팀 프로젝트  /  DUOLINGO", M, 25, 8.3, MUTED, bold=True); txt(cat, W - M, 25, 8.3, MUTED, align="right")
    line(M, 49, W - M, 49); line(M, 801, W - M, 801)
    txt("기준: 노션 지표 정의 · 세그먼트 기본(세그먼트 분석 최신 코드·지표 체계) · 2013년 공개 학습 기록", M, 812, 7.6, MUTED)
    txt(f"{num:02d} / {TOTAL:02d}", W - M, 812, 8, MUTED, align="right")
def tabtag(t):
    c.setFont("KR-B", 8); wdt = c.stringWidth(t, "KR-B", 8) + 14
    rect(W - M - wdt, 60, wdt, 16, PALE, r=8); txt(t, W - M - wdt / 2, 64, 8, TEAL, bold=True, align="center")
def title(label, heading, sub, tab=None):
    txt(label, M, 69, 9, TEAL, bold=True)
    if tab: tabtag(tab)
    y = p(heading, M, 91, CW, 22, 29, bold=True)
    return p(sub, M, y + 11, CW, 9.4, 14.5, color=MUTED)
def callout(s, y, h, size=10.0, lead=16, fill=PALE, bar=TEAL):
    rect(M, y, CW, h, fill, r=7); rect(M, y, 3, h, bar); p(s, M + 16, y + 11, CW - 32, size, lead)
def section(s, y): txt(s, M, y, 12, INK, bold=True)
def note(s, y, size=8.4, lead=12.8): return p(s, M, y, CW, size, lead, color=MUTED)
def table(headers, rows, x, y, widths, rh=23, hh=24, size=8.6, boldfirst=True):
    rect(x, y, sum(widths), hh, INK); off = x
    for h_, w in zip(headers, widths): p(h_, off + 6, y + 6, w - 12, 8.0, 11, color=white, bold=True); off += w
    yy = y + hh
    for i, row in enumerate(rows):
        rect(x, yy, sum(widths), rh, white if i % 2 else BG); off = x
        for j, (cell, w) in enumerate(zip(row, widths)):
            p(str(cell), off + 6, yy + 5.5, w - 12, size, size * 1.4, bold=(j == 0 and boldfirst)); off += w
        line(x, yy + rh, x + sum(widths), yy + rh); yy += rh
    return yy
def heat(v): return Color(.93 - .86 * v, .97 - .48 * v, .96 - .48 * v)
def kcards(items, y, h=74):
    gap = 8; n = len(items); cw_ = (CW - gap * (n - 1)) / n
    for i, (lab, val, det, hl) in enumerate(items):
        x = M + i * (cw_ + gap); rect(x, y, cw_, h, PALE if hl else BG, r=6)
        p(lab, x + 9, y + 8, cw_ - 18, 7.8, 10.5, color=MUTED, bold=True)
        txt(val, x + 9, y + 32, 17, TEAL, bold=True); p(det, x + 9, y + h - 20, cw_ - 18, 7.0, 9.5, color=MUTED)

r1 = {d: rate(days.loc[d, "k1"], days.loc[d, "n"]) for d in days.index}
r2 = {d: rate(days.loc[d, "k2"], days.loc[d, "n"]) for d in days.index}
hit, miss = NSMG["hit"], NSMG["miss"]

# ---------------------------------------------------------------- 1. 요약 (= 대시보드 '개요' 탭)
base(1, "핵심 요약 · 개요 탭")
title("01  /  분석의 결론", "여러 날 학습한 사용자가 다시 돌아왔고,<br/>하루 공백이 가장 큰 하락 지점이었다",
      "듀오링고 코호트 분석 · 최종 통합본(코호트분석 + 코호트분석2) · 노션·세그먼트 기본 기준 · 2026.10.15", "대시보드 탭 1 · 개요")
section("North Star와 결과", 186)
kcards([("주간 활성 학습자", "82,467", "3/1-3/7 1일 이상", False), ("NSM 지속 학습자", "9,834", "7일 중 4일 이상 · 11.9%", True),
        ("후속 4일 재학습", pct(29240, 82467), "3/8-3/11 1일 이상", False), ("후속 4일 반복학습", pct(13466, 82467), "3/8-3/11 2일 이상", False)], 208, 70)
section("Input Metrics (세그먼트 기본 정의)", 298)
kcards([("다음날 재학습률", f"{IM['next']:.1f}%", "사용자-활동일 기준", True), ("규칙적 학습자 비율", f"{IM['regular']:.1f}%", "세션 3개+ 사용자 · 정의 재검토 필요", False),
        ("학습 성과 개선율", f"{IM['improved']:.1f}%", "세션 3개+ 사용자", False), ("적정 간격 복습 비율", f"{IM['review_med']:.1f}%", "사용자별 값의 중앙값", False)], 320, 70)
section("분석 질문별 답", 412)
y = 436
for num, head, body in [
    ("1", "학습 일수가 늘수록 후속 재학습이 계단처럼 높아졌다 (NSM)", f"NSM 달성군 {pct(hit['k1'], hit['n'])}, 미달성군 {pct(miss['k1'], miss['n'])}. 1일 {r1[1]:.1f}% → 4일 {r1[4]:.1f}% → 7일 {r1[7]:.1f}%."),
    ("2", "6개 세그먼트의 반복학습률은 55.9%에서 4.7%까지 갈렸다 (분석 질문 1)", "세그먼트 간 차이는 유의했고(카이제곱 p&lt;0.001), 마지막 학습일을 맞춰도 순서가 유지됐다."),
    ("3", "하루를 쉬면 재학습 가능성이 가장 크게 떨어졌다 (분석 질문 3)", f"1일 학습자 기준 마지막 학습이 어제면 {rate(rc1.loc[1, 'k1'], rc1.loc[1, 'n']):.1f}%, 이틀 전이면 {rate(rc1.loc[2, 'k1'], rc1.loc[2, 'n']):.1f}%."),
    ("4", "Input metric 중 '다음날 재학습률'만 NSM과 같은 방향으로 움직였다 (가설)",
     f"규칙적 학습자는 오히려 반복학습이 낮았고({rate(reg_tab.loc[1.0, 'k2'], reg_tab.loc[1.0, 'n']):.1f}% vs {rate(reg_tab.loc[0.0, 'k2'], reg_tab.loc[0.0, 'n']):.1f}%) 정의에 구조적 문제가 있다. 성과 개선은 차이가 없었다.")]:
    txt(num, M, y, 13, TEAL, bold=True); y = p("<b>" + head + "</b><br/>" + body, M + 24, y, CW - 24, 9.2, 13.8) + 8
callout("<b>실행 제안</b>  NSM 직전 단계인 <b>습관 형성형</b>에게 학습을 마친 직후 <b>다음 학습일을 정하는 안내</b>를 주고, 다음날 재학습률(주 지표)과 주간 NSM 달성률(보조)로 효과를 실험한다.", y + 6, 58, 9.6, 15)
c.showPage()

# ---------------------------------------------------------------- 2. 대시보드 구성안
base(2, "대시보드 구성안")
title("02  /  대시보드 구성안", "이 보고서의 각 장이<br/>대시보드의 한 탭이 되도록 정리했다",
      "모든 수치는 dashboard_data 폴더의 CSV에서 다시 그릴 수 있다 · 사용자 단위 파일로 세그먼트·학습 일수 필터를 걸 수 있다")
rows = [["1 개요", "NSM·Input metric은 어떤 수준인가", "KPI 카드 8개, 세그먼트 구성 막대", "01_kpi_summary, 04_segment_summary", "1장"],
        ["2 NSM 코호트", "여러 날 학습할수록 다시 오는가", "학습 일수별 막대, 달성/미달성 날짜별 선", "02_cohort_active_days, 03_cohort_nsm_daily", "3장"],
        ["3 세그먼트 코호트", "어떤 유형이 계속 학습하는가", "100% 누적 막대, 날짜×세그먼트 히트맵, 요약표", "04_segment_summary, 05_segment_daily", "4장"],
        ["4 첫 학습일 코호트", "처음 학습한 뒤 언제 끊기는가", "삼각형 리텐션 히트맵", "06_first_active_cohort", "5장"],
        ["5 이탈 위험", "얼마나 쉬면 돌아오지 않는가", "경과일별 선, 재개자 비교 막대", "07_recency_curve, 08_resume_compare", "6장"],
        ["6 지표·가설", "어떤 Input metric이 NSM과 함께 움직이는가", "세그먼트×지표 표, 가설별 비교 막대", "04_segment_summary, 09_input_metric_hypothesis", "7장"],
        ["7 액션", "누구에게 무엇을, 무엇으로 잴 것인가", "우선순위 표 + 성공 지표 기준값", "10_action_baselines", "8장"]]
ty = table(["탭", "답하는 질문", "권장 시각화", "데이터 파일", "보고서"], rows, M, 176, [80, 132, 140, 130, CW - 482], 34, 24, 8.1)
section("공통 필터와 데이터 단위", ty + 22)
y = p("· <b>필터</b>: 세그먼트(6개), 기준 주간 학습 일수(1~7일), NSM 달성 여부. 모두 11_user_level.csv(사용자 82,467행)의 열로 들어 있어 사용자 단위로 다시 집계할 수 있다.<br/>"
      "· <b>집계 단위 주의</b>: 다음날 재학습률은 사용자-활동일 단위, 나머지 비율은 사용자 단위다. 한 화면에서 같은 축에 섞지 않는다.<br/>"
      "· <b>기간 표기</b>: 기준 주간 2013-03-01~07, 후속 관측 03-08~11(UTC). 후속 7일 NSM·장기 유지는 이 데이터로 계산할 수 없어 '측정 불가'로 표시한다.<br/>"
      "· <b>퍼널 탭</b>: 팀원 담당 퍼널 분석을 같은 필터(세그먼트·NSM 달성 여부)로 연결하면 두 분석을 한 대시보드에서 비교할 수 있다.", M, ty + 46, CW, 9.0, 14.5)
callout("<b>대시보드에서 강조할 흐름</b>  개요(NSM이 11.9%) → 누가 계속 학습하나(학습 일수·세그먼트) → 언제 끊기나(첫날 직후·하루 공백) → 무엇이 NSM을 움직이나(다음날 재학습률) → 누구에게 어떤 액션(습관 형성형).", y + 16, 62, 9.4, 15)
c.showPage()

# ---------------------------------------------------------------- 3. NSM 코호트
base(3, "NSM과 학습 일수")
title("03  /  NSM 관점의 코호트", "기준 주간 학습 일수가 늘수록<br/>후속 재학습이 단계적으로 높아졌다",
      "코호트 = 3/1-3/7 학습 일수(세그먼트 기본의 F 원값) · 후속 3/8-3/11 · 분모: 각 코호트 전체 · 코호트분석2의 37개 값과 일치", "대시보드 탭 2")
half = (CW - 12) / 2
for i, (gg, name) in enumerate([(hit, "NSM 달성군 · 4~7일"), (miss, "NSM 미달성군 · 1~3일")]):
    x = M + i * (half + 12); rect(x, 196, half, 80, PALE if i == 0 else BG, r=6)
    txt(f"{name} · {gg['n']:,}명", x + 12, 205, 9, TEAL if i == 0 else MUTED, bold=True)
    txt(pct(gg["k1"], gg["n"]), x + 12, 224, 19, TEAL if i == 0 else INK, bold=True); txt("1일 이상 재학습", x + 12, 252, 8, MUTED)
    txt(pct(gg["k2"], gg["n"]), x + half / 2 + 6, 224, 19, TEAL if i == 0 else INK, bold=True); txt("2일 이상 반복학습", x + half / 2 + 6, 252, 8, MUTED)
note("날짜별 당일 재학습률(3/8→3/11): 달성군 " + "→".join(f"{v / hit['n'] * 100:.1f}" for v in hit["daily"]) + "%, 미달성군 " +
     "→".join(f"{v / miss['n'] * 100:.1f}" for v in miss["daily"]) + "%. 3/9·3/10은 주말이다.", 284)
section("학습 일수별 코호트 (1~7일)", 318)
rect(M, 342, 9, 9, MID); txt("1일 이상 재학습", M + 14, 340, 8, MUTED); rect(M + 118, 342, 9, 9, TEAL); txt("2일 이상 반복학습", M + 132, 340, 8, MUTED)
cx, cy, ch = M + 30, 366, 136; cwid = CW - 30
for v in [0, 50, 100]:
    yy = cy + ch * (1 - v / 100); line(cx, yy, cx + cwid, yy); txt(f"{v}%", cx - 6, yy - 4, 7.5, MUTED, align="right")
gw = cwid / 7; bw = gw * 0.32
for i, d in enumerate(range(1, 8)):
    gx = cx + i * gw + gw * 0.16
    for j, (val, col) in enumerate([(r1[d], MID), (r2[d], TEAL)]):
        bx = gx + j * (bw + 2); bh = ch * val / 100; rect(bx, cy + ch - bh, bw, bh, col)
        txt(f"{val:.1f}", bx + bw / 2, cy + ch - bh - 11, 7.2, TEAL if j else MUTED, bold=bool(j), align="center")
    txt(f"{d}일", cx + i * gw + gw / 2, cy + ch + 6, 9, INK, bold=(d in (2, 3)), align="center")
    txt(f"n={days.loc[d, 'n']:,}", cx + i * gw + gw / 2, cy + ch + 20, 7.3, MUTED, align="center")
line(cx + 3 * gw, cy - 4, cx + 3 * gw, cy + ch, ORANGE, 1); txt("NSM 기준(4일)", cx + 3 * gw + 4, cy - 4, 7.5, ORANGE, bold=True)
note(f"1일 학습자가 {days.loc[1, 'n']:,}명({rate(days.loc[1, 'n'], 82467):.1f}%). 세그먼트 기본의 'NSM 4일 선정 근거' 표(복귀율 21.8%→96.6%)와 같은 결과다.", cy + ch + 38)
section("마지막 학습일을 3/7로 맞춰도 계단은 유지됐다", 586)
rw = (CW - 92) / 7
table(["학습 일수"] + [f"{d}일" for d in range(1, 8)], [["2일 이상"] + [pct(rec1_days.loc[d, "k2"], rec1_days.loc[d, "n"]) for d in range(1, 8)],
      ["인원"] + [f"{rec1_days.loc[d, 'n']:,}" for d in range(1, 8)]], M, 608, [92] + [rw] * 7, 21, 22, 8.3)
callout(f"<b>4일은 급변점이 아니라 계단의 한 칸이었다.</b>  1일 이상 재학습 증가폭: 1→2일 +{r1[2] - r1[1]:.1f}%p, 2→3일 +{r1[3] - r1[2]:.1f}%p, 3→4일 +{r1[4] - r1[3]:.1f}%p.<br/>NSM은 목표선으로 두고, 개입은 바로 아래 단계(2~3일 학습자, 그중 습관 형성형)를 겨냥한다.", 690, 66, 9.5, 15)
c.showPage()

# ---------------------------------------------------------------- 4. 세그먼트 코호트
base(4, "세그먼트 코호트")
title("04  /  행동 유형별 코호트", "세그먼트마다 후속 반복학습이<br/>12배 가까이 차이 났다",
      "코호트 = 세그먼트 기본의 6개 세그먼트(3/1-3/7 RFM 규칙) · 분모: 각 세그먼트 전체", "대시보드 탭 3")
for x, lab, col in [(M, "후속 학습 없음", GRAY), (M + 112, "1일 학습", MID), (M + 196, "2일 이상 학습", TEAL)]:
    rect(x, 184, 9, 9, col); txt(lab, x + 14, 182, 8.2, MUTED)
barx = M + 118; barw = CW - 180
for i, s in enumerate(SEG):
    yy = 204 + i * 26; n = seg.loc[s, "n"]; k1, k2 = seg.loc[s, "k1"], seg.loc[s, "k2"]
    txt(s, M, yy, 9.4, bold=(s == "습관 형성형")); txt(f"n={n:,}", M, yy + 12.5, 7.3, MUTED)
    xx = barx
    for cnt, col in [(n - k1, GRAY), (k1 - k2, MID), (k2, TEAL)]:
        w = barw * cnt / n; rect(xx, yy + 1, w, 17, col); xx += w
    txt(pct(k2, n), W - M, yy + 4, 9.4, TEAL, bold=True, align="right")
rows = []
for s in SEG:
    n = seg.loc[s, "n"]
    rows.append([s, f"{seg.loc[s, 'cust']:.1f}%", f"{seg.loc[s, 'vol']:.1f}%", f"{seg.loc[s, 'conc']:.2f}"] +
                [f"{rate(seg.loc[s, f'd{d.day}'], n):.1f}" for d in DATES] + [pct(seg.loc[s, "k1"], n), pct(seg.loc[s, "k2"], n)])
ty = table(["세그먼트", "고객 비중", "학습량 비중", "집중도", "3/8", "3/9", "3/10", "3/11", "1일 이상", "2일 이상"], rows, M, 366,
           [82, 50, 56, 44, 38, 38, 38, 38, 56, CW - 440], 22, 24, 8.2)
note(f"날짜 칸 = 당일 학습 비율(%). 6개 세그먼트의 2일 이상 반복학습 차이는 유의했다(χ²={CHI2[0]:,.0f}, 자유도 5, p&lt;0.001). '1일 이상'은 세그먼트 기본의 4일 복귀율과 같은 값이다.", ty + 6)
section("마지막 학습일을 맞춰도 순서는 유지됐다", 588)
rw = (CW - 104) / 3
rr = [[lab] + [f"{pct(seg_rec.loc[(r, s), 'k2'], seg_rec.loc[(r, s), 'n'])} · n={seg_rec.loc[(r, s), 'n']:,}" for s in ["꾸준형", "습관 형성형", "최근 단발형"]]
      for r, lab in [(1, "3/7 (어제)"), (2, "3/6 (이틀 전)")]]
ty = table(["마지막 학습", "꾸준형", "습관 형성형", "최근 단발형"], rr, M, 610, [104, rw, rw, rw], 22, 23, 8.5)
callout(f"<b>대시보드 포인트</b>  꾸준형은 고객 {seg.loc['꾸준형', 'cust']:.1f}%로 학습량 {seg.loc['꾸준형', 'vol']:.1f}%를 만든다. 가장 큰 그룹인 멈춤-저활동형({seg.loc['멈춤-저활동형', 'cust']:.1f}%)은 학습량 {seg.loc['멈춤-저활동형', 'vol']:.1f}%, 반복학습 {pct(seg.loc['멈춤-저활동형', 'k2'], seg.loc['멈춤-저활동형', 'n'])}다. 세그먼트는 기준 주간 행동으로 정의했으므로 이 차이는 분류의 타당성 확인이며 개입 효과가 아니다.", ty + 14, 74, 9.3, 14.8)
c.showPage()

# ---------------------------------------------------------------- 5. 첫 학습일 코호트
base(5, "첫 학습일 코호트")
title("05  /  관측 주 첫 학습일 코호트", "처음 학습한 다음날 다시 학습한 사용자는<br/>4명 중 1명 수준이었다",
      "코호트 = first_active(관측 주 첫 학습일, 세그먼트 기본 변수표의 '코호트 분석' 용도) · 칸 = 첫 학습일 k일 뒤 학습 비율(%)", "대시보드 탭 4")
labw = 110; ncol = 10; cellw = (CW - labw) / ncol; y0 = 196
txt("첫 학습일 / 인원", M, y0, 8.3, MUTED, bold=True)
for k in range(1, ncol + 1): txt(f"D{k}", M + labw + (k - .5) * cellw, y0, 8.3, MUTED, bold=True, align="center")
WD = ["금", "토", "일", "월", "화", "수", "목"]
for i, row in enumerate(TRI):
    yy = y0 + 18 + i * 30
    txt(f"3/{row['first'].day} ({WD[i]}) · {row['n']:,}", M, yy + 9, 8.6, bold=(i == 0))
    for k in range(1, ncol + 1):
        xx = M + labw + (k - 1) * cellw
        if k in row["D"]:
            v = row["D"][k] / row["n"]; rect(xx + 1.5, yy, cellw - 3, 26, heat(min(v / .35, 1)), r=2)
            txt(f"{v * 100:.1f}", xx + cellw / 2, yy + 9, 7.8, white if v > .22 else INK, align="center")
        else: rect(xx + 1.5, yy, cellw - 3, 26, BG, r=2)
d1 = [r["D"][1] / r["n"] * 100 for r in TRI]; ylast = y0 + 18 + 7 * 30 + 8
note("3/1 코호트에는 데이터가 2/28 저녁부터 시작해 이미 학습 중이던 사용자가 많이 섞여 있다. first_active는 가입일이 아니다. 3/8 이후 칸은 후속 관측 기간이다.", ylast)
section("읽을 점", ylast + 40)
_t = TRI[1]; _d9 = _t["D"][9] / _t["n"] * 100
y = p(f"<b>· 첫날 이후 바로 이어진 비율이 낮다.</b>  3/2-3/7 코호트의 D1은 {min(d1[1:]):.1f}-{max(d1[1:]):.1f}%다. Input metric '다음날 재학습률'이 가장 먼저 무너지는 지점이다.", M, ylast + 64, CW, 9.2, 14.2)
y = p(f"<b>· 가장 큰 하락은 첫날 직후다.</b>  3/2 코호트는 D1 {d1[1]:.1f}% 뒤 D9 {_d9:.1f}%까지 하루 평균 {(d1[1] - _d9) / 8:.1f}%p씩 완만하게 줄었다.", M, y + 6, CW, 9.2, 14.2)
y = p(f"<b>· 요일 영향이 섞인다.</b>  3/4 코호트는 토·일인 D5·D6이 {TRI[3]['D'][5] / TRI[3]['n'] * 100:.1f}·{TRI[3]['D'][6] / TRI[3]['n'] * 100:.1f}%로 월요일 D7 {TRI[3]['D'][7] / TRI[3]['n'] * 100:.1f}%보다 낮았다.", M, y + 6, CW, 9.2, 14.2)
callout("두 원본 파일 모두 이 코호트가 없었다(코호트분석2는 제외를 명시). 세그먼트 기본이 first_active를 코호트용 변수로 만들어 둔 만큼 통합본에 추가했다. 대시보드에서는 세그먼트 필터와 함께 보면 첫날 이후 이탈이 어느 유형에서 큰지 확인할 수 있다.", y + 14, 62, 9.2, 14.8)
c.showPage()

# ---------------------------------------------------------------- 6. 이탈 위험
base(6, "비활동과 이탈 위험")
title("06  /  비활동과 재학습", "하루를 쉬는 순간<br/>재학습 가능성이 가장 크게 떨어졌다",
      "분석 질문 3(이탈 위험) · 노션 가설 후보 5 · 결과: 3/8-3/11 중 1일 이상 학습 · 학습 일수를 같게 두고 비교", "대시보드 탭 5")
section("마지막 학습 후 경과일별 후속 재학습률", 186)
px, py, pw, ph = M + 34, 228, CW - 50, 148
for v in [0, 20, 40, 60]:
    yy = py + ph * (1 - v / 60); line(px, yy, px + pw, yy); txt(f"{v}%", px - 6, yy - 4, 7.5, MUTED, align="right")
for ad_, col in [(1, TEAL), (2, ORANGE)]:
    cur = rec_curve.loc[ad_]; ks = list(cur.index)
    pts = [(px + (k - 1) * pw / 6, py + ph * (1 - rate(cur.loc[k, "k1"], cur.loc[k, "n"]) / 60)) for k in ks]
    for a, b in zip(pts, pts[1:]): line(*a, *b, col, 2)
    for (xx, yy), k in zip(pts, ks):
        c.setFillColor(col); c.circle(xx, H - yy, 2.8, fill=1, stroke=0)
        txt(f"{rate(cur.loc[k, 'k1'], cur.loc[k, 'n']):.1f}", xx, yy - (14 if ad_ == 2 else -6), 7.4, col, bold=True, align="center")
rect(M, 208, 9, 9, TEAL); txt("기준 주간 1일 학습", M + 14, 206, 8, MUTED); rect(M + 130, 208, 9, 9, ORANGE); txt("기준 주간 2일 학습", M + 144, 206, 8, MUTED)
for k in range(1, 8): txt(f"{k}일 전", px + (k - 1) * pw / 6, py + ph + 8, 8.3, MUTED, align="center")
txt("마지막 학습일 (3/8 기준)", px + pw, py + ph + 22, 7.6, MUTED, align="right")
drop1 = rate(rc1.loc[1, "k1"], rc1.loc[1, "n"]) - rate(rc1.loc[2, "k1"], rc1.loc[2, "n"]); drop2 = rate(rc1.loc[2, "k1"], rc1.loc[2, "n"]) - rate(rc1.loc[3, "k1"], rc1.loc[3, "n"])
note(f"1일 학습자는 마지막 학습이 어제→이틀 전이 되면 {drop1:.1f}%p, 이틀→사흘 전이면 {drop2:.1f}%p 떨어졌고 이후 완만했다. 세그먼트 기본이 R≥4(최근 2일)를 '활동 중' 경계로 둔 근거와도 맞는다.", py + ph + 40)
section("같은 날 돌아온 사용자: 이어서 학습 vs 하루 쉬고 재개", 476)
rows = []
for sg_ in ["꾸준형", "습관 형성형", "최근 단발형"]:
    (n0, k0), (n1, k1_) = RESUME[(sg_, "cont")], RESUME[(sg_, "rest")]
    rows.append([sg_, f"{pct(k0, n0)} · n={n0:,}", f"{pct(k1_, n1)} · n={n1:,}", f"{rate(k0, n0) - rate(k1_, n1):.1f}%p"])
ty = table(["3/8에 학습한 사용자", "3/7에도 학습 (이어서)", "3/6이 마지막 (하루 쉬고 재개)", "차이"], rows, M, 498, [128, 140, 160, CW - 428], 23, 24, 8.7)
note(f"결과 = 3/9·3/10 중 추가 학습 비율. 습관 형성형 차이 {pa * 100 - pb * 100:.1f}%p(95% CI ±{RES_CI:.1f}%p, z={RES_Z:.2f}). 다음 두 날이 주말인 같은 날짜끼리의 관측 비교(코호트분석의 재개자 비교를 원본에서 재계산).", ty + 6)
callout("<b>이탈 위험 신호는 '하루 공백'이다.</b>  공백이 생기기 전 다음 학습을 약속하게 하거나, 쉬었다 돌아온 순간 다음 학습을 연결하는 개입이 가장 큰 하락 구간을 겨냥한다. 기록 없음은 이 데이터에 학습 기록이 없다는 뜻이며 영구 이탈은 아니다.", 666, 74, 9.4, 15)
c.showPage()

# ---------------------------------------------------------------- 7. Input metric · 가설
base(7, "Input metric과 가설")
title("07  /  Input metric과 가설", "다음날 재학습률만 NSM과 같은 방향이었고,<br/>규칙적 학습자 비율은 정의부터 다시 봐야 한다",
      "정의: 세그먼트 기본 Input Metrics 표 · 대상: 세션 3개 이상 사용자(다음날 재학습률 제외)", "대시보드 탭 6")
rows = []
for s in SEG:
    rows.append([s, pct(NEXT_SEG.loc[s, "sum"], NEXT_SEG.loc[s, "size"]), f"{int(im_seg.loc[s, 'n']):,}", f"{im_seg.loc[s, 'reg'] * 100:.1f}%",
                 f"{im_seg.loc[s, 'imp'] * 100:.1f}%", f"{im_seg.loc[s, 'rev'] * 100:.1f}%"])
rows.append(["전체", f"{IM['next']:.1f}%", f"{IM['elig']:,}", f"{IM['regular']:.1f}%", f"{IM['improved']:.1f}%", f"{IM['review_med']:.1f}%"])
ty = table(["세그먼트", "다음날 재학습률", "세션 3개+ 인원", "규칙적 학습자 비율", "학습 성과 개선율", "적정 간격 복습(중앙값)"], rows, M, 182,
           [92, 82, 82, 88, 88, CW - 432], 20, 30, 8.3)
section("가설별 확인 (후속 2일 이상 반복학습)", ty + 18)
def rr_(tab, k): return f"{rate(tab.loc[k, 'k2'], tab.loc[k, 'n']):.1f}% · n={int(tab.loc[k, 'n']):,}"
rows = [["가설 1 규칙성", "규칙적(CV&lt;1)", rr_(reg_tab, 1.0), rr_(reg_habit, 1.0)], ["", "불규칙(CV≥1)", rr_(reg_tab, 0.0), rr_(reg_habit, 0.0)],
        ["가설 2 성과 변화", "후반 정답률 상승", rr_(imp_tab, 1.0), rr_(imp_habit, 1.0)], ["", "상승 없음", rr_(imp_tab, 0.0), rr_(imp_habit, 0.0)]]
for k_ in rv_tab.index:
    rows.append(["가설 3 복습 타이밍" if k_ == rv_tab.index[0] else "", f"적정 간격 비율 {k_}", rr_(rv_tab, k_), rr_(rv_habit, k_) if k_ in rv_habit.index else "-"])
ty2 = table(["가설", "집단", "전체", "습관 형성형"], rows, M, ty + 40, [100, 120, 150, CW - 370], 19, 22, 8.2)
regd1 = reg_by_days.loc[1, "mean"] * 100; regd2 = reg_by_days.loc[2:, "mean"].mul(reg_by_days.loc[2:, "size"]).sum() / reg_by_days.loc[2:, "size"].sum() * 100
y = p(f"<b>· 가설 1:</b> 규칙적 학습자의 반복학습이 오히려 낮았다. 1일만 학습한 사용자의 {regd1:.1f}%가 '규칙적'으로 분류되는 반면 2일 이상 학습자는 {regd2:.1f}%뿐이다. 하루 안의 세션 간격과 며칠에 걸친 간격이 한 CV에 섞여, 이 지표는 '하루에 몰아서 학습'을 규칙성으로 잡는다. "
      "→ 활동일 간 간격 기준으로 정의를 바꾸거나, 대시보드에서는 다음날 재학습률로 대체할 것을 권한다.", M, ty2 + 8, CW, 8.5, 12.8)
y = p("<b>· 가설 2:</b> 성과 개선 여부에 따른 차이가 없었다(0.6%p 이내). <b>· 가설 3:</b> 적정 간격 복습 비율이 0%인 집단이 가장 낮고 10~25%까지 오른 뒤 정체했다. 여러 날 학습해야 12~48시간 간격이 생기므로 학습 일수의 영향이 섞인다. "
      "노션 가설 3은 '복습 간격 → 학습 성과', 세그먼트 기본은 '복습 타이밍 → 리텐션'으로 결과 변수가 다르니 팀에서 하나로 정해야 한다.", M, y + 4, CW, 8.5, 12.8)
c.showPage()

# ---------------------------------------------------------------- 8. 액션
base(8, "액션과 실험")
title("08  /  누구에게 무엇을", "세그먼트 기본의 액션 표에<br/>성공 지표의 현재 기준값을 붙였다",
      "대시보드 탭 7은 액션별 '지금 값'을 보여 주고, 실험 후 같은 정의로 비교하는 화면이다", "대시보드 탭 7")
rows = [["1", "습관 형성형", "주간 4일 목표·진행률, 간격 벌어지기 전 알림", "4일 이상 학습 전환율", f"후속 4일 모두 학습 {BASE['habit_all4']:.1f}% (2일 이상 {BASE['habit_ret2']:.1f}%)"],
        ["2", "멈춤-꾸준형", "\"잊기 전에 복습\" 알림", "4일 내 복귀율", f"{BASE['pk_ret1']:.1f}%"],
        ["2", "멈춤-몰입형", "\"매일 소량\" 목표 제안", "재학습일 수", f"후속 4일 평균 {BASE['pm_fd']:.2f}일"],
        ["3", "꾸준형", "평소 시간대 알림, 연속 학습 보상", "NSM 유지율", f"측정 불가(다음 7일 필요) · 대체: 2일 이상 {BASE['steady_ret2']:.1f}%"],
        ["4", "최근 단발형", "첫 학습 직후 성취 피드백, 다음 날 안내", "다음 날 복귀율", f"3/7 학습자의 3/8 학습 {BASE['single_next']:.1f}% (n={BASE['single_next_n']:,})"],
        ["5", "멈춤-저활동형", "저비용 일괄 리마인드", "알림 반응률", f"측정 불가(알림 로그 없음) · 대체: 4일 내 복귀율 {BASE['low_ret1']:.1f}%"]]
ty = table(["순위", "세그먼트", "액션안 (세그먼트 기본)", "성공 지표", "현재 기준값"], rows, M, 176, [36, 80, 150, 90, CW - 356], 32, 24, 8.2)
section("1순위 실험안 (두 코호트 파일의 제안을 합침)", ty + 20)
ty2 = table(["항목", "내용"],
            [["대상", f"습관 형성형 {seg.loc['습관 형성형', 'n']:,}명 (2~3일 학습 + 최근 학습). 같은 2~3일 학습자라도 멈춤 계열은 반복학습 {pct(T23P.ret2.sum(), len(T23P))}로 습관 형성형({pct(T23H.ret2.sum(), len(T23H))})보다 낮다"],
             ["시점", "학습을 마친 직후(하루 공백 전). 하루 이상 쉬고 돌아온 경우에도 같은 시점에 노출"],
             ["개입", "다음 학습일 정하기 + 주간 4일 목표 표시 (코호트분석2의 4일 목표 + 코호트분석의 다음 학습일 계획)"],
             ["배정", "사용자 단위 1:1 무작위, 안내 미노출자도 배정군 유지"],
             ["주 지표", f"다음날 재학습률 (노션·세그먼트 기본 Input metric). 현재 습관 형성형 {pct(NEXT_SEG.loc['습관 형성형', 'sum'], NEXT_SEG.loc['습관 형성형', 'size'])}"],
             ["보조 지표", "후속 7일 NSM 달성률(코호트분석2), 2일 이상 반복학습률"]], M, ty + 42, [70, CW - 70], 26, 22, 8.4)
callout("<b>측정 한계</b>  액션 효과, 7일 NSM 유지, 알림 반응은 이 데이터로 확인할 수 없다(세그먼트 기본도 같은 한계를 명시). 표본 수는 팀이 목표 개선 폭을 정한 뒤 산정한다.", ty2 + 14, 52, 9.2, 14.5)
c.showPage()

# ---------------------------------------------------------------- 9. 통합 기준
base(9, "통합 기준")
title("09  /  두 파일을 어떻게 통합했나", "노션과 세그먼트 기본에 비춰 평가하고<br/>대시보드에 필요한 것만 남겼다",
      "중심 파일: 코호트분석(세그먼트 축·통계 검정·이탈 위험) · 코호트분석2에서 NSM·학습 일수 코호트와 실험 지표를 가져옴")
table(["기준", "코호트분석", "코호트분석2", "통합본"],
      [["세그먼트 기본의 6개 세그먼트를 코호트 축으로", "O", "X (학습 일수만)", "탭 3"],
       ["NSM(7일 중 4일) 중심 해석", "△ (KPI로만)", "O", "탭 1·2"],
       ["세그먼트 기본 Input Metrics 4개", "X", "X", "탭 1·6 신규"],
       ["first_active 코호트", "X", "X (제외 명시)", "탭 4 신규"],
       ["이탈 위험(분석 질문 3)", "O", "X", "탭 5"],
       ["통계적 유의성(노션 성공 기준)", "O", "X", "탭 3·5"],
       ["세그먼트 기본의 전처리 정의", "O", "△ (학습량 중복 제거 오류)", "정정"],
       ["세그먼트 기본 액션과 연결", "X", "△ (2~3일군)", "탭 7"]],
      M, 176, [196, 96, 120, CW - 412], 22, 24, 8.3, boldfirst=False)
y = note("O 충족 · △ 부분 · X 미충족", 382)
y = p("<b>뺀 것</b>  코호트분석의 A1·완전 관측 같은 자체 용어, 표본 수 8,692명 등 실험 설계 세부, 회귀(OR) 결과는 코호트 범위를 넘어 제외했다. 가설 결과는 노션 '가설 검증' 페이지, 실험 세부는 별도 설계 문서로 옮길 것을 권한다.", M, 404, CW, 8.9, 13.8)
y = p("<b>정정</b>  코호트분석2의 학습량 중앙값 27은 user_id·timestamp·session_seen 세 열로 중복을 지울 때 나오는 값(서로 다른 단어 기록 손실)이다. 세그먼트 기본 정의의 중앙값은 75다. 팀원 표의 나머지 37개 값은 원본 재계산과 일치했다.", M, y + 6, CW, 8.9, 13.8)
y = p("<b>팀 결정이 필요한 것</b>  ① 규칙적 학습자 비율의 정의 수정 여부(탭 6) ② 가설 3의 결과 변수(학습 성과 vs 리텐션) ③ 실험 주 지표를 다음날 재학습률로 확정할지.", M, y + 6, CW, 8.9, 13.8)
section("데이터와 재현", y + 20)
note(f"Duolingo Spaced Repetition Dataset(Settles &amp; Meeder, 2016) 원본 {N_RAW:,}행 → 12개 열 완전 중복 {N_DUP}행 제거 → 3/1-3/11({N_USERS_311:,}명) → 관측 주 3/1-3/7 {len(u):,}명. "
     "세그먼트 인원·M 경계(24·53·108·239)가 세그먼트 기본과 일치. 세션 = 사용자+timestamp, 학습 문항 수 = session_seen 합. "
     "생성 코드: 코호트분석_통합/build_cohort_dashboard.py (원본 → 집계 → 보고서·CSV, 두 파일과 세그먼트 기본 수치 대조 포함).", y + 44, 8.2, 12.5)
c.showPage()

# ---------------------------------------------------------------- 10. 데이터 사전
base(10, "대시보드 데이터 사전")
title("10  /  대시보드 데이터 사전", "dashboard_data 폴더의 파일과 열",
      "모든 비율은 % 단위 · 날짜는 UTC · 파일은 UTF-8(BOM)로 엑셀에서 바로 열린다")
table(["파일", "단위(행)", "주요 열", "쓰는 탭"],
      [["01_kpi_summary", "지표 10개", "지표, 정의, 인원_또는_분자, 값, 출처", "1"],
       ["02_cohort_active_days", "학습 일수 7", "users, ret1_rate, ret2_rate, nsm_group, last3_7_ret2_rate", "2"],
       ["03_cohort_nsm_daily", "NSM 군 × 날짜 8", "daily_rate, cum_rate", "2"],
       ["04_segment_summary", "세그먼트 6", "user_share, volume_share, concentration, ret1/ret2(+CI), next_day_rate, regular_rate, improved_rate, review_ok_median", "1·3·6"],
       ["05_segment_daily", "세그먼트 × 날짜 24", "active_users, daily_rate", "3"],
       ["06_first_active_cohort", "첫 학습일 × D1~D10 70", "active_users, rate, observed(관측 가능 여부)", "4"],
       ["07_recency_curve", "학습 일수 × 경과일", "ret1_rate, ret2_rate", "5"],
       ["08_resume_compare", "세그먼트 × 집단 6", "d1d2_rate", "5"],
       ["09_input_metric_hypothesis", "지표 × 집단", "metric, scope, group, ret2_rate", "6"],
       ["10_action_baselines", "액션 6", "success_metric, baseline_definition, baseline_value", "7"],
       ["11_user_level", "사용자 82,467", "segment, R/F/M, first_active, a8~a11, ret1, ret2, gap_cv, regular, improved, review_ok", "필터 전체"]],
      M, 172, [118, 92, CW - 262, 52], 34, 24, 7.9)
note("'observed=False'인 첫 학습일 코호트 칸은 관측 기간 밖이므로 0이 아니라 빈칸으로 그린다. 11_user_level의 Input metric 열은 세션 3개 미만 사용자에서 비어 있다(정의상 대상 아님).", 586)
c.showPage(); c.save()

# =============================================================== 4. 검증
reader = PdfReader(PDF); assert len(reader.pages) == TOTAL
text = "\n".join(pg.extract_text() for pg in reader.pages)
for req in ["82,467", "9,834", "77.8%", "29.7%", "55.9%", "4.7%", "49.7%", "42.0%", "35.8%", "25.9%", "51.6%", "9.3%"]:
    assert req in text, req
summary = {"source_rows": N_RAW, "baseline_users": len(u), "nsm": int((u.active_days >= 4).sum()), "input_metrics": IM,
           "segment_n": seg.n.to_dict(), "chi2": float(CHI2[0]), "files": sorted(os.listdir(DATA))}
with open(os.path.join(OUTDIR, "cohort_dashboard_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(json.dumps({"pdf": PDF, "pages": TOTAL, "IM": IM}, ensure_ascii=False, default=str))
