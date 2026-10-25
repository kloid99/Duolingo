"""듀오링고 코호트 분석 최종 통합본 (노션 기준 + 세그먼트 분석 최신 코드 기준).

기준: 노션 3팀 프로젝트(문제정의·NSM·지표 정의서·가설)와 '세그먼트 분석 최신' 코드.
원본 learning_traces에 세그먼트 코드의 전처리·세그먼트 규칙을 그대로 적용해 모든 수치를 다시 계산한다.
통합 대상: 코호트분석.pdf, 코호트분석2.pdf. 두 파일의 공통 수치는 assert로 대조한다.

실행 예: python build_cohort_final.py <원본 csv 또는 csv.gz> <출력 pdf>
환경변수 KR_FONT, KR_FONT_BOLD로 한글 TTF 지정(기본: 맑은 고딕).
"""
import sys, os, re, json
from math import sqrt
import numpy as np, pandas as pd
from scipy.stats import chi2_contingency, kruskal
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color, white
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph
from pypdf import PdfReader

SRC, OUT = sys.argv[1], sys.argv[2]
OUTDIR = os.path.dirname(os.path.abspath(OUT))

# =============================================================== 1. 세그먼트 분석 최신 코드 재현
df = pd.read_csv(SRC, dtype={"user_id": "category", "learning_language": "category", "ui_language": "category",
                             "lexeme_id": "category", "lexeme_string": "category"})
N_RAW = len(df); df = df.drop_duplicates(); N_DUP = N_RAW - len(df)
df = df[["user_id", "timestamp", "learning_language", "lexeme_id", "session_seen", "session_correct"]]
df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
df = df[(df["dt"] >= "2013-03-01") & (df["dt"] < "2013-03-12")].copy()
df["date"] = df["dt"].dt.normalize()
N_USERS_311 = df["user_id"].nunique()
ud = df.groupby(["user_id", "date"], observed=True).agg(seen=("session_seen", "sum"), correct=("session_correct", "sum"),
                                                         sessions=("timestamp", "nunique")).reset_index()
ud["user_id"] = ud["user_id"].astype(str)
del df
T = pd.Timestamp
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
for d in DATES:
    u[f"a{d.day}"] = [int((i, d) in act) for i in u.index]
u["fdays"] = u[[f"a{d.day}" for d in DATES]].sum(axis=1)
u["ret1"] = (u.fdays >= 1).astype(int); u["ret2"] = (u.fdays >= 2).astype(int)
u["acc"] = u.words_correct / u.words_seen
u["spd"] = u.sessions / u.active_days

# 세그먼트 코드·두 보고서와의 대조
assert N_DUP == 81 and N_USERS_311 == 109504 and len(u) == 82467
assert (u.active_days >= 4).sum() == 9834 and u.ret1.sum() == 29240 and u.ret2.sum() == 13466
assert [int(x) for x in M_EDGES] == [1, 24, 53, 108, 239, 11501]
SEG_N = u.segment.value_counts().reindex(SEG)
assert SEG_N.tolist() == [8882, 14583, 15402, 3627, 9303, 30670]

def rate(k, n): return k / n * 100
def pct(k, n, d=1): return f"{rate(k, n):.{d}f}%"
def wilson(k, n, z=1.96):
    p = k / n; den = 1 + z * z / n; c0 = (p + z * z / (2 * n)) / den
    h = z * sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (c0 - h) * 100, (c0 + h) * 100

# ---- 학습 일수 / NSM (코호트분석2)
days = u.groupby("active_days").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
TEAM_DAYS = {1: (47087, 10278, 3214), 2: (17134, 6675, 2711), 3: (8412, 4633, 2276), 4: (4748, 3310, 1931),
             5: (2723, 2189, 1521), 6: (1532, 1352, 1096), 7: (831, 803, 717)}
for d, v in TEAM_DAYS.items(): assert tuple(days.loc[d]) == v
NSMG = {}
for key, sub in [("hit", u[u.active_days >= 4]), ("miss", u[u.active_days < 4])]:
    NSMG[key] = dict(n=len(sub), k1=int(sub.ret1.sum()), k2=int(sub.ret2.sum()),
                     daily=[int(sub[f"a{d.day}"].sum()) for d in DATES],
                     cum=[int((sub[[f"a{x.day}" for x in DATES if x <= d]].sum(axis=1) > 0).sum()) for d in DATES])
assert NSMG["hit"]["daily"] == [4869, 4067, 3887, 4286] and NSMG["hit"]["cum"] == [4869, 6286, 7013, 7654]
assert NSMG["miss"]["daily"] == [9977, 7649, 7365, 8139] and NSMG["miss"]["cum"] == [9977, 14801, 18301, 21586]
rec1_days = u[u.recency == 1].groupby("active_days").agg(n=("F", "size"), k2=("ret2", "sum"))

# ---- 세그먼트 코호트 (코호트분석)
seg = u.groupby("segment").agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"),
                               **{f"d{d.day}": (f"a{d.day}", "sum") for d in DATES}).reindex(SEG)
assert seg.k2.tolist() == [4963, 3562, 1862, 808, 841, 1430]
CHI2 = chi2_contingency(pd.crosstab(u.segment, u.ret2))
seg_rec = u[u.recency.isin([1, 2])].groupby(["recency", "segment"]).agg(n=("F", "size"), k2=("ret2", "sum"))

# ---- 관측 주 첫 학습일 코호트 (세그먼트 코드의 first_active, '코호트용')
allact = set(zip(ud.user_id, ud.date))
TRI = []
for f in pd.date_range("2013-03-01", "2013-03-07"):
    ids = u.index[u.first_active == f]; row = {"first": f, "n": len(ids), "D": {}}
    for k in range(1, 11):
        d = f + pd.Timedelta(days=k)
        if d > T("2013-03-11"): break
        row["D"][k] = sum((i, d) in allact for i in ids)
    TRI.append(row)

