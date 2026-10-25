"""듀오링고 코호트 분석 통합본 (코호트분석 + 코호트분석2) — 노션 문서 형식 PDF.

두 코호트 분석 파일의 코호트 분석 내용만 통합한다. 세그먼트는 '세그먼트 기본'(세그먼트 분석 최신 코드) 규칙을 그대로 적용한다.
실행: pip install pandas numpy matplotlib playwright pypdf && playwright install chromium
      python build_cohort_report.py <원본 csv 또는 csv.gz> <출력 폴더>
"""
import sys, os, json, html
from math import sqrt
import numpy as np, pandas as pd

SRC, OUTDIR = sys.argv[1], sys.argv[2]
CHART = os.path.join(OUTDIR, "charts"); os.makedirs(CHART, exist_ok=True)
PDF = os.path.join(OUTDIR, "코호트분석 통합본.pdf")
T = pd.Timestamp

# 1. 세그먼트 분석 최신 코드의 전처리 (12개 열 완전 중복 제거, 3/1~3/11 UTC)
df = pd.read_csv(SRC, dtype={"user_id": "category", "learning_language": "category", "ui_language": "category",
                             "lexeme_id": "category", "lexeme_string": "category"})
N_RAW = len(df); df = df.drop_duplicates(); N_DUP = N_RAW - len(df)
first_trace = (df.timestamp - df.delta).groupby(df.user_id.astype(str)).min()      # 신규 추정용(퍼널 분석과 같은 방식)
df = df[["user_id", "timestamp", "session_seen", "session_correct"]]
df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
df = df[(df["dt"] >= "2013-03-01") & (df["dt"] < "2013-03-12")].copy()
df["date"] = df["dt"].dt.normalize(); df["user_id"] = df["user_id"].astype(str)
N_USERS_311 = df["user_id"].nunique()
ud = df.groupby(["user_id", "date"]).agg(seen=("session_seen", "sum"), sessions=("timestamp", "nunique")).reset_index()
del df

# 2. 기준 주간(3/1~3/7) 사용자 집계와 6개 세그먼트
obs = ud[ud.date < T("2013-03-08")]; fol = ud[ud.date >= T("2013-03-08")]
u = obs.groupby("user_id").agg(first_active=("date", "min"), last_active=("date", "max"), active_days=("date", "nunique"),
                               words_seen=("seen", "sum"))
u["recency"] = (T("2013-03-08") - u.last_active).dt.days
u["F"] = pd.cut(u.active_days, [0, 1, 2, 3, 4, 7], labels=[1, 2, 3, 4, 5]).astype(int)
u["M"], M_EDGES = pd.qcut(u.words_seen, 5, labels=[1, 2, 3, 4, 5], retbins=True); u["M"] = u.M.astype(int)
u["R"] = pd.cut(u.recency, [0, 1, 2, 4, 6, 7], labels=[5, 4, 3, 2, 1]).astype(int)
SEG = ["꾸준형", "습관 형성형", "최근 단발형", "멈춤-꾸준형", "멈춤-몰입형", "멈춤-저활동형"]
cond = [(u.R >= 4) & (u.F >= 4), (u.R >= 4) & u.F.isin([2, 3]), (u.R >= 4) & (u.F == 1), (u.R <= 3) & (u.F >= 3), (u.R <= 3) & (u.M >= 4)]
u["segment"] = np.select(cond, SEG[:5], default=SEG[5])
u["new"] = pd.to_datetime(first_trace.reindex(u.index), unit="s") >= T("2013-03-01")

# 3. 후속 관측(3/8~3/11) 날짜별 학습 여부
DATES = list(pd.date_range("2013-03-08", "2013-03-11")); AC = [f"a{d.day}" for d in DATES]
act = set(zip(fol.user_id, fol.date))
for d, c in zip(DATES, AC): u[c] = [int((i, d) in act) for i in u.index]
u["fdays"] = u[AC].sum(axis=1); u["ret1"] = (u.fdays >= 1).astype(int); u["ret2"] = (u.fdays >= 2).astype(int)
u["first_return"] = u[AC].values.argmax(axis=1).astype(float); u.loc[u.ret1 == 0, "first_return"] = np.nan

assert N_DUP == 81 and N_USERS_311 == 109504 and len(u) == 82467
assert (u.active_days >= 4).sum() == 9834 and u.ret1.sum() == 29240 and u.ret2.sum() == 13466
assert u.segment.value_counts().reindex(SEG).tolist() == [8882, 14583, 15402, 3627, 9303, 30670]
def rate(k, n): return k / n * 100
def pct(k, n, d=1): return f"{rate(k, n):.{d}f}%"

# ① NSM 달성 여부 코호트 (코호트분석2)
NSMG = {}
for key, sub in [("hit", u[u.active_days >= 4]), ("miss", u[u.active_days < 4])]:
    NSMG[key] = dict(n=len(sub), k1=int(sub.ret1.sum()), k2=int(sub.ret2.sum()), daily=[int(sub[c].sum()) for c in AC],
                     cum=[int((sub[AC[:i + 1]].sum(axis=1) > 0).sum()) for i in range(4)])
assert NSMG["hit"]["daily"] == [4869, 4067, 3887, 4286] and NSMG["hit"]["cum"] == [4869, 6286, 7013, 7654]
assert NSMG["miss"]["daily"] == [9977, 7649, 7365, 8139] and NSMG["miss"]["cum"] == [9977, 14801, 18301, 21586]
# ② 학습 일수 코호트 (코호트분석2) + 마지막 학습일 통제 + 학습량 교차
days = u.groupby("active_days").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
TEAM = {1: (47087, 10278, 3214), 2: (17134, 6675, 2711), 3: (8412, 4633, 2276), 4: (4748, 3310, 1931), 5: (2723, 2189, 1521), 6: (1532, 1352, 1096), 7: (831, 803, 717)}
for d_, v in TEAM.items(): assert tuple(days.loc[d_]) == v
rec1_days = u[u.recency == 1].groupby("active_days").agg(n=("F", "size"), k2=("ret2", "sum"))
MED = u.words_seen.median(); assert MED == 75
u["grp"] = np.where(u.active_days >= 4, np.where(u.words_seen >= MED, "D", "C"), np.where(u.words_seen >= MED, "B", "A"))
abcd = u.groupby("grp").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
grid = u.assign(dg=u.active_days.clip(upper=4), hi=u.words_seen >= MED).groupby(["dg", "hi"]).agg(n=("F", "size"), k2=("ret2", "sum"))
one_day_share = {g: rate(((u.grp == g) & (u.active_days == 1)).sum(), (u.grp == g).sum()) for g in ["A", "B"]}
two3 = u[u.active_days.isin([2, 3])]; T23H = two3[two3.segment == "습관 형성형"]; T23P = two3[two3.segment != "습관 형성형"]
# ③ 세그먼트 코호트 (코호트분석)
seg = u.groupby("segment").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"), **{c: (c, "sum") for c in AC}).reindex(SEG)
assert seg.k2.tolist() == [4963, 3562, 1862, 808, 841, 1430]
seg_cum = {s: [rate((u[u.segment == s][AC[:i + 1]].sum(axis=1) > 0).sum(), seg.loc[s, "n"]) for i in range(4)] for s in SEG}
seg_rec = u[u.recency.isin([1, 2])].groupby(["recency", "segment"]).agg(n=("F", "size"), k2=("ret2", "sum"))
# ④ 첫 후속 학습일 코호트 (코호트분석)
def fr_table(s):
    out = []
    for i in range(4):
        g = s[s.first_return == i]; row = {"date": DATES[i], "n": len(g), "D": {}}
        for k in range(1, 4):
            if i + k < 4: row["D"][k] = rate(g[AC[i + k]].sum(), len(g))
        out.append(row)
    g = s[s.first_return.isin([0, 1])]
    ok = sum((g[AC[int(r)+1]].iloc[j] + g[AC[int(r)+2]].iloc[j]) > 0 for j, r in enumerate(g.first_return))
    return out, (len(g), int(ok))
FR_ALL, D12_ALL = fr_table(u); FR_HAB, D12_HAB = fr_table(u[u.segment == "습관 형성형"])
assert FR_ALL[0]["n"] == 14846 and FR_HAB[0]["n"] == 4106 and D12_HAB == (5679, 2704)
RESUME = {}
for sg in ["꾸준형", "습관 형성형", "최근 단발형"]:
    s = u[(u.segment == sg) & (u.a8 == 1)]
    for r, lab in [(1, "cont"), (2, "rest")]:
        t = s[s.recency == r]; RESUME[(sg, lab)] = (len(t), int(((t.a9 + t.a10) > 0).sum()))