# ---- 이탈 위험: 마지막 학습 후 경과일 (노션 가설 후보 5, 분석 질문 3)
rec_curve = u[u.active_days <= 2].groupby(["active_days", "recency"]).agg(n=("F", "size"), k1=("ret1", "sum"), k2=("ret2", "sum"))
# 쉬었다 돌아온 사용자 vs 이어서 학습한 사용자 (코호트분석의 A0/A1, 원본으로 재계산)
RESUME = {}
for sg in ["꾸준형", "습관 형성형", "최근 단발형"]:
    s = u[(u.segment == sg) & (u.a8 == 1)]
    for r, lab in [(1, "cont"), (2, "rest")]:
        t = s[s.recency == r]; RESUME[(sg, lab)] = (len(t), int(((t.a9 + t.a10) > 0).sum()))
assert RESUME[("습관 형성형", "cont")] == (2799, 1392) and RESUME[("습관 형성형", "rest")] == (1307, 549)
na, ka = RESUME[("습관 형성형", "cont")]; nb, kb = RESUME[("습관 형성형", "rest")]
pa, pb = ka / na, kb / nb; pp = (ka + kb) / (na + nb)
RES_Z = (pa - pb) / sqrt(pp * (1 - pp) * (1 / na + 1 / nb))
RES_CI = 1.96 * sqrt(pa * (1 - pa) / na + pb * (1 - pb) / nb) * 100

# ---- 노션 Input metrics (관측 주간 7일)
key = set(zip(obs.user_id, obs.date))
ad6 = obs[obs.date <= T("2013-03-06")][["user_id", "date"]].copy()
ad6["nxt"] = [(a, b + pd.Timedelta(days=1)) in key for a, b in zip(ad6.user_id, ad6.date)]
ad6 = ad6.merge(u[["segment"]], left_on="user_id", right_index=True)
NEXT_ALL = (int(ad6.nxt.sum()), len(ad6))
NEXT_SEG = ad6.groupby("segment").nxt.agg(["sum", "size"]).reindex(SEG)
fa = obs.merge(u[["first_active"]], left_on="user_id", right_index=True)
u["first_vol"] = fa[fa.date == fa.first_active].groupby("user_id").seen.sum()
FVQ, FVQ_EDGES = pd.qcut(u.first_vol, 4, labels=["Q1", "Q2", "Q3", "Q4"], retbins=True)
u["fvq"] = FVQ
fvq_days = u.assign(dg=u.active_days.clip(upper=4)).groupby(["dg", "fvq"], observed=True).agg(n=("F", "size"), k2=("ret2", "sum"))
ACC_KW = kruskal(*[u.acc[u.segment == s] for s in SEG])
inp = pd.DataFrame({"spd": u.groupby("segment").spd.median(), "fv": u.groupby("segment").first_vol.median(),
                    "ws": u.groupby("segment").words_seen.median(), "acc": u.groupby("segment").acc.mean() * 100}).reindex(SEG)
MED = u.words_seen.median(); assert MED == 75
grid = u.assign(dg=u.active_days.clip(upper=4), hi=u.words_seen >= MED).groupby(["dg", "hi"]).agg(n=("F", "size"), k2=("ret2", "sum"))
two3 = u[u.active_days.isin([2, 3])]
T23 = (len(two3), int(two3.ret2.sum()))
T23H = two3[two3.segment == "습관 형성형"]; T23P = two3[two3.segment != "습관 형성형"]

# =============================================================== 2. PDF
FR = os.environ.get("KR_FONT", "C:/Windows/Fonts/malgun.ttf"); FB = os.environ.get("KR_FONT_BOLD", "C:/Windows/Fonts/malgunbd.ttf")
pdfmetrics.registerFont(TTFont("KR", FR)); pdfmetrics.registerFont(TTFont("KR-B", FB))
pdfmetrics.registerFontFamily("KR", normal="KR", bold="KR-B", italic="KR", boldItalic="KR-B")
TOTAL = 8
W, H = 595.276, 841.89; M = 38; CW = W - 2 * M
INK = HexColor("#152A3A"); MUTED = HexColor("#536674"); TEAL = HexColor("#117C7A"); PALE = HexColor("#EAF5F3")
LINE = HexColor("#DCE5E8"); GRAY = HexColor("#E2E7EA"); MID = HexColor("#8FC6BE"); ORANGE = HexColor("#BA713B"); BG = HexColor("#F5F7F8")
c = canvas.Canvas(OUT, pagesize=(W, H), pageCompression=1)
c.setTitle("듀오링고 코호트 분석 | 최종 통합본"); c.setAuthor("3팀 프로젝트")
c.setSubject("노션 지표 정의와 세그먼트 분석 최신 코드를 기준으로 두 코호트 분석을 통합")
bounds = []

def rect(x, y, w, h, fill=BG, stroke=None, r=0):
    c.setFillColor(fill); c.setStrokeColor(stroke or fill); c.roundRect(x, H - y - h, w, h, r, stroke=bool(stroke), fill=1)
def line(x1, y1, x2, y2, color=LINE, width=0.7):
    c.setStrokeColor(color); c.setLineWidth(width); c.line(x1, H - y1, x2, H - y2)
def txt(s, x, y, size=10, color=INK, bold=False, align="left"):
    c.setFont("KR-B" if bold else "KR", size); c.setFillColor(color)
    {"left": c.drawString, "right": c.drawRightString, "center": c.drawCentredString}[align](x, H - y - size * 0.85, str(s))
def p(s, x, y, w, size=10.3, leading=None, color=INK, bold=False):
    st = ParagraphStyle("b", fontName="KR-B" if bold else "KR", fontSize=size, leading=leading or size * 1.57,
                        textColor=color, wordWrap="CJK", allowWidows=0, allowOrphans=0)
    obj = Paragraph(s, st); ow, oh = obj.wrap(w, 1000); obj.drawOn(c, x, H - y - oh)
    bounds.append({"page": c.getPageNumber(), "top": round(y, 1), "bottom": round(y + oh, 1), "text": re.sub("<[^>]+>", "", s)[:80]})
    if y + oh > 792: raise RuntimeError(f"overflow p{c.getPageNumber()} {y + oh:.0f} {s[:50]}")
    return y + oh
def base(num, cat):
    rect(0, 0, W, 8, TEAL); txt("3팀 프로젝트  /  DUOLINGO", M, 25, 8.3, MUTED, bold=True); txt(cat, W - M, 25, 8.3, MUTED, align="right")
    line(M, 49, W - M, 49); line(M, 801, W - M, 801)
    txt("기준: 노션 지표 정의 · 세그먼트 분석 최신 코드 · 2013년 공개 학습 기록", M, 812, 8, MUTED)
    txt(f"{num:02d} / {TOTAL:02d}", W - M, 812, 8, MUTED, align="right")
def title(label, heading, sub):
    txt(label, M, 69, 9, TEAL, bold=True); y = p(heading, M, 91, CW, 23, 30, bold=True)
    return p(sub, M, y + 12, CW, 9.8, 15, color=MUTED)
def callout(s, y, h, size=10.4, lead=16.5):
    rect(M, y, CW, h, PALE, r=7); rect(M, y, 3, h, TEAL); p(s, M + 16, y + 12, CW - 32, size, lead)
def section(s, y): txt(s, M, y, 12.5, INK, bold=True)
def note(s, y, size=8.5, lead=13): return p(s, M, y, CW, size, lead, color=MUTED)
def table(headers, rows, x, y, widths, rh=24, hh=25, size=8.8, boldfirst=True):
    rect(x, y, sum(widths), hh, INK); off = x
    for h_, w in zip(headers, widths): p(h_, off + 7, y + 7, w - 14, 8.3, 11.5, color=white, bold=True); off += w
    yy = y + hh
    for i, row in enumerate(rows):
        rect(x, yy, sum(widths), rh, white if i % 2 else BG); off = x
        for j, (cell, w) in enumerate(zip(row, widths)):
            p(str(cell), off + 7, yy + 6, w - 14, size, size * 1.42, bold=(j == 0 and boldfirst)); off += w
        line(x, yy + rh, x + sum(widths), yy + rh); yy += rh
    return yy
def heat(v):  # 0~1 → 연한 청록~진한 청록
    return Color(.93 - .86 * v, .97 - .48 * v, .96 - .48 * v)

r1 = {d: rate(days.loc[d, "k1"], days.loc[d, "n"]) for d in days.index}
r2 = {d: rate(days.loc[d, "k2"], days.loc[d, "n"]) for d in days.index}
hit, miss = NSMG["hit"], NSMG["miss"]
rc1 = rec_curve.loc[1]
fq1 = {q: rate(fvq_days.loc[(1, q), "k2"], fvq_days.loc[(1, q), "n"]) for q in ["Q1", "Q2", "Q3", "Q4"]}

# ---------------------------------------------------------------- 1. 요약
base(1, "핵심 요약")
title("01  /  분석의 결론", "여러 날 학습한 사용자가 다시 돌아왔고,<br/>하루 공백이 가장 큰 하락 지점이었다",
      "듀오링고 코호트 분석 · 최종 통합본(코호트분석 + 코호트분석2) · 2026.10.15")
callout("<b>기준</b>  노션의 NSM(7일 중 4일 이상 학습)·지표 정의서·분석 질문과 '세그먼트 분석 최신' 코드의 전처리·6개 세그먼트 규칙을 원본 데이터에 그대로 적용해 모든 수치를 다시 계산했다.", 196, 62, 9.8, 15.5)
gap = 10; cw4 = (CW - gap * 3) / 4
for i, (lab, val, det) in enumerate([("주간 활성 학습자", "82,467", "3/1-3/7 1일 이상 학습"),
                                     ("NSM 지속 학습자", "9,834", "활성자 중 11.9%"),
                                     ("후속 4일 재학습", pct(29240, 82467), "29,240명 · 1일 이상"),
                                     ("후속 4일 반복학습", pct(13466, 82467), "13,466명 · 2일 이상")]):
    x = M + i * (cw4 + gap); rect(x, 272, cw4, 78, BG, r=6)
    txt(lab, x + 10, 282, 8.3, MUTED, bold=True); txt(val, x + 10, 302, 20, TEAL, bold=True); p(det, x + 10, 332, cw4 - 20, 7.6, 10.5, color=MUTED)
section("분석 질문별 답", 372)
y = 397
for num, head, body in [
    ("1", "학습 일수가 늘수록 후속 재학습이 계단처럼 높아졌다 (NSM)",
     f"NSM 달성군 {pct(hit['k1'], hit['n'])}, 미달성군 {pct(miss['k1'], miss['n'])}. 1일 {r1[1]:.1f}% → 4일 {r1[4]:.1f}% → 7일 {r1[7]:.1f}%. 4일에서 급변하지 않았다."),
    ("2", "6개 세그먼트의 반복학습률은 55.9%에서 4.7%까지 갈렸다 (분석 질문 1)",
     f"세그먼트 간 차이는 통계적으로 유의했다(카이제곱 p&lt;0.001). 마지막 학습일을 맞춰도 순서가 유지됐다."),
    ("3", "하루를 쉰 사용자는 재학습 가능성이 가장 크게 떨어졌다 (분석 질문 3)",
     f"1일 학습자 기준 마지막 학습이 어제면 {rate(rc1.loc[1,'k1'], rc1.loc[1,'n']):.1f}%, 이틀 전이면 {rate(rc1.loc[2,'k1'], rc1.loc[2,'n']):.1f}%. 같은 날 돌아온 습관 형성형도 쉬었다 온 사람이 {pa*100-pb*100:.1f}%p 덜 이어졌다."),
    ("4", "첫 학습일 학습량이 많을수록 반복학습이 높았다 (Input metric)",
     f"같은 1일 학습자 안에서도 첫날 학습량 하위 25% {fq1['Q1']:.1f}% → 상위 25% {fq1['Q4']:.1f}%. 정답률의 세그먼트 차이는 2%p 이내로 작았다.")]:
    txt(num, M, y, 13, TEAL, bold=True); y = p("<b>" + head + "</b><br/>" + body, M + 24, y, CW - 24, 9.4, 14) + 9