assert RESUME[("습관 형성형", "cont")] == (2799, 1392) and RESUME[("습관 형성형", "rest")] == (1307, 549)
(na, ka), (nb, kb) = RESUME[("습관 형성형", "cont")], RESUME[("습관 형성형", "rest")]
pa, pb = ka / na, kb / nb; RES_CI = 1.96 * sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb) * 100
# ⑤ 관측 주 첫 학습일 코호트
allact = set(zip(ud.user_id, ud.date))
TRI = []
for f in pd.date_range("2013-03-01", "2013-03-07"):
    ids = u.index[u.first_active == f]; newids = u.index[(u.first_active == f) & u.new]
    row = {"first": f, "n": len(ids), "n_new": len(newids), "D": {}, "D1_new": rate(sum((i, f + pd.Timedelta(days=1)) in allact for i in newids), len(newids))}
    for k in range(1, 11):
        d = f + pd.Timedelta(days=k)
        if d > T("2013-03-11"): break
        row["D"][k] = rate(sum((i, d) in allact for i in ids), len(ids))
    TRI.append(row)
NEW_N = int(u.new.sum())

# 부록. 대시보드용 추가 집계 (본문과 같은 기준 주간·세그먼트 규칙·후속 관측)
def wilson(k, n, z=1.96):
    p_ = k / n; den = 1 + z * z / n; c0 = (p_ + z * z / (2 * n)) / den
    h = z * sqrt(p_ * (1 - p_) / n + z * z / (4 * n * n)) / den
    return (c0 - h) * 100, (c0 + h) * 100
# A. 이탈 위험 = 후속 4일(3/8~3/11) 학습 기록 없음
u["risk"] = (u.fdays == 0).astype(int); RISK = int(u.risk.sum()); assert RISK == 82467 - 29240
# B. 세그먼트별 규모·학습량 비중·이탈 위험
WS = u.words_seen.sum()
segx = u.groupby("segment").agg(n=("F", "size"), ws=("words_seen", "sum"), risk=("risk", "sum"), k1=("ret1", "sum"), k2=("ret2", "sum")).reindex(SEG)
segx["share"] = segx.n / len(u) * 100; segx["vol"] = segx.ws / WS * 100; segx["per"] = segx.ws / segx.n
segx["ci"] = [wilson(k, n) for k, n in zip(segx.k2, segx.n)]
# C. 마지막 학습 후 경과일별 재학습 (NSM 미달성 1~3일 학습자)
rec_curve = u[u.active_days <= 3].groupby(["active_days", "recency"]).agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
assert tuple(rec_curve.loc[(1, 1)]) == (8444, 3169, 1297) and tuple(rec_curve.loc[(1, 7)]) == (7642, 1074, 256)
# D. NSM 입력 지표: 다음날 재학습률(사용자-활동일), 첫 학습일 학습량, 활동일당 세션 수
key = set(zip(obs.user_id, obs.date))
ad6 = obs[obs.date <= T("2013-03-06")]
nxt = np.array([(a, b + pd.Timedelta(days=1)) in key for a, b in zip(ad6.user_id, ad6.date)])
NEXT_ALL = (int(nxt.sum()), len(nxt)); assert NEXT_ALL == (46635, 130409)
NEXT_SEG = pd.Series(nxt).groupby(ad6.user_id.map(u.segment).values).agg(["sum", "size"]).reindex(SEG)
fv = obs.merge(u[["first_active"]], left_on="user_id", right_index=True)
u["first_vol"] = fv[fv.date == fv.first_active].groupby("user_id").seen.sum()
u["sessions"] = obs.groupby("user_id").sessions.sum(); u["spd"] = u.sessions / u.active_days
assert u.first_vol.median() == 47 and u.spd.median() == 2
# E. 세그먼트별 액션의 보조 지표 (이 데이터로 잴 수 있는 것만)
s1y = u[(u.segment == "최근 단발형") & (u.recency == 1)]; SINGLE_NEXT = (len(s1y), int(s1y.a8.sum()))
assert SINGLE_NEXT == (8444, 1795)

# 차트 (퍼널 분석 문서와 같은 스타일) ------------------------------------------------
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
FONT = os.environ.get("KR_FONT")
if FONT: font_manager.fontManager.addfont(FONT); fam = font_manager.FontProperties(fname=FONT).get_name()
else: fam = "Malgun Gothic"
BLUE, ORANGE, LBLUE = "#2a78d6", "#eb6834", "#9cc3ef"
INK, INK_2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({"font.family": fam, "axes.unicode_minus": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "axes.edgecolor": AXIS,
                     "axes.labelcolor": INK_2, "text.color": INK, "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})
r1 = {d: rate(days.loc[d, "k1"], days.loc[d, "n"]) for d in days.index}; r2 = {d: rate(days.loc[d, "k2"], days.loc[d, "n"]) for d in days.index}
hit, miss = NSMG["hit"], NSMG["miss"]

fig, ax = plt.subplots(figsize=(8, 3.6)); xs = [f"3/{d.day}" for d in DATES]
for g, col, lab in [(hit, BLUE, f"NSM 달성군 ({hit['n']:,}명)"), (miss, ORANGE, f"NSM 미달성군 ({miss['n']:,}명)")]:
    for vals, ls, sfx in [([v / g["n"] * 100 for v in g["daily"]], "-", "당일"), ([v / g["n"] * 100 for v in g["cum"]], "--", "누적")]:
        ax.plot(xs, vals, ls, marker="o", color=col, linewidth=2 if ls == "-" else 1.4, label=f"{lab} · {sfx}")
        for x_, v in zip(xs, vals): ax.text(x_, v + 2, f"{v:.1f}", ha="center", fontsize=7.5, color=col)
ax.set_ylim(0, 90); ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=8, ncol=2, loc="upper left"); ax.tick_params(axis="x", colors=INK_2, length=0)
ax.set_title("NSM 달성 여부별 날짜별 재학습률 (당일 / 누적 1일 이상)", loc="left", fontsize=12, pad=12)
fig.tight_layout(); fig.savefig(f"{CHART}/chart_01_nsm_daily.png", dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4.2)); x = np.arange(1, 8); w = 0.36
b1 = ax.bar(x - w / 2, [r1[d] for d in x], w, color=LBLUE, label="1일 이상 재학습"); b2 = ax.bar(x + w / 2, [r2[d] for d in x], w, color=BLUE, label="2일 이상 재학습")
for b, v in zip(b1, [r1[d] for d in x]): ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}", ha="center", fontsize=8, color=INK_2)
for b, v in zip(b2, [r2[d] for d in x]): ax.text(b.get_x() + b.get_width() / 2, v + 1.2, f"{v:.1f}", ha="center", fontsize=8, color=INK, fontweight="bold")
ax.axvline(3.5, color=ORANGE, linewidth=1); ax.text(3.55, 103, "NSM 기준(4일)", color=ORANGE, fontsize=9)
ax.set_xticks(x, [f"{d}일\nn={days.loc[d, 'n']:,}" for d in x], fontsize=8.5); ax.set_ylim(0, 112)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
ax.tick_params(axis="x", colors=INK_2, length=0); ax.legend(frameon=False, fontsize=9, loc="upper left")
ax.set_title("기준 주간 학습 일수별 후속 재학습률 (3/8~3/11)", loc="left", fontsize=12, pad=12)
fig.tight_layout(); fig.savefig(f"{CHART}/chart_02_active_days.png", dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 3.9)); labs = SEG[::-1]
none = [rate(seg.loc[s, "n"] - seg.loc[s, "k1"], seg.loc[s, "n"]) for s in labs]; one = [rate(seg.loc[s, "k1"] - seg.loc[s, "k2"], seg.loc[s, "n"]) for s in labs]
two = [rate(seg.loc[s, "k2"], seg.loc[s, "n"]) for s in labs]
ax.barh(labs, none, color="#e4e3dd", height=0.56, label="후속 학습 없음"); ax.barh(labs, one, left=none, color=LBLUE, height=0.56, label="1일 학습")
ax.barh(labs, two, left=[a + b for a, b in zip(none, one)], color=BLUE, height=0.56, label="2일 이상 학습")
for i, v in enumerate(two): ax.text(101, i, f"{v:.1f}%", va="center", fontsize=9, color=INK, fontweight="bold")
ax.set_xlim(0, 110); ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f}%" if v <= 100 else "")
ax.tick_params(axis="y", colors=INK_2, length=0); ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="lower left", bbox_to_anchor=(0, 1.0))
ax.set_title("세그먼트별 후속 4일 학습 분포 (오른쪽 = 2일 이상)", loc="left", fontsize=12, pad=26)
fig.tight_layout(); fig.savefig(f"{CHART}/chart_03_segment.png", dpi=200); plt.close(fig)