callout("<b>실행 제안</b>  NSM 직전 단계인 <b>습관 형성형</b>(2~3일 학습 + 최근 학습)에게 학습을 마친 직후 <b>다음 학습일을 정하는 안내</b>를 주고, 다음날 재학습률과 주간 NSM 달성률로 효과를 실험한다.", y + 6, 64, 9.8, 15.5)
c.showPage()

# ---------------------------------------------------------------- 2. NSM과 학습 일수
base(2, "NSM과 학습 일수")
title("02  /  NSM 관점의 코호트", "기준 주간 학습 일수가 늘수록<br/>후속 재학습이 단계적으로 높아졌다",
      "코호트 = 3/1-3/7 학습 일수(세그먼트 코드의 F 원값) · 후속 관측 3/8-3/11 · 분모: 각 코호트 전체")
half = (CW - 12) / 2
for i, (g, name) in enumerate([(hit, "NSM 달성군 · 4~7일"), (miss, "NSM 미달성군 · 1~3일")]):
    x = M + i * (half + 12); rect(x, 196, half, 82, PALE if i == 0 else BG, r=6)
    txt(f"{name} · {g['n']:,}명", x + 12, 206, 9, TEAL if i == 0 else MUTED, bold=True)
    txt(pct(g["k1"], g["n"]), x + 12, 226, 19, TEAL if i == 0 else INK, bold=True); txt("1일 이상 재학습", x + 12, 254, 8, MUTED)
    txt(pct(g["k2"], g["n"]), x + half / 2 + 6, 226, 19, TEAL if i == 0 else INK, bold=True); txt("2일 이상 반복학습", x + half / 2 + 6, 254, 8, MUTED)
note("날짜별 당일 재학습률(3/8→3/11): 달성군 " + "→".join(f"{v / hit['n'] * 100:.1f}" for v in hit["daily"]) + "%, 미달성군 " +
     "→".join(f"{v / miss['n'] * 100:.1f}" for v in miss["daily"]) + "%. 3/9·3/10은 주말이다.", 286)
section("학습 일수별 코호트 (1~7일)", 320)
rect(M, 344, 9, 9, MID); txt("1일 이상 재학습", M + 14, 342, 8, MUTED); rect(M + 118, 344, 9, 9, TEAL); txt("2일 이상 반복학습", M + 132, 342, 8, MUTED)
cx, cy, ch = M + 30, 368, 138; cwid = CW - 30
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
note(f"1일 학습자가 {days.loc[1, 'n']:,}명으로 전체의 {rate(days.loc[1, 'n'], 82467):.1f}%다. 2~3일 학습자는 {T23[0]:,}명({rate(T23[0], 82467):.1f}%)으로 NSM 바로 아래 단계다.", cy + ch + 38)
section("마지막 학습일을 3/7로 맞춰도 계단은 유지됐다", 588)
rw = (CW - 92) / 7
table(["학습 일수"] + [f"{d}일" for d in range(1, 8)],
      [["2일 이상"] + [pct(rec1_days.loc[d, "k2"], rec1_days.loc[d, "n"]) for d in range(1, 8)],
       ["인원"] + [f"{rec1_days.loc[d, 'n']:,}" for d in range(1, 8)]], M, 610, [92] + [rw] * 7, 21, 22, 8.3)
callout(f"<b>4일은 갑자기 달라지는 경계가 아니라 계단의 한 칸이었다.</b><br/>1일 이상 재학습 증가폭: 1→2일 +{r1[2] - r1[1]:.1f}%p, 2→3일 +{r1[3] - r1[2]:.1f}%p, 3→4일 +{r1[4] - r1[3]:.1f}%p.<br/>NSM은 목표선으로 두고, 개입은 바로 아래 단계(2~3일 학습자)를 겨냥한다.", 692, 70, 9.8, 15)
c.showPage()

# ---------------------------------------------------------------- 3. 세그먼트 코호트
base(3, "세그먼트 코호트")
title("03  /  행동 유형별 코호트", "세그먼트마다 후속 반복학습이<br/>12배 가까이 차이 났다",
      "코호트 = 세그먼트 분석 최신 코드의 6개 세그먼트(3/1-3/7 RFM 규칙) · 분모: 각 세그먼트 전체")
for x, lab, col in [(M, "후속 학습 없음", GRAY), (M + 118, "1일 학습", MID), (M + 210, "2일 이상 학습", TEAL)]:
    rect(x, 192, 9, 9, col); txt(lab, x + 14, 190, 8.3, MUTED)
barx = M + 118; barw = CW - 180
for i, s in enumerate(SEG):
    yy = 214 + i * 27; n = seg.loc[s, "n"]; k1, k2 = seg.loc[s, "k1"], seg.loc[s, "k2"]
    txt(s, M, yy, 9.6, bold=(s == "습관 형성형")); txt(f"n={n:,}", M, yy + 13, 7.4, MUTED)
    xx = barx
    for cnt, col in [(n - k1, GRAY), (k1 - k2, MID), (k2, TEAL)]:
        w = barw * cnt / n; rect(xx, yy + 1, w, 18, col); xx += w
    txt(pct(k2, n), W - M, yy + 4, 9.6, TEAL, bold=True, align="right")
RULE = ["R≥4, F≥4", "R≥4, F 2~3", "R≥4, F=1", "R≤3, F≥3", "R≤3, F≤2, M≥4", "R≤3, F≤2, M≤3"]
rows = []
for s, rl in zip(SEG, RULE):
    n = seg.loc[s, "n"]; lo, hi_ = wilson(seg.loc[s, "k2"], n)
    rows.append([s, rl] + [f"{rate(seg.loc[s, f'd{d.day}'], n):.1f}" for d in DATES] + [pct(seg.loc[s, "k1"], n), f"{pct(seg.loc[s, 'k2'], n)}<br/><font size=6.5>({lo:.1f}-{hi_:.1f})</font>"])
ty = table(["세그먼트", "규칙(점수)", "3/8", "3/9", "3/10", "3/11", "1일 이상", "2일 이상 (95% CI)"], rows, M, 384,
           [86, 92, 44, 44, 44, 44, 66, CW - 420], 28, 25, 8.3)
note(f"날짜 칸 = 당일 학습 비율(%). R: 3/7 학습 5점·3/6 4점 … / F: 학습 일수 / M: 학습 문항 수 5분위(경계 24·53·108·239). "
     f"6개 세그먼트의 2일 이상 반복학습 차이는 유의했다(χ²={CHI2[0]:,.0f}, 자유도 5, p&lt;0.001).", ty + 6)
section("마지막 학습일을 맞춰도 순서는 유지됐다", 622)
rw = (CW - 104) / 3
rr = []
for r, lab in [(1, "3/7 (어제)"), (2, "3/6 (이틀 전)")]:
    rr.append([lab] + [f"{pct(seg_rec.loc[(r, s), 'k2'], seg_rec.loc[(r, s), 'n'])} · n={seg_rec.loc[(r, s), 'n']:,}" for s in ["꾸준형", "습관 형성형", "최근 단발형"]])
table(["마지막 학습", "꾸준형", "습관 형성형", "최근 단발형"], rr, M, 644, [104, rw, rw, rw], 22, 23, 8.5)
note("최근 학습이 있는 세 세그먼트끼리 같은 날 마지막으로 학습한 사용자만 비교했다. 세그먼트는 기준 주간 행동으로 정의했으므로 이 결과는 분류의 타당성 확인이며 개입 효과가 아니다.", 716)
c.showPage()

# ---------------------------------------------------------------- 4. 첫 학습일 코호트
base(4, "첫 학습일 코호트")
title("04  /  관측 주 첫 학습일 코호트", "처음 학습한 다음날 다시 학습한 사용자는<br/>4명 중 1명 수준이었다",
      "코호트 = 세그먼트 코드의 first_active(관측 주 첫 학습일, '코호트용') · 칸 = 첫 학습일 k일 뒤 학습한 비율 · 3/11 이후는 관측 범위 밖")
labw = 110; ncol = 10; cellw = (CW - labw) / ncol; y0 = 200
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
        else:
            rect(xx + 1.5, yy, cellw - 3, 26, BG, r=2)
d1 = [r["D"][1] / r["n"] * 100 for r in TRI]
ylast = y0 + 18 + 7 * 30 + 8
note("D1은 첫 학습일 다음 날. 3/1 코호트에는 데이터가 2/28 저녁부터 시작해 이미 학습 중이던 사용자가 많이 섞여 있다. first_active는 관측 주의 첫 학습일이며 가입일이 아니다. 3/8 이후 칸은 후속 관측 기간이다.", ylast)
section("읽을 점", ylast + 54)
y = p(f"<b>· 첫날 이후 바로 이어진 비율이 낮다.</b>  3/2-3/7 코호트의 D1은 {min(d1[1:]):.1f}-{max(d1[1:]):.1f}%다. 노션 Input metric인 '다음날 재학습률'이 가장 먼저 무너지는 지점이다.", M, ylast + 78, CW, 9.3, 14.5)
_t = TRI[1]; _d9 = _t['D'][9] / _t['n'] * 100
y = p(f"<b>· 가장 큰 하락은 첫날 직후다.</b>  3/2 코호트는 첫날 100% → D1 {d1[1]:.1f}%로 떨어진 뒤, D9 {_d9:.1f}%까지 하루 평균 {(d1[1] - _d9) / 8:.1f}%p씩 완만하게 줄었다.", M, y + 6, CW, 9.3, 14.5)
y = p(f"<b>· 요일 영향이 섞인다.</b>  예: 3/4 코호트는 토·일인 D5·D6이 {TRI[3]['D'][5] / TRI[3]['n'] * 100:.1f}·{TRI[3]['D'][6] / TRI[3]['n'] * 100:.1f}%로 월요일 D7 {TRI[3]['D'][7] / TRI[3]['n'] * 100:.1f}%보다 낮았다. 전체 사용자의 당일 학습 비율도 3/8-3/11에 18.0→14.2→13.6→15.1%였다.", M, y + 6, CW, 9.3, 14.5)
callout("코호트분석2는 이 분석을 '최초 학습일 기준 리텐션과 구분된다'며 제외했고, 코호트분석은 후속 기간의 첫 재학습일 기준 코호트만 다뤘다. 세그먼트 코드가 first_active를 코호트용으로 남겨 둔 만큼 통합본에 추가했다.", y + 14, 64, 9.4, 15)
c.showPage()

# ---------------------------------------------------------------- 5. 이탈 위험
base(5, "비활동과 이탈 위험")
title("05  /  비활동과 재학습", "하루를 쉬는 순간<br/>재학습 가능성이 가장 크게 떨어졌다",
      "분석 질문 3(이탈 위험) · 노션 가설 후보 5(마지막 학습 후 경과 시간과 재접속) · 결과: 3/8-3/11 중 1일 이상 학습")