mat = np.full((7, 10), np.nan)
for i, r in enumerate(TRI):
    for k, v in r["D"].items(): mat[i, k - 1] = v
WD = ["금", "토", "일", "월", "화", "수", "목"]
fig, ax = plt.subplots(figsize=(8, 4.0)); ax.imshow(np.ma.masked_invalid(mat), cmap="Blues", vmin=0, vmax=35, aspect="auto")
for i in range(7):
    for j in range(10):
        if not np.isnan(mat[i, j]): ax.text(j, i, f"{mat[i, j]:.1f}", ha="center", va="center", fontsize=8, color="white" if mat[i, j] > 22 else INK)
ax.set_xticks(range(10), [f"D{k}" for k in range(1, 11)], fontsize=8.5)
ax.set_yticks(range(7), [f"3/{r['first'].day} ({WD[i]}) · {r['n']:,}" for i, r in enumerate(TRI)], fontsize=8.5)
ax.tick_params(length=0); [s_.set_visible(False) for s_ in ax.spines.values()]
ax.set_title("관측 주 첫 학습일 코호트 — 첫 학습일 k일 뒤 학습 비율(%)", loc="left", fontsize=12, pad=10)
fig.tight_layout(); fig.savefig(f"{CHART}/chart_04_first_active.png", dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 3.8))
for ad_, col in [(1, ORANGE), (2, LBLUE), (3, BLUE)]:
    rc = rec_curve.loc[ad_]; vals = (rc.k1 / rc.n * 100)
    ax.plot(vals.index, vals.values, "-o", color=col, linewidth=2, label=f"기준 주간 {ad_}일 학습")
    for x_, v in zip(vals.index, vals.values): ax.text(x_, v + 1.6, f"{v:.1f}", ha="center", fontsize=7.5, color=col)
ax.set_xticks(range(1, 8), [f"{k}일 전\n(3/{8 - k})" for k in range(1, 8)], fontsize=8.5); ax.set_ylim(0, 75)
ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f}%"); ax.grid(axis="y", color=GRID, linewidth=0.8); ax.set_axisbelow(True)
ax.tick_params(axis="x", colors=INK_2, length=0); ax.legend(frameon=False, fontsize=8.5, ncol=3, loc="upper right")
ax.set_xlabel("마지막 학습일 (3/8 기준 경과일)", fontsize=8.5)
ax.set_title("마지막 학습 후 경과일별 후속 4일 재학습률 (1일 이상)", loc="left", fontsize=12, pad=12)
fig.tight_layout(); fig.savefig(f"{CHART}/chart_05_recency.png", dpi=200); plt.close(fig)