section("마지막 학습 후 경과일별 후속 재학습률", 190)
px, py, pw, ph = M + 34, 230, CW - 50, 150
for v in [0, 20, 40, 60]:
    yy = py + ph * (1 - v / 60); line(px, yy, px + pw, yy); txt(f"{v}%", px - 6, yy - 4, 7.5, MUTED, align="right")
for ad_, col, lab in [(1, TEAL, "기준 주간 1일 학습"), (2, ORANGE, "기준 주간 2일 학습")]:
    cur = rec_curve.loc[ad_]; ks = list(cur.index)
    pts = [(px + (k - 1) * pw / 6, py + ph * (1 - rate(cur.loc[k, "k1"], cur.loc[k, "n"]) / 60)) for k in ks]
    for a, b in zip(pts, pts[1:]): line(*a, *b, col, 2)
    for (xx, yy), k in zip(pts, ks):
        c.setFillColor(col); c.circle(xx, H - yy, 2.8, fill=1, stroke=0)
        txt(f"{rate(cur.loc[k, 'k1'], cur.loc[k, 'n']):.1f}", xx, yy - (14 if ad_ == 2 else -6), 7.4, col, bold=True, align="center")
rect(M, 210, 9, 9, TEAL); txt("기준 주간 1일 학습", M + 14, 208, 8, MUTED); rect(M + 130, 210, 9, 9, ORANGE); txt("기준 주간 2일 학습", M + 144, 208, 8, MUTED)
for k in range(1, 8): txt(f"{k}일 전", px + (k - 1) * pw / 6, py + ph + 8, 8.3, MUTED, align="center")
txt("마지막 학습일 (3/8 기준)", px + pw, py + ph + 22, 7.6, MUTED, align="right")
drop1 = rate(rc1.loc[1, "k1"], rc1.loc[1, "n"]) - rate(rc1.loc[2, "k1"], rc1.loc[2, "n"])
drop2 = rate(rc1.loc[2, "k1"], rc1.loc[2, "n"]) - rate(rc1.loc[3, "k1"], rc1.loc[3, "n"])
note(f"학습 일수를 같게 두고 비교했다. 1일 학습자는 마지막 학습이 어제→이틀 전이 되면 {drop1:.1f}%p, 이틀→사흘 전이면 {drop2:.1f}%p 떨어졌고 이후 완만해졌다. 단, 마지막 학습이 이른 사람은 추적 시작 전 공백도 길다.", py + ph + 40)
section("같은 날 돌아온 사용자: 이어서 학습 vs 쉬었다 재개", 482)
rows = []
for sg in ["꾸준형", "습관 형성형", "최근 단발형"]:
    (n0, k0), (n1, k1_) = RESUME[(sg, "cont")], RESUME[(sg, "rest")]
    rows.append([sg, f"{pct(k0, n0)} · n={n0:,}", f"{pct(k1_, n1)} · n={n1:,}", f"{rate(k0, n0) - rate(k1_, n1):.1f}%p"])
ty = table(["3/8에 학습한 사용자", "3/7에도 학습 (이어서)", "3/6이 마지막 (하루 쉬고 재개)", "차이"], rows, M, 506, [128, 140, 160, CW - 428], 24, 25, 8.8)
note(f"결과 = 3/9·3/10 중 추가 학습 비율. 습관 형성형 차이 {pa*100-pb*100:.1f}%p(95% CI ±{RES_CI:.1f}%p, z={RES_Z:.2f}). 다음 두 날이 주말인 같은 날짜끼리의 관측 비교다. 코호트분석의 A0/A1 비교를 원본에서 재계산해 같은 값을 확인했다.", ty + 6)
callout("<b>이탈 위험 신호는 '하루 공백'이다.</b>  공백이 생기기 전 다음 학습을 약속하게 하거나, 쉬었다 돌아온 순간 다음 학습을 연결하는 개입이 가장 큰 하락 구간을 겨냥한다. 기록이 없다는 것은 이 데이터에 학습 기록이 없다는 뜻이며 영구 이탈은 아니다.", 670, 70, 9.6, 15.5)
c.showPage()

# ---------------------------------------------------------------- 6. Input metrics와 학습량
base(6, "Input metrics와 학습량")
title("06  /  노션 Input metric으로 본 세그먼트", "첫 학습일 학습량은 같은 학습 일수 안에서도<br/>반복학습과 함께 움직였다",
      "지표 정의는 노션 지표 정의서를 따른다 · 관측 주간 3/1-3/7 · 학습 문항 수 = session_seen 합")
rows = []
for s in SEG:
    ns, nz = NEXT_SEG.loc[s, "sum"], NEXT_SEG.loc[s, "size"]
    rows.append([s, pct(ns, nz), f"{inp.loc[s, 'spd']:.1f}", f"{inp.loc[s, 'fv']:.0f}", f"{inp.loc[s, 'ws']:.0f}", f"{inp.loc[s, 'acc']:.1f}%"])
rows.append(["전체", pct(*NEXT_ALL), f"{u.spd.median():.1f}", f"{u.first_vol.median():.0f}", f"{MED:.0f}", f"{u.acc.mean() * 100:.1f}%"])
ty = table(["세그먼트", "다음날 재학습률", "활동일당 세션 (중앙값)", "첫 학습일 학습량 (중앙값)", "주간 학습 문항 (중앙값)", "평균 정답률"],
           rows, M, 186, [94, 82, 86, 92, 86, CW - 440], 22, 34, 8.6)
note(f"다음날 재학습률 = 3/1-3/6 활동일 중 다음날에도 활동한 비율(사용자-활동일 단위). 세그먼트가 활동 일수·최근성으로 정의돼 있어 세그먼트별 차이 일부는 정의상 생긴다(최근 단발형은 구조상 0%). "
     f"평균 정답률은 세그먼트 간 통계적 차이가 있었지만(Kruskal-Wallis p&lt;0.001) 폭이 {inp.acc.max() - inp.acc.min():.1f}%p로 작았다.", ty + 6)
section("첫 학습일 학습량 × 학습 일수 → 2일 이상 반복학습", 428)
rows = []
for dg, lab in [(1, "1일"), (2, "2일"), (3, "3일"), (4, "4일 이상")]:
    rows.append([lab] + [f"{pct(fvq_days.loc[(dg, q), 'k2'], fvq_days.loc[(dg, q), 'n'])} · {fvq_days.loc[(dg, q), 'n']:,}" for q in ["Q1", "Q2", "Q3", "Q4"]])
e = [int(x) for x in FVQ_EDGES]
ty = table(["학습 일수", f"Q1 (≤{e[1]}문항)", f"Q2 ({e[1]+1}-{e[2]})", f"Q3 ({e[2]+1}-{e[3]})", f"Q4 (>{e[3]})"], rows, M, 452,
           [86] + [(CW - 86) / 4] * 4, 23, 25, 8.5)
note("칸 = 2일 이상 반복학습 비율 · 인원. 노션 가설 후보 2(첫 학습일 학습량이 많으면 리텐션이 높다)와 같은 방향이다. 관측 연관성이며 학습량을 늘리면 재학습이 오른다는 인과 근거는 아니다.", ty + 6)
section("코호트분석2의 학습량 교차 분석 보완", 612)
rows = []
for dg, lab in [(1, "1일"), (2, "2일"), (3, "3일"), (4, "4일 이상")]:
    lo, hi_ = grid.loc[(dg, False)], grid.loc[(dg, True)]
    rows.append([lab, f"{pct(lo.k2, lo.n)} · {lo.n:,}", f"{pct(hi_.k2, hi_.n)} · {hi_.n:,}"])
ty = table(["학습 일수", f"주간 학습 문항 {MED:.0f} 미만", f"{MED:.0f} 이상"], rows, M, 634, [120, (CW - 120) / 2, (CW - 120) / 2], 21, 23, 8.5)
note(f"코호트분석2는 중앙값을 27문항으로 보고 수치를 확정하지 못했다. 세그먼트 코드 정의(12개 열 중복 제거 후 session_seen 합)의 중앙값은 {MED:.0f}문항이다. 27은 user_id·timestamp·session_seen 세 열로 중복을 지울 때 나오는 값으로, 서로 다른 단어의 기록이 지워진 결과다.", ty + 6)
c.showPage()

# ---------------------------------------------------------------- 7. 우선 대상과 실행
base(7, "우선 대상과 실행 제안")
title("07  /  누구에게 무엇을", "NSM 직전의 습관 형성형에게<br/>다음 학습일을 약속하게 한다",
      "두 파일의 제안(2~3일 학습군 · 습관 형성형 재개자)은 모두 '다음 학습일 안내'로 모였다. 대상과 지표를 노션 기준으로 맞췄다.")
section("대상을 좁히는 순서", 188)
fun = [("주간 활성 학습자", 82467, f"2일 이상 {pct(13466, 82467)}"),
       ("2~3일 학습 (NSM 바로 아래)", T23[0], f"2일 이상 {pct(T23[1], T23[0])}"),
       ("그중 최근 학습 = 습관 형성형", len(T23H), f"2일 이상 {pct(T23H.ret2.sum(), len(T23H))}"),
       ("그중 최근 학습 없음 = 멈춤 계열", len(T23P), f"2일 이상 {pct(T23P.ret2.sum(), len(T23P))}")]
bx0 = M + 182; bmax = CW - 182
for i, (lab, n, nt) in enumerate(fun):
    yy = 212 + i * 38
    txt(lab, M, yy + 2, 9.1, INK, bold=(i == 2)); txt(nt, M, yy + 16, 7.6, MUTED)
    w = max(bmax * n / 82467, 4); rect(bx0, yy, w, 24, TEAL if i == 2 else (GRAY if i == 3 else MID), r=3)
    inside = w > bmax - 60
    txt(f"{n:,}명", bx0 + w - 6 if inside else bx0 + w + 6, yy + 7, 8.8, white if inside else INK, bold=True, align="right" if inside else "left")
note(f"같은 2~3일 학습자라도 최근 학습이 있으면 반복학습이 {rate(T23H.ret2.sum(), len(T23H)) - rate(T23P.ret2.sum(), len(T23P)):.1f}%p 높았다. 학습 일수(코호트분석2)만으로 대상을 잡으면 이미 멈춘 사용자가 43% 섞인다.", 370)
section("실험안", 418)
table(["항목", "통합안"],
      [["대상", "습관 형성형 (3/1-3/7 중 2~3일 학습, 마지막 학습이 최근 이틀 안)"],
       ["시점", "학습을 마친 직후 (하루 공백이 생기기 전). 하루 이상 쉬고 돌아온 경우에도 같은 시점에 노출"],
       ["개입", "다음 학습일 정하기 안내 1회 + 주간 4일 목표 표시 (두 파일의 안내안을 합침)"],
       ["배정", "사용자 단위 1:1 무작위 배정, 안내를 보지 않은 사람도 배정군에 포함"],
       ["주 지표", "다음날 재학습률 (노션 Input metric, 노출 다음날 학습 여부)"],
       ["보조 지표", "후속 7일 NSM 달성률(코호트분석2), 2일 이상 반복학습률"]],
      M, 442, [90, CW - 90], 27, 25, 8.8)