# 문서 (노션 형식 HTML → PDF) ---------------------------------------------------------
TITLE = "코호트분석 통합본"
E = html.escape
def tbl(head, rows):
    return ("<table><thead><tr>" + "".join(f"<th>{x}</th>" for x in head) + "</tr></thead><tbody>" +
            "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows) + "</tbody></table>")
def ul(items): return "<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>"
def quote(s): return f"<blockquote>{s}</blockquote>"
def callout(icon, s): return f'<div class="callout"><span class="ci">{icon}</span><div>{s}</div></div>'
def img(name): return f'<img src="file://{CHART}/{name}">'
def code(x): return f"<code>{E(x)}</code>"
P = []; A = P.append
A(f"<h1>{TITLE}</h1>")

A("<h2>📌 코호트 분석 설계</h2>")
A(quote("<b>기준 주간의 학습 행동으로 사용자를 고정하고, 이후 4일 동안 다시 학습하는지를 추적함.</b> NSM(7일 중 4일 이상 학습)이 학습의 지속을 나타내는 지표이므로, NSM 달성 여부·학습 일수·행동 세그먼트·학습 시작일에 따라 이후 재학습이 어떻게 달라지는지 비교함."))
A(ul(["데이터: Duolingo Spaced Repetition Dataset. 세그먼트 분석 최신 코드와 같은 전처리(12개 열 완전 중복 81행 제거, 하루가 온전한 3/1~3/11 UTC)",
      "기준 주간: 2013-03-01 ~ 03-07 (UTC). 대상: 기준 주간에 1일 이상 학습한 사용자 <b>82,467명</b>" +
      ul(["3/8~3/11에만 나타난 27,037명은 기준 주간 행동이 없어 제외"]),
      "후속 관측: 2013-03-08 ~ 03-11 (UTC) 4일. 기준 주간 이후 결과로 코호트를 다시 나누지 않음",
      "코호트 종류" + ul(["① NSM 달성 여부: 기준 주간 4~7일 학습(달성) / 1~3일(미달성)", "② 학습 일수: 기준 주간 학습 일수 1~7일",
                       "③ 행동 세그먼트: 세그먼트 기본의 6개 세그먼트(R·F·M 규칙)", "④ 첫 후속 학습일: 후속 기간 중 처음 다시 학습한 날(D0)",
                       "⑤ 관측 주 첫 학습일: 기준 주간에 처음 학습한 날(가입일 아님)"])]))
A(tbl(["지표", "정의"], [["당일 재학습률", "해당 날짜에 학습한 사용자 ÷ 코호트 전체"], ["누적 재학습률", "해당 날짜까지 1일 이상 학습한 사용자 ÷ 코호트 전체"],
                       ["1일 이상 재학습률", "후속 4일 중 1일 이상 학습 ÷ 코호트 전체"], ["2일 이상 재학습률", "후속 4일 중 서로 다른 2일 이상 학습 ÷ 코호트 전체 (반복학습)"]]))
A(ul(["분모는 처음 정한 코호트 전체 인원. 후속 학습이 없는 사용자도 분모에 남김.", "관측 기간(3/11)을 넘는 날짜는 0%가 아니라 '미관측'으로 둠."]))

A("<h2>📊 ① NSM 달성 여부 코호트</h2>")
A(tbl(["구분", "유저 수", "비율", "1일 이상 재학습", "2일 이상 재학습"],
      [["NSM 달성군 (4~7일)", f"{hit['n']:,}", pct(hit['n'], 82467, 2), f"<b>{pct(hit['k1'], hit['n'], 2)}</b>", f"<b>{pct(hit['k2'], hit['n'], 2)}</b>"],
       ["NSM 미달성군 (1~3일)", f"{miss['n']:,}", pct(miss['n'], 82467, 2), pct(miss['k1'], miss['n'], 2), pct(miss['k2'], miss['n'], 2)],
       ["합계", "82,467", "100.00%", pct(29240, 82467, 2), pct(13466, 82467, 2)]]))
A(img("chart_01_nsm_daily.png"))
A(tbl(["집단", "날짜", "당일 재학습자", "당일 재학습률", "누적 재학습자", "누적 재학습률"],
      [[nm, f"3/{d.day}", f"{g['daily'][i]:,}", pct(g['daily'][i], g['n'], 2), f"{g['cum'][i]:,}", pct(g['cum'][i], g['n'], 2)]
       for nm, g in [("NSM 달성군", hit), ("NSM 미달성군", miss)] for i, d in enumerate(DATES)]))
A(ul([f"NSM 달성군은 모든 날짜에서 미달성군보다 재학습률이 높음. 3/11 누적 1일 이상 재학습률은 {pct(hit['k1'], hit['n'], 2)} vs {pct(miss['k1'], miss['n'], 2)}로 {rate(hit['k1'], hit['n']) - rate(miss['k1'], miss['n']):.2f}%p 차이(약 {rate(hit['k1'], hit['n']) / rate(miss['k1'], miss['n']):.2f}배).",
      f"당일 재학습률은 달성군 약 40~50%, 미달성군 약 10~14% 수준을 유지. 3/9(토)·3/10(일)에 두 집단 모두 낮아짐.",
      "다만 NSM 달성 자체가 높은 재학습률을 만들었다고 단정할 수는 없음."]))

A("<h2>📊 ② 학습 일수별 코호트</h2>")
A(img("chart_02_active_days.png"))
A(tbl(["학습 일수", "코호트 규모", "1일 이상 재학습자", "1일 이상 재학습률", "2일 이상 재학습자", "2일 이상 재학습률"],
      [[f"{d}일", f"{days.loc[d, 'n']:,}", f"{days.loc[d, 'k1']:,}", f"{r1[d]:.2f}%", f"{days.loc[d, 'k2']:,}", f"{r2[d]:.2f}%"] for d in range(1, 8)] +
      [["합계", "82,467", "29,240", pct(29240, 82467, 2), "13,466", pct(13466, 82467, 2)]]))
A(ul([f"학습 일수가 늘수록 재학습률이 단계적으로 높아짐. 1일 {r1[1]:.2f}% → 4일 {r1[4]:.2f}% → 7일 {r1[7]:.2f}%.",
      f"3일 → 4일 증가폭({r1[4] - r1[3]:.2f}%p)은 1→2일({r1[2] - r1[1]:.2f}%p), 2→3일({r1[3] - r1[2]:.2f}%p)과 비슷함. 4일에서 갑자기 달라지기보다 학습 일수에 따라 점진적으로 높아지는 패턴.",
      f"1일 학습자가 {days.loc[1, 'n']:,}명(전체의 {rate(days.loc[1, 'n'], 82467):.2f}%)으로 가장 많음."]))
A("<h3>마지막 학습일을 3/7로 맞춘 비교</h3>")
A(ul(["학습 일수가 많은 사용자는 최근에도 학습했을 가능성이 높아, 마지막 학습일이 같은(3/7) 사용자끼리 다시 비교함."]))
A(tbl(["학습 일수"] + [f"{d}일" for d in range(1, 8)], [["2일 이상 재학습률"] + [pct(rec1_days.loc[d, "k2"], rec1_days.loc[d, "n"]) for d in range(1, 8)],
                                                       ["인원"] + [f"{rec1_days.loc[d, 'n']:,}" for d in range(1, 8)]]))
A(ul(["마지막 학습일을 맞춰도 학습 일수에 따른 차이가 유지됨."]))
A("<h3>학습 일수 × 학습량 교차 분석</h3>")
A(ul([f"학습량 = 기준 주간 session_seen 합(학습 문항 수). 세그먼트 기본 정의(12개 열 기준 중복 제거)의 중앙값 <b>{MED:.0f}문항</b>으로 구분."]))
A(tbl(["집단", "학습 일수", "학습량", "유저 수", "1일 이상 재학습률", "2일 이상 재학습률"],
      [[k, d_, v_, f"{abcd.loc[k, 'n']:,}", pct(abcd.loc[k, 'k1'], abcd.loc[k, 'n']), pct(abcd.loc[k, 'k2'], abcd.loc[k, 'n'])]
       for k, d_, v_ in [("A", "1~3일", f"{MED:.0f}문항 미만"), ("B", "1~3일", f"{MED:.0f}문항 이상"), ("C", "4~7일", f"{MED:.0f}문항 미만"), ("D", "4~7일", f"{MED:.0f}문항 이상")]]))
A(ul([f"같은 학습량 구간 안에서는 학습 일수가 많은 집단의 재학습률이 높음(A {pct(abcd.loc['A', 'k2'], abcd.loc['A', 'n'])} → C {pct(abcd.loc['C', 'k2'], abcd.loc['C', 'n'])}, B {pct(abcd.loc['B', 'k2'], abcd.loc['B', 'n'])} → D {pct(abcd.loc['D', 'k2'], abcd.loc['D', 'n'])}). C 집단은 {abcd.loc['C', 'n']}명으로 작아 해석에 주의.",
      f"A와 B의 차이에는 학습 일수 구성 차이가 섞여 있음. 1일 학습자 비중이 A는 {one_day_share['A']:.1f}%, B는 {one_day_share['B']:.1f}%로, B에 2~3일 학습자가 더 많음. 그래서 학습 일수를 나눠 다시 비교함."]))
A(tbl(["학습 일수", f"학습량 {MED:.0f}문항 미만", f"학습량 {MED:.0f}문항 이상", "차이"],
      [[lab, f"{pct(grid.loc[(dg, False), 'k2'], grid.loc[(dg, False), 'n'])} · n={grid.loc[(dg, False), 'n']:,}",
        f"{pct(grid.loc[(dg, True), 'k2'], grid.loc[(dg, True), 'n'])} · n={grid.loc[(dg, True), 'n']:,}",
        f"+{rate(grid.loc[(dg, True), 'k2'], grid.loc[(dg, True), 'n']) - rate(grid.loc[(dg, False), 'k2'], grid.loc[(dg, False), 'n']):.1f}%p"]
       for dg, lab in [(1, "1일"), (2, "2일"), (3, "3일"), (4, "4일 이상")]]))
A(ul([f"2일 이상 재학습률. 학습 일수가 같은 사용자끼리 비교해도 학습량이 많은 쪽이 높지만, 1~3일 구간의 차이는 +{min(rate(grid.loc[(d, True), 'k2'], grid.loc[(d, True), 'n']) - rate(grid.loc[(d, False), 'k2'], grid.loc[(d, False), 'n']) for d in (1, 2, 3)):.1f}~{max(rate(grid.loc[(d, True), 'k2'], grid.loc[(d, True), 'n']) - rate(grid.loc[(d, False), 'k2'], grid.loc[(d, False), 'n']) for d in (1, 2, 3)):.1f}%p로 A·B 차이({rate(abcd.loc['B', 'k2'], abcd.loc['B', 'n']) - rate(abcd.loc['A', 'k2'], abcd.loc['A', 'n']):.1f}%p)보다 작음.",
      "학습량은 학습 일수를 보완하는 요인이며, 학습 일수의 차이를 대신 설명하지는 않음."]))

A("<h2>🔍 ③ 세그먼트별 코호트</h2>")
A(img("chart_03_segment.png"))
A(tbl(["세그먼트", "기준 주간 행동", "인원", "3/8", "3/9", "3/10", "3/11", "1일 이상", "2일 이상"],
      [[s, de, f"{seg.loc[s, 'n']:,}"] + [f"{rate(seg.loc[s, c], seg.loc[s, 'n']):.1f}" for c in AC] + [pct(seg.loc[s, 'k1'], seg.loc[s, 'n']), f"<b>{pct(seg.loc[s, 'k2'], seg.loc[s, 'n'])}</b>"]
       for s, de in zip(SEG, ["4일 이상, 최근 2일 내 학습", "2~3일, 최근 2일 내 학습", "1일, 최근 2일 내 학습", "3일 이상, 3/5 이전 마지막", "2일 이하, 3/5 이전 마지막, 109문항 이상", "2일 이하, 3/5 이전 마지막, 108문항 이하"])]))
A(ul(["날짜 칸 = 당일 재학습률(%). 꾸준형 55.9%부터 멈춤-저활동형 4.7%까지 반복학습률 차이가 큼.",
      "세그먼트는 기준 주간 행동으로 정의했으므로 이 차이는 분류의 타당성 확인이며, 개입 효과를 뜻하지 않음."]))
A("<h3>습관 형성형의 날짜별 재학습</h3>")
A(tbl(["날짜", "3/8 (금)", "3/9 (토)", "3/10 (일)", "3/11 (월)"],
      [["당일 재학습률"] + [pct(seg.loc["습관 형성형", c], seg.loc["습관 형성형", "n"]) for c in AC], ["누적 재학습률"] + [f"{v:.1f}%" for v in seg_cum["습관 형성형"]]]))
A(ul([f"분모 14,583명. 3/11까지 1일 이상 {pct(seg.loc['습관 형성형', 'k1'], seg.loc['습관 형성형', 'n'])}가 다시 학습했지만 2일 이상은 {pct(seg.loc['습관 형성형', 'k2'], seg.loc['습관 형성형', 'n'])}에 그침. 재학습이 여러 날의 학습으로 충분히 이어지지 않음."]))
A("<h3>마지막 학습일을 맞춘 세그먼트 비교</h3>")
A(tbl(["마지막 학습", "꾸준형", "습관 형성형", "최근 단발형"],
      [[lab] + [f"{pct(seg_rec.loc[(r, s), 'k2'], seg_rec.loc[(r, s), 'n'])} · n={seg_rec.loc[(r, s), 'n']:,}" for s in ["꾸준형", "습관 형성형", "최근 단발형"]]
       for r, lab in [(1, "3/7 (1일 전)"), (2, "3/6 (2일 전)")]]))
A(ul(["2일 이상 재학습률. 마지막 학습일이 같아도 세그먼트 간 차이가 유지됨."]))
A("<h3>2~3일 학습자 안의 차이</h3>")
A(tbl(["구분", "인원", "2일 이상 재학습률"], [["2~3일 학습자 전체", f"{len(two3):,}", pct(two3.ret2.sum(), len(two3))],
                                          ["└ 최근 2일 내 학습 (습관 형성형)", f"{len(T23H):,}", f"<b>{pct(T23H.ret2.sum(), len(T23H))}</b>"],
                                          ["└ 마지막 학습이 3/5 이전 (멈춤 계열)", f"{len(T23P):,}", pct(T23P.ret2.sum(), len(T23P))]]))
A(ul(["NSM 직전 단계(2~3일)라도 최근 학습 여부에 따라 재학습률이 크게 다름."]))

A("<h2>📅 ④ 첫 후속 학습일 코호트</h2>")
A(quote("후속 기간에 처음 다시 학습한 날을 D0로 맞추고, 그 뒤 날짜별로 학습했는지를 비교함. D0 = 100%는 정의상 값. 3/11 이후는 미관측."))
def frrows(F_):
    return [[f"3/{r['date'].day}", f"{r['n']:,}", "100.0%"] + [f"{r['D'][k]:.1f}%" if k in r["D"] else "미관측" for k in (1, 2, 3)] for r in F_]
A("<h3>전체</h3>"); A(tbl(["첫 후속 학습일", "인원", "D0", "D1", "D2", "D3"], frrows(FR_ALL)))
A("<h3>습관 형성형</h3>"); A(tbl(["첫 후속 학습일", "인원", "D0", "D1", "D2", "D3"], frrows(FR_HAB)))
A(ul([f"재학습 뒤 2일(D1·D2) 안에 추가로 학습한 비율: 전체 {pct(D12_ALL[1], D12_ALL[0])} ({D12_ALL[0]:,}명 중 {D12_ALL[1]:,}명), 습관 형성형 {pct(D12_HAB[1], D12_HAB[0])} ({D12_HAB[0]:,}명 중 {D12_HAB[1]:,}명). D1·D2가 모두 관측되는 3/8·3/9 재학습자만 분모에 포함.",
      "<b>행끼리 비교할 때 주의</b>: D1이 36.9%(3/8) → 33.0%(3/9) → 27.1%(3/10)로 낮아지지만, D1에 해당하는 요일이 각각 토·일·월로 다르고, 늦게 돌아온 사용자일수록 기준 주간 이후 더 오래 쉰 사용자임. 이 차이를 '늦게 돌아온 사용자는 덜 이어진다'는 결론으로 쓰지 않음.",
      "첫 후속 학습자에는 전날(3/7)에도 학습한 사람이 포함됨. 아래에서 이어서 학습한 사람과 쉬었다 재개한 사람을 나눠 봄."]))
A("<h3>이어서 학습 vs 하루 쉬고 재개 (3/8 첫 후속 학습자)</h3>")
rows = []
for sg_ in ["꾸준형", "습관 형성형", "최근 단발형"]:
    (n0, k0), (n1, k1_) = RESUME[(sg_, "cont")], RESUME[(sg_, "rest")]
    rows.append([sg_, f"{pct(k0, n0)} · n={n0:,}", f"{pct(k1_, n1)} · n={n1:,}", f"<b>{rate(k0, n0) - rate(k1_, n1):.1f}%p</b>"])
A(tbl(["세그먼트", "3/7에도 학습 (이어서)", "3/6이 마지막 (하루 쉬고 재개)", "차이"], rows))
A(ul([f"결과 = 3/9·3/10 중 추가 학습 비율. 습관 형성형 차이 {pa * 100 - pb * 100:.1f}%p (95% CI ±{RES_CI:.1f}%p). 세 세그먼트 모두 하루 쉬고 재개한 쪽이 덜 이어짐.",
      "다음 두 날이 모두 주말(토·일)인 같은 날짜끼리의 관측 비교이며, 재개 자체의 인과 효과는 아님."]))

A("<h2>📅 ⑤ 관측 주 첫 학습일 코호트</h2>")
A(img("chart_04_first_active.png"))
d1 = [r["D"][1] for r in TRI]
A(ul([f"첫 학습일 다음날(D1) 다시 학습한 비율은 3/2~3/7 코호트에서 {min(d1[1:]):.1f}~{max(d1[1:]):.1f}%. 3/1 코호트(31.0%)에는 데이터 시작(2/28 저녁) 전부터 학습하던 사용자가 많이 섞여 있음.",
      f"가장 큰 감소는 첫 학습일 직후. 3/2 코호트는 D1 {d1[1]:.1f}% 이후 D9 {TRI[1]['D'][9]:.1f}%까지 완만하게 줄어듦.",
      f"관측 주 첫 학습일은 가입일이 아님. 퍼널 분석과 같은 방식(timestamp − delta)으로 보면 신규 추정 사용자는 {NEW_N:,}명({rate(NEW_N, 82467):.1f}%)이며, 신규 추정 사용자만 본 D1은 " +
      ", ".join(f"3/{r['first'].day} {r['D1_new']:.1f}%" for r in TRI) + "로 전체와 비슷한 수준."]))

A("<h2>🎯 시사점 및 실험 제안</h2>")
A("<h3>학습 일수 코호트별 학습 지속 지원 방향</h3>")
A(tbl(["대상 집단", "관측 결과", "개선 방향"],
      [["1일 학습군", f"후속 재학습률 {r1[1]:.2f}%", "다음 학습일 설정 및 학습 재참여 안내"],
       ["2~3일 학습군", f"후속 재학습률 {r1[2]:.2f}~{r1[3]:.2f}%", "주간 4일 학습 목표 제시"],
       ["4~6일 학습군", f"후속 재학습률 {r1[4]:.2f}~{r1[6]:.2f}%", "주간 학습 목표 유지 피드백"],
       ["7일 학습군", f"후속 재학습률 {r1[7]:.2f}%", "학습 성취 피드백 및 장기 목표 제공"]]))
A(ul([f"규모가 큰 1~3일 학습군({miss['n']:,}명, {rate(miss['n'], 82467):.1f}%)의 재학습 참여를 지원하는 것이 중요한 과제. 그중 2~3일 학습군({len(two3):,}명, {rate(len(two3), 82467):.1f}%)은 이미 여러 날 학습한 경험이 있지만 NSM 기준에 도달하지 못한 집단."]))
A("<h3>코호트 결과에서 나온 시사점</h3>")
A(tbl(["관찰 결과", "시사점"],
      [["학습 일수가 많을수록 재학습률이 점진적으로 높음", "NSM(4일)은 목표선으로 두고, 바로 아래 단계(2~3일) 사용자를 우선 대상으로 봄"],
       ["2~3일 학습자 중 최근 학습한 습관 형성형의 재학습률이 멈춤 계열보다 높음", "우선 대상은 2~3일 학습자 중 습관 형성형"],
       ["습관 형성형의 재학습이 여러 날로 이어지지 않음 (1일 이상 52.2% vs 2일 이상 24.4%)", "다시 학습한 뒤 다음 학습으로 연결하는 안내가 필요"],
       ["하루 쉬고 재개한 사용자가 이어서 학습한 사용자보다 덜 이어짐", "학습 직후 다음 학습일을 정하게 하는 시점이 유효"]]))
A(tbl(["항목", "내용"],
      [["실험 대상", "습관 형성형 (기준 주간 2~3일 학습 + 최근 2일 내 학습)"], ["실험군", "학습 직후 다음 학습일 안내 + 주간 4일 학습 목표 표시"],
       ["대조군", "기존 서비스 유지"], ["배정 방식", "사용자 단위 무작위 배정"],
       ["평가 지표", "학습 뒤 2일(D1·D2) 안 추가 학습 비율, 다음 7일 NSM 달성률, 후속 1일·2일 이상 재학습률"]]))
A(ul(["안내의 실제 효과는 실험으로 확인해야 함. 현재 데이터는 추적 4일이라 다음 7일 NSM 달성률의 기준값은 계산할 수 없음."]))

A("<h2>📌 코호트 분석 요약 및 한계</h2>")
A("<p><b>요약</b></p>")
A(ul([f"NSM 달성군의 후속 1일 이상 재학습률은 {pct(hit['k1'], hit['n'])}로 미달성군({pct(miss['k1'], miss['n'])})보다 높음.",
      f"학습 일수가 1일에서 7일로 늘수록 재학습률이 {r1[1]:.1f}%에서 {r1[7]:.1f}%로 점진적으로 높아짐. 마지막 학습일을 맞춰도 유지됨.",
      "6개 세그먼트의 2일 이상 재학습률은 55.9%(꾸준형)~4.7%(멈춤-저활동형). 마지막 학습일을 맞춰도 차이가 유지됨.",
      "재학습 뒤 2일 안에 추가 학습한 비율은 절반 수준이며, 하루 쉬고 재개한 사용자일수록 덜 이어짐.",
      "관측 주에 처음 학습한 다음날 다시 학습한 사용자는 4명 중 1명 수준(신규 추정 사용자도 비슷)."]))
A("<p><b>한계</b></p>")
A(ul(["관찰 데이터이므로 학습 일수·세그먼트가 재학습을 직접 높인다고 단정할 수 없음.",
      "후속 관측이 4일이라 D7·D30 리텐션, 다음 주 NSM 달성, 장기 이탈은 판단할 수 없음. 추적 4일(금·토·일·월)에 주말이 포함됨.",
      "기준 주간에 학습 기록이 있는 사용자만 대상. 관측 주 첫 학습일은 가입일이 아니며, 사용자의 약 75%는 3/1 이전 학습 흔적이 있는 기존 사용자.",
      "기록 없음은 이 데이터에 학습 기록이 없다는 뜻이며 앱 미사용이나 영구 이탈을 뜻하지 않음.",
      "학습량(session_seen 합)은 노출·응답 시도 수이며 학습 시간이나 난이도를 반영하지 않음."]))

A('<h2 style="break-before: page">📎 부록. 대시보드용 추가 집계</h2>')
A(quote("대시보드에 쓰는 수치 중 본문에 없는 것을 <b>본문과 같은 데이터·기준</b>(기준 주간 3/1~3/7 사용자 82,467명, 세그먼트 기본 규칙, 후속 관측 3/8~3/11)으로 계산해 정리함. 대시보드의 모든 수치는 본문 또는 이 부록에서 나옴."))
A("<h3>A. 이탈 위험 정의</h3>")
A(ul([f"<b>이탈 위험</b> = 후속 4일(3/8~3/11) 동안 학습 기록이 없는 사용자. <b>{RISK:,}명({pct(RISK, 82467)})</b>. 100%에서 1일 이상 재학습률({pct(29240, 82467)})을 뺀 값과 같음.",
      "'이탈'이 아니라 '이탈 위험'으로 부름. 주말이 포함된 4일 동안 이 데이터에 기록이 없다는 뜻이며, 영구 이탈이나 앱 미사용을 뜻하지 않음."]))
A("<h3>B. 세그먼트별 규모·학습량 비중·이탈 위험</h3>")
A(tbl(["세그먼트", "인원 (비중)", "학습량 비중", "1인당 학습량", "이탈 위험률", "다음날 재학습률", "2일 이상 재학습률 (95% CI)"],
      [[s, f"{segx.loc[s, 'n']:,} ({segx.loc[s, 'share']:.1f}%)", f"{segx.loc[s, 'vol']:.1f}%", f"{segx.loc[s, 'per']:.0f}문항",
        pct(segx.loc[s, 'risk'], segx.loc[s, 'n']), "해당 없음" if s == "최근 단발형" else pct(NEXT_SEG.loc[s, 'sum'], NEXT_SEG.loc[s, 'size']),
        f"{pct(segx.loc[s, 'k2'], segx.loc[s, 'n'])} ({segx.loc[s, 'ci'][0]:.1f}~{segx.loc[s, 'ci'][1]:.1f})"] for s in SEG] +
      [["전체", "82,467 (100%)", "100%", f"{WS / 82467:.0f}문항", pct(RISK, 82467), pct(*NEXT_ALL), pct(13466, 82467)]]))
_hi = segx.risk.idxmax()
A(ul([f"꾸준형은 사용자의 {segx.loc['꾸준형', 'share']:.1f}%이지만 기준 주간 학습량의 {segx.loc['꾸준형', 'vol']:.1f}%를 차지함. 이 집단의 이탈 위험률은 {pct(segx.loc['꾸준형', 'risk'], segx.loc['꾸준형', 'n'])}로 가장 낮음.",
      f"이탈 위험 인원은 {_hi}이 {segx.loc[_hi, 'risk']:,}명으로 가장 많음(이탈 위험자 전체의 {rate(segx.loc[_hi, 'risk'], RISK):.1f}%). 다만 학습량 비중은 {segx.loc[_hi, 'vol']:.1f}%.",
      "학습량 = 기준 주간 session_seen 합. 다음날 재학습률 정의는 D 참고(최근 단발형은 학습일이 1일이라 정의상 계산 대상이 아님). 95% CI는 윌슨 구간."]))
A("<h3>C. 마지막 학습 후 경과일별 재학습 (1~3일 학습자)</h3>")
A(img("chart_05_recency.png"))
def _cell(ad_, k):
    if (ad_, k) not in rec_curve.index: return "–"
    r_ = rec_curve.loc[(ad_, k)]
    return f"<b>{rate(r_.k1, r_.n):.1f}</b> · {rate(r_.k2, r_.n):.1f}<br>n={int(r_.n):,}"
A(tbl(["일수"] + [f"{k}일 전<br>(3/{8 - k})" for k in range(1, 8)], [[f"{ad_}일"] + [_cell(ad_, k) for k in range(1, 8)] for ad_ in (1, 2, 3)]))
_c1 = rec_curve.loc[1]
A(ul(["칸 = 후속 4일 <b>1일 이상 재학습률(%)</b> · 2일 이상 재학습률(%). 일수 = 기준 주간 학습 일수. 경과일 = 3/8 기준 마지막 학습일로부터 지난 날 수(1일 전 = 3/7에 마지막 학습).",
      f"같은 학습 일수 안에서 쉰 기간이 길수록 재학습률이 낮아짐. 1일 학습자는 {pct(_c1.loc[1, 'k1'], _c1.loc[1, 'n'])}(1일 전) → {pct(_c1.loc[2, 'k1'], _c1.loc[2, 'n'])}(2일 전) → {pct(_c1.loc[3, 'k1'], _c1.loc[3, 'n'])}(3일 전) → {pct(_c1.loc[7, 'k1'], _c1.loc[7, 'n'])}(7일 전)으로, 감소가 처음 2~3일에 큼.",
      "대시보드에서는 '공백이 길어지기 전에 개입해야 한다'는 개입 시점의 근거로 씀.",
      "관측 비교이며 인과 효과가 아님. 경과일마다 마지막 학습 요일이 다르고, 3일 학습자는 경과일 5일까지만 존재함."]))
A("<h3>D. NSM 입력 지표의 현재값</h3>")
A(tbl(["지표", "정의", "값"],
      [["다음날 재학습률", "활동일 d(3/1~3/6) 중 다음날 d+1에도 학습한 비율. 사용자-활동일 단위", f"<b>{pct(*NEXT_ALL)}</b> ({NEXT_ALL[0]:,} / {NEXT_ALL[1]:,})"],
       ["첫 학습일 학습량", "관측 주 첫 학습일 session_seen 합의 중앙값", f"<b>{u.first_vol.median():.0f}문항</b>"],
       ["활동일당 세션 수", "사용자별 세션 수(사용자·timestamp 단위) ÷ 학습 일수의 중앙값", f"<b>{u.spd.median():.1f}</b>"]]))
A(ul(["다음날 재학습률은 ⑤의 D1(첫 학습일 다음날, 사용자 단위)과도, 퍼널 분석의 '다음날 재학습'(3/1 시작자의 첫 학습일 다음날)과도 정의가 다름. 대시보드에서는 이름을 구분해 표기함.",
      "첫 학습일 학습량은 퍼널 분석의 '첫날 학습량'과 같은 개념이지만, 퍼널은 3/1 시작자를 20/60/120문항 구간으로 나눠 봄."]))
A("<h3>E. 세그먼트별 액션과 측정 지표</h3>")
A(quote("모든 세그먼트에 <b>공통 지표(2일 이상 재학습률)</b>를 두고, 세그먼트별 보조 지표는 이 데이터로 잴 수 있는 것만 둠. 순위와 액션안은 세그먼트 기본 문서 기준이며, 1순위인 습관 형성형은 본문의 실험 제안과 같은 내용으로 맞춤."))
def _seg_rate(s, k): return pct(segx.loc[s, k], segx.loc[s, "n"])
A(tbl(["순위", "세그먼트", "인원", "액션안", "공통: 2일 이상 재학습률", "보조 지표 (현재값)"],
      [["1", "습관 형성형", f"{segx.loc['습관 형성형', 'n']:,}", "학습 직후 다음 학습일 안내 + 주간 4일 학습 목표 표시", _seg_rate("습관 형성형", "k2"),
        f"재학습 뒤 D1·D2 추가 학습 {pct(D12_HAB[1], D12_HAB[0])} ({D12_HAB[0]:,}명 중 {D12_HAB[1]:,}명, ④)"],
       ["2", "멈춤-꾸준형", f"{segx.loc['멈춤-꾸준형', 'n']:,}", "\"잊기 전에 복습\" 알림", _seg_rate("멈춤-꾸준형", "k2"), f"4일 내 복귀율 {_seg_rate('멈춤-꾸준형', 'k1')}"],
       ["2", "멈춤-몰입형", f"{segx.loc['멈춤-몰입형', 'n']:,}", "\"매일 소량\" 목표 제안", _seg_rate("멈춤-몰입형", "k2"), f"4일 내 복귀율 {_seg_rate('멈춤-몰입형', 'k1')}"],
       ["3", "꾸준형", f"{segx.loc['꾸준형', 'n']:,}", "평소 시간대 알림, 연속 학습 보상", _seg_rate("꾸준형", "k2"), "없음. NSM 유지율은 다음 7일 관측이 필요해 측정 불가"],
       ["4", "최근 단발형", f"{segx.loc['최근 단발형', 'n']:,}", "첫 학습 직후 성취 피드백, 다음 날 안내", _seg_rate("최근 단발형", "k2"),
        f"다음날 복귀율 {pct(SINGLE_NEXT[1], SINGLE_NEXT[0])} (3/7 학습자 {SINGLE_NEXT[0]:,}명 중 3/8 학습 {SINGLE_NEXT[1]:,}명)"],
       ["5", "멈춤-저활동형", f"{segx.loc['멈춤-저활동형', 'n']:,}", "저비용 일괄 리마인드", _seg_rate("멈춤-저활동형", "k2"),
        f"4일 내 복귀율 {_seg_rate('멈춤-저활동형', 'k1')}. 알림 반응률은 알림 기록이 없어 측정 불가"]]))
A(ul(["4일 내 복귀율 = 후속 4일 중 1일 이상 학습(= 1 − 이탈 위험률).",
      "현재값은 개입 전 관측 기준값이며 액션의 효과가 아님. 효과는 실험으로 확인해야 함."]))

src = open(os.path.abspath(__file__), encoding="utf-8").read()
cut = src.index("# 차트 (퍼널 분석 문서와 같은 스타일)"); analysis_code = src[:cut].rstrip()
A('<h2 class="tg">💻 분석 코드</h2>')
A(ul([f"파일: {code('build_cohort_report.py')} (pandas + numpy, 차트 matplotlib)",
      f"실행 방법: {code('pip install pandas numpy matplotlib playwright pypdf')} → {code('python build_cohort_report.py <원본 CSV> <출력 폴더>')}",
      "데이터 경로: 실행할 때 첫 번째 인자로 원본 CSV(또는 .csv.gz) 경로를 넘김",
      f"결과 파일 ({code('<출력 폴더>/')})" + ul([f"{code('charts/chart_01~05_*.png')}: NSM 달성 여부별 날짜별 재학습, 학습 일수별 재학습, 세그먼트 분포, 첫 학습일 코호트, 경과일별 재학습(부록)",
                                                f"{code('코호트분석 통합본.pdf')}: 이 문서", f"{code('dashboard_data_final/')}: 대시보드용 CSV (본문·부록 수치와 같은 값)"]),
      "아래는 분석 부분 코드(차트와 문서 출력 부분 제외)"]))
A('<details open><summary>코드보기</summary><pre class="code">' + E(analysis_code) + "</pre></details>")

CSS = """
@page { size: 595.92pt 842.88pt; margin: 56pt 0 60pt 0; }
html,body { margin:0; padding:0; background:#fff; }
body { font-family: Inter, "Noto Sans CJK KR", sans-serif; color:#37352f; font-size:8.3pt; line-height:1.55; }
.wrap { margin: 0 72pt; }
h1 { font-size:20pt; font-weight:700; margin: 8pt 0 12pt 0; letter-spacing:-0.2pt; }
h2 { font-size:12.5pt; font-weight:700; margin: 18pt 0 6pt 0; break-after: avoid; }
h3 { font-size:9.6pt; font-weight:700; margin: 12pt 0 5pt 0; break-after: avoid; }
h2.tg::before { content:"▼ "; font-size:10pt; }
p { margin: 8pt 0 3pt 0; }
blockquote { margin: 6pt 0 8pt 0; padding: 1pt 0 1pt 11pt; border-left: 2.4pt solid #37352f; }
ul, ol { margin: 3pt 0 6pt 0; padding-left: 17pt; } li { margin: 2.5pt 0; } ul ul { list-style: circle; }
table { border-collapse: collapse; width:auto; max-width:100%; margin: 5pt 0 8pt 0; font-size:7.3pt; line-height:1.4; }
th, td { border: 0.6pt solid #e3e2e0; padding: 3pt 6pt; text-align:left; vertical-align: top; }
th { background:#f7f6f3; font-weight:400; } tr { break-inside: avoid; }
img { width: 100%; max-width: 420pt; display:block; margin: 6pt 0; break-inside: avoid; }
.callout { display:flex; gap:8pt; border:0.6pt solid #e3e2e0; border-radius:4pt; padding:9pt 11pt; margin: 6pt 0 8pt 0; break-inside: avoid; }
code { font-family:"DejaVu Sans Mono","Noto Sans Mono CJK KR",monospace; font-size:6.8pt; color:#eb5757; background:#f1f1ef; padding:0.5pt 2pt; border-radius:2pt; }
details summary { list-style:none; margin: 4pt 0; }
pre.code { background:#f5f2f0; padding:10pt 9pt; font-family:"DejaVu Sans Mono","Noto Sans Mono CJK KR",monospace; font-size:6.4pt; line-height:9.6pt;
           white-space:pre-wrap; word-break:break-all; color:#000; box-decoration-break: clone; -webkit-box-decoration-break: clone; }
"""
HTML = os.path.join(OUTDIR, "_report.html")
open(HTML, "w", encoding="utf-8").write(f'<!doctype html><html><head><meta charset="utf-8"><style>{CSS}</style></head><body><div class="wrap">{"".join(P)}</div></body></html>')
FOOT = f"""<div style="width:100%;font-family:Inter,'Noto Sans CJK KR',sans-serif;font-size:7.4pt;color:#7f7f7f;padding:0 26.9pt 0 27pt;display:flex;justify-content:space-between;margin-bottom:11pt"><span>{TITLE}</span><span class="pageNumber"></span></div>"""
from playwright.sync_api import sync_playwright
with sync_playwright() as pw:
    b = pw.chromium.launch(); pg = b.new_page(); pg.goto("file://" + HTML); pg.wait_for_timeout(500)
    pg.pdf(path=PDF, width="8.2767in", height="11.7067in", prefer_css_page_size=True, print_background=True,
           display_header_footer=True, header_template="<span></span>", footer_template=FOOT)
    b.close()
os.remove(HTML)
from pypdf import PdfReader
text = "\n".join(p_.extract_text() for p_ in PdfReader(PDF).pages)
for req in ["82,467", "9,834", "77.83%", "29.72%", "21.83%", "96.63%", "55.9%", "4.7%", "49.7%", "42.0%", "47.6%", "14,846", "53,227", "64.5%", "38.5%", "35.8%", "21.3%"]:
    assert req in text, req
print(json.dumps({"pdf": PDF, "pages": len(PdfReader(PDF).pages)}, ensure_ascii=False))

# 대시보드 데이터 (본문·부록과 같은 값) ----------------------------------------------------
DD = os.path.join(OUTDIR, "dashboard_data_final"); os.makedirs(DD, exist_ok=True)
def save(df_, name): df_.to_csv(os.path.join(DD, name), index=False, encoding="utf-8-sig")
save(pd.DataFrame([
    ("주간 활성 학습자 수", "3/1~3/7 학습일 1일 이상 사용자", 82467, 82467, 100.0, "본문 설계"),
    ("NSM 달성자 수", "3/1~3/7 학습일 4일 이상 사용자", hit["n"], 82467, rate(hit["n"], 82467), "본문 ①"),
    ("이탈 위험자 수", "후속 3/8~3/11 학습 기록 없음", RISK, 82467, rate(RISK, 82467), "부록 A"),
    ("후속 1일 이상 재학습률", "3/8~3/11 중 1일 이상 학습", 29240, 82467, rate(29240, 82467), "본문 ①"),
    ("후속 2일 이상 재학습률(반복학습)", "3/8~3/11 중 서로 다른 2일 이상 학습", 13466, 82467, rate(13466, 82467), "본문 ①"),
    ("다음날 재학습률", "활동일 d(3/1~3/6) 중 d+1에도 학습, 사용자-활동일 단위", NEXT_ALL[0], NEXT_ALL[1], rate(*NEXT_ALL), "부록 D"),
    ("첫 학습일 학습량(중앙값, 문항)", "관측 주 첫 학습일 session_seen 합의 중앙값", None, None, float(u.first_vol.median()), "부록 D"),
    ("활동일당 세션 수(중앙값)", "사용자별 세션 수 ÷ 학습 일수의 중앙값", None, None, float(u.spd.median()), "부록 D")],
    columns=["metric", "definition", "numerator", "denominator", "value", "source"]), "01_kpi_summary.csv")
save(pd.DataFrame({"active_days": days.index, "nsm_group": np.where(days.index >= 4, "달성", "미달성"), "users": days.n.values,
                   "ret1_users": days.k1.values, "ret1_rate": (days.k1 / days.n * 100).values, "ret2_users": days.k2.values, "ret2_rate": (days.k2 / days.n * 100).values,
                   "last3_7_users": rec1_days.n.reindex(days.index).values, "last3_7_ret2_users": rec1_days.k2.reindex(days.index).values,
                   "last3_7_ret2_rate": (rec1_days.k2 / rec1_days.n * 100).reindex(days.index).values, "source": "본문 ②"}), "02_cohort_active_days.csv")
save(pd.DataFrame([[nm, str(d.date()), g["n"], g["daily"][i], rate(g["daily"][i], g["n"]), g["cum"][i], rate(g["cum"][i], g["n"]), "본문 ①"]
                   for nm, g in [("NSM 달성", hit), ("NSM 미달성", miss)] for i, d in enumerate(DATES)],
                  columns=["group", "date", "users", "active_users", "daily_rate", "cum_users", "cum_rate", "source"]), "03_cohort_nsm_daily.csv")
save(pd.DataFrame({"segment": SEG, "priority": [3, 1, 4, 2, 2, 5], "users": segx.n.values, "user_share": segx.share.values,
                   "words_seen": segx.ws.values, "volume_share": segx.vol.values, "words_per_user": segx.per.values,
                   "risk_users": segx.risk.values, "risk_rate": (segx.risk / segx.n * 100).values,
                   "ret1_users": segx.k1.values, "ret1_rate": (segx.k1 / segx.n * 100).values,
                   "ret2_users": segx.k2.values, "ret2_rate": (segx.k2 / segx.n * 100).values,
                   "ret2_ci_low": [c[0] for c in segx.ci], "ret2_ci_high": [c[1] for c in segx.ci],
                   "next_day_rate": np.where(np.array(SEG) == "최근 단발형", np.nan, (NEXT_SEG["sum"] / NEXT_SEG["size"] * 100).values), "source": "본문 ③ · 부록 B"}), "04_segment_summary.csv")
save(pd.DataFrame([[s, str(d.date()), int(seg.loc[s, "n"]), int(seg.loc[s, c]), rate(seg.loc[s, c], seg.loc[s, "n"]),
                    seg_cum[s][i], "본문 ③"] for s in SEG for i, (d, c) in enumerate(zip(DATES, AC))],
                  columns=["segment", "date", "users", "active_users", "daily_rate", "cum_rate", "source"]), "05_segment_daily.csv")
save(pd.DataFrame([[str(r["first"].date()), r["n"], k, r["D"].get(k), k in r["D"], "본문 ⑤"] for r in TRI for k in range(1, 11)],
                  columns=["first_active", "users", "day_k", "rate", "observed", "source"]), "06_first_active_cohort.csv")
rcv = rec_curve.reset_index()
save(rcv.assign(ret1_rate=rcv.k1 / rcv.n * 100, ret2_rate=rcv.k2 / rcv.n * 100, last_active=[str((T("2013-03-08") - pd.Timedelta(days=int(k))).date()) for k in rcv.recency],
                source="부록 C").rename(columns={"n": "users", "k1": "ret1_users", "k2": "ret2_users", "recency": "days_since_last"}), "07_recency_curve.csv")
save(pd.DataFrame([[sg_, "이어서 학습(3/7 학습)" if lab == "cont" else "하루 쉬고 재개(3/6 마지막)", n_, k_, rate(k_, n_), "본문 ④"]
                   for (sg_, lab), (n_, k_) in RESUME.items()], columns=["segment", "group", "users", "d1d2_users", "d1d2_rate", "source"]), "08_resume_compare.csv")
rows = []
for scope, F_, D12 in [("전체", FR_ALL, D12_ALL), ("습관 형성형", FR_HAB, D12_HAB)]:
    for r in F_:
        for k in range(0, 4): rows.append([scope, str(r["date"].date()), r["n"], k, 100.0 if k == 0 else r["D"].get(k), k == 0 or k in r["D"], "본문 ④"])
save(pd.DataFrame(rows, columns=["scope", "first_return_date", "users", "day_k", "rate", "observed", "source"]), "09_first_return_cohort.csv")
save(pd.DataFrame([[s, "4일 내 복귀율" if s.startswith("멈춤") else m, v_, d_] for s, m, v_, d_ in [
        ("습관 형성형", "재학습 뒤 D1·D2 추가 학습률", rate(D12_HAB[1], D12_HAB[0]), f"3/8·3/9 재학습자 {D12_HAB[0]:,}명 중 {D12_HAB[1]:,}명"),
        ("멈춤-꾸준형", "", rate(segx.loc["멈춤-꾸준형", "k1"], segx.loc["멈춤-꾸준형", "n"]), "후속 4일 중 1일 이상 학습"),
        ("멈춤-몰입형", "", rate(segx.loc["멈춤-몰입형", "k1"], segx.loc["멈춤-몰입형", "n"]), "후속 4일 중 1일 이상 학습"),
        ("꾸준형", "없음(NSM 유지율 측정 불가)", None, "다음 7일 관측 필요"),
        ("최근 단발형", "다음날 복귀율", rate(SINGLE_NEXT[1], SINGLE_NEXT[0]), f"3/7 학습자 {SINGLE_NEXT[0]:,}명 중 3/8 학습 {SINGLE_NEXT[1]:,}명"),
        ("멈춤-저활동형", "", rate(segx.loc["멈춤-저활동형", "k1"], segx.loc["멈춤-저활동형", "n"]), "후속 4일 중 1일 이상 학습 · 알림 반응률 측정 불가")]],
    columns=["segment", "sub_metric", "sub_value", "sub_definition"]).merge(pd.DataFrame({
        "segment": SEG, "priority": [3, 1, 4, 2, 2, 5], "users": segx.n.values,
        "action": ["평소 시간대 알림, 연속 학습 보상", "학습 직후 다음 학습일 안내 + 주간 4일 학습 목표 표시", "첫 학습 직후 성취 피드백, 다음 날 안내",
                   "\"잊기 전에 복습\" 알림", "\"매일 소량\" 목표 제안", "저비용 일괄 리마인드"],
        "common_metric_ret2_rate": (segx.k2 / segx.n * 100).values}), on="segment").sort_values(["priority", "segment"], kind="stable")
     [["priority", "segment", "users", "action", "common_metric_ret2_rate", "sub_metric", "sub_value", "sub_definition"]].assign(source="부록 E"), "10_segment_actions.csv")
gg = grid.reset_index()
save(gg.assign(active_days_group=gg.dg.map({1: "1일", 2: "2일", 3: "3일", 4: "4일 이상"}), volume_group=np.where(gg.hi, f"{MED:.0f}문항 이상", f"{MED:.0f}문항 미만"),
               ret2_rate=gg.k2 / gg.n * 100, source="본문 ②")[["active_days_group", "volume_group", "n", "k2", "ret2_rate", "source"]]
     .rename(columns={"n": "users", "k2": "ret2_users"}), "11_days_volume_grid.csv")
uu = u[["segment", "active_days", "recency", "R", "F", "M", "first_active", "last_active", "words_seen", "first_vol", "sessions", "new",
        "a8", "a9", "a10", "a11", "fdays", "ret1", "ret2", "risk"]].copy()
uu["first_active"] = uu.first_active.dt.date; uu["last_active"] = uu.last_active.dt.date; uu["new"] = uu.new.astype(int)
save(uu.reset_index().rename(columns={"index": "user_id", "new": "new_estimated"}), "12_user_level.csv")
print(json.dumps({"dashboard_data": sorted(os.listdir(DD))}, ensure_ascii=False))