ty7 = 442 + 25 + 27 * 6
note(f"현재 기준값: 습관 형성형 다음날 재학습률 {pct(NEXT_SEG.loc['습관 형성형', 'sum'], NEXT_SEG.loc['습관 형성형', 'size'])}(관측 주간). 7일 NSM은 4일 추적으로 기준값을 낼 수 없어 보조 지표로 두었다. 표본 수는 목표 개선 폭을 팀에서 정한 뒤 산정한다.", ty7 + 6)
callout("<b>이 분석이 말하지 않는 것</b><br/>안내의 실제 효과, 영구 이탈, 4일 이후의 장기 유지. 모두 관측 데이터의 연관성이며 효과는 실험으로 확인해야 한다. 공개 학습 기록에 없는 활동(다른 기능 사용 등)은 반영되지 않는다.", 680, 76, 9.6, 15.5)
c.showPage()

# ---------------------------------------------------------------- 8. 통합 기준
base(8, "통합 기준과 자료")
title("08  /  두 파일을 어떻게 통합했나", "노션 기준에 비춰 두 파일을 평가하고<br/>맞는 부분만 남겼다",
      "기준: 노션 문제정의·분석 질문·NSM·Input metric·지표 정의서·분석 가설, 세그먼트 분석 최신 코드")
table(["노션·세그먼트 코드 기준", "코호트분석", "코호트분석2", "통합본"],
      [["6개 세그먼트를 코호트 축으로 사용", "O", "X (학습 일수만)", "3장"],
       ["NSM(7일 중 4일) 중심 해석", "△ (KPI로만)", "O", "2장"],
       ["Input metric(다음날 재학습률·첫 학습일 학습량)", "X", "X", "4·6장 신규"],
       ["first_active(관측 주 첫 학습일) 코호트", "X", "X (제외 명시)", "4장 신규"],
       ["이탈 위험(분석 질문 3)", "O (재개자 비교)", "X", "5장"],
       ["통계적 유의성(성공 기준)", "O", "X", "3·5장"],
       ["세그먼트 코드의 전처리 정의", "O", "△ (학습량 중복 제거 오류)", "6장 정정"],
       ["실행 가능한 인사이트", "O (과도하게 상세)", "O", "7장"]],
      M, 186, [190, 100, 120, CW - 410], 23, 25, 8.4, boldfirst=False)
y = note("O 충족 · △ 부분 · X 미충족", 399)
section("평가와 처리", 424)
y = p("<b>중심 파일은 코호트분석.</b>  노션의 흐름(세그먼트 → 코호트 → 가설)과 성공 기준(통계적 유의성)을 따른 쪽이다. 다만 A1·완전 관측 같은 자체 용어, 표본 수 8,692명 같은 실험 설계 세부, 회귀 모형(OR) 결과는 코호트 분석 범위를 넘어 이번 통합본에서 뺐다. 가설 결과는 노션의 '가설 검증' 페이지, 실험 세부는 실험 설계 문서로 분리하는 것을 권한다.", M, 448, CW, 9.1, 14)
y = p("<b>코호트분석2에서 가져온 것.</b>  NSM 달성 여부와 학습 일수 1~7일 코호트(2장), 2~3일 학습군을 우선 대상으로 본 관점(7장), 7일 NSM 보조 지표. 팀원 표의 37개 값은 원본 재계산과 모두 일치했다. 학습량 중앙값 27은 오류로 확인돼 75로 정정했다.", M, y + 8, CW, 9.1, 14)
y = p("<b>두 파일 모두에 없던 것.</b>  노션 Input metric(다음날 재학습률·활동일당 세션·첫 학습일 학습량)과 first_active 코호트를 추가했다.", M, y + 8, CW, 9.1, 14)
section("데이터와 재현", y + 22)
note(f"Duolingo Spaced Repetition Dataset(Settles &amp; Meeder, 2016) 원본 {N_RAW:,}행. 세그먼트 코드대로 12개 열 완전 중복 {N_DUP}행 제거, 3/1-3/11 하루가 온전한 구간(사용자 {N_USERS_311:,}명), 관측 주간 3/1-3/7, RFM 기준일 3/8. "
     "세션 = 사용자+timestamp 추정, 학습 문항 수 = session_seen 합. 세그먼트 인원·M 경계(24·53·108·239)가 코드 결과와 일치했다. "
     "생성 코드: 코호트분석_통합/build_cohort_final.py (원본 → 집계 → 보고서, 두 파일 수치 대조 포함).", y + 46, 8.3, 12.5)
c.showPage(); c.save()

# =============================================================== 3. 검증 기록
reader = PdfReader(OUT); assert len(reader.pages) == TOTAL
text = "\n".join(pg.extract_text() for pg in reader.pages)
for req in ["82,467", "9,834", "77.8%", "29.7%", "21.8", "96.6", "55.9%", "4.7%", "49.7%", "42.0%", "75", "25,546", "14,583"]:
    assert req in text, req
assert "\ufffd" not in text
summary = {"source_rows": N_RAW, "duplicates_removed": N_DUP, "users_0301_0311": N_USERS_311, "baseline_users": len(u),
           "nsm": int((u.active_days >= 4).sum()), "m_edges": [float(x) for x in M_EDGES], "median_words_seen": float(MED),
           "segment_n": SEG_N.to_dict(), "segment_ret2": seg.k2.to_dict(), "chi2_ret2": [float(CHI2[0]), float(CHI2[1])],
           "next_day_overall": NEXT_ALL, "first_vol_median": float(u.first_vol.median()), "first_vol_quartile_edges": [float(x) for x in FVQ_EDGES],
           "resume_compare": {f"{k[0]}|{k[1]}": v for k, v in RESUME.items()},
           "first_active_cohorts": [{"first": str(r["first"].date()), "n": r["n"], **{f"D{k}": v for k, v in r["D"].items()}} for r in TRI],
           "teammate_values_matched": 37}
with open(os.path.join(OUTDIR, "cohort_final_metrics.json"), "w", encoding="utf-8") as f:
    json.dump(summary, f, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o))
print(json.dumps({"output": OUT, "pages": TOTAL}, ensure_ascii=False))
