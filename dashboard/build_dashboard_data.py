"""듀오링고 이탈 방지 대시보드 데이터 생성.

입력(v3 산출물, 원본 CSV에서 파생):
  regularity/baseline_unique_timestamps.csv  기준 주간(3/1~3/7) 사용자별 학습 시각
  cohort_inputs/user_daily_activity.csv                 후속 4일(3/8~3/11) 사용자·날짜별 학습 여부
  segmentation/user_rfm.csv                             사용자별 학습량(words_seen), K-means 군집
  learning_traces.13m.csv (원본)                        H2 정답률 변화용 세션별 문항·정답 수 (노션 코드와 같은 중복 제거 후)
출력(기본값은 모두 이 스크립트 폴더): dashboard_data.json, 그리고 dashboard_template.html의 __DATA__에 넣은 duolingo_dashboard.html
모든 수치는 여기서 계산하고, 노션 「듀오링고 이탈 방지 분석」 값과 대조해 하나라도 다르면 중단한다.
실행(프로젝트 루트): python dashboard/build_dashboard_data.py [v3 폴더] [json 출력] [html 출력] [원본 csv]
화면을 고칠 때는 duolingo_dashboard.html이 아니라 dashboard_template.html을 고친다.
"""
import json, os, sys
import numpy as np, pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
V3 = sys.argv[1] if len(sys.argv) > 1 else "cohort_v2/"
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(HERE, "dashboard_data.json")
HTML = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, "duolingo_dashboard.html")
RAW = sys.argv[4] if len(sys.argv) > 4 else "learning_traces.13m.csv/learning_traces.13m.csv"
TEMPLATE = os.path.join(HERE, "dashboard_template.html")
SEG = ["꾸준형", "습관 형성형", "최근 단발형", "멈춤-꾸준형", "멈춤-몰입형", "멈춤-저활동형"]
P = lambda x: round(100 * float(x), 1)
P2 = lambda x: round(100 * float(x), 2)
day = pd.Timedelta(days=1)

ts = pd.read_csv(V3 + "regularity/baseline_unique_timestamps.csv")
ts["date"] = pd.to_datetime(ts.timestamp, unit="s").dt.normalize()
bd = ts[["user_id", "date"]].drop_duplicates()
fa = pd.read_csv(V3 + "cohort_inputs/user_daily_activity.csv")
fd = fa[fa.active == 1][["user_id", "date"]].copy()
fd["date"] = pd.to_datetime(fd.date)
rfm = pd.read_csv(V3 + "segmentation/user_rfm.csv").set_index("user_id")
alld = pd.concat([bd, fd]).drop_duplicates().sort_values(["user_id", "date"])
dset = set(zip(alld.user_id, alld.date))

# ---- 사용자 표
u = bd.groupby("user_id").agg(first=("date", "min"), last=("date", "max"), days=("date", "nunique"))
u["recency"] = (pd.Timestamp("2013-03-08") - u["last"]).dt.days
u["words"] = rfm["words_seen"].reindex(u.index)
u["cluster"] = rfm["cluster"].reindex(u.index)
u["ret_days"] = fd.groupby("user_id").date.nunique().reindex(u.index).fillna(0).astype(int)
u["ret1"] = u.ret_days >= 1
u["ret2"] = u.ret_days >= 2
FOLLOW = list(pd.date_range("2013-03-08", "2013-03-11"))
for d in FOLLOW:
    u["d" + d.strftime("%m%d")] = u.index.isin(set(fd.loc[fd.date == d, "user_id"]))
u["F"] = pd.cut(u.days, [0, 1, 2, 3, 4, 7], labels=[1, 2, 3, 4, 5]).astype(int)
u["M"], m_edges = pd.qcut(u.words, 5, labels=[1, 2, 3, 4, 5], retbins=True)
u["M"] = u.M.astype(int)
u["R"] = pd.cut(u.recency, [0, 1, 2, 4, 6, 7], labels=[5, 4, 3, 2, 1]).astype(int)
cond = [(u.R >= 4) & (u.F >= 4), (u.R >= 4) & u.F.isin([2, 3]), (u.R >= 4) & (u.F == 1),
        (u.R <= 3) & (u.F >= 3), (u.R <= 3) & (u.M >= 4)]
u["seg"] = np.select(cond, SEG[:5], default=SEG[5])
assert (u.seg == rfm.segment.reindex(u.index)).all(), "세그먼트가 v3 파일과 다름"

D = {"meta": {"base": "2013-03-01~03-07", "follow": "2013-03-08~03-11", "users": int(len(u)),
              "m_edges": [int(x) for x in m_edges]}}

# ---- 탭 1
nsm = u.days >= 4
stop = u[u.recency >= 3]
b6 = bd[bd.date <= "2013-03-06"]
i1 = np.mean([(a, b + day) in dset for a, b in zip(b6.user_id, b6.date)])
act = u[u["first"] <= "2013-03-06"]
ac1 = np.mean([(a, b + day) in dset for a, b in zip(act.index, act["first"])])
D["kpi"] = {
    "N1": int(nsm.sum()), "N1_pct": P(nsm.mean()), "B1": int(len(u)),
    "I1": P(i1), "I1_n": int(len(b6)),
    "I2": P(stop.ret1.mean()), "I2_exact": P2(stop.ret1.mean()), "I2_n": int(len(stop)),
    "O1": P(u.ret1.mean()), "O2": P(u.ret2.mean()),
    "O3_n": int((~u.ret1).sum()), "O3": P((~u.ret1).mean()),
    "AC1": P(ac1), "AC1_n": int(len(act)),
    "nsm_ret": P(u[nsm].ret1.mean()), "rest_ret": P(u[~nsm].ret1.mean()),
    "two_plus": P((u.days >= 2).mean()),
}
g = u.groupby("days")
D["ret_by_days"] = [{"days": int(k), "n": int(len(v)), "ret": P(v.ret1.mean()), "ret_exact": P2(v.ret1.mean())} for k, v in g]

# 퍼널 인용(다음날 재학습)
fu = u[u["first"] <= "2013-03-04"]
c = fu[fu["first"] == "2013-03-01"].copy()
c["nd"] = [(a, pd.Timestamp("2013-03-02")) in dset for a in c.index]
d37 = bd[bd.date >= "2013-03-03"].groupby("user_id").date.nunique()
c["c37"] = d37.reindex(c.index).fillna(0) >= 3
D["funnel"] = {"one_to_two": P((fu.days >= 2).mean()), "cohort_n": int(len(c)),
               "came_4d": P((c[c.nd].days >= 4).mean()), "came_4d_excl": P(c[c.nd].c37.mean()),
               "not_4d": P((c[~c.nd].days >= 4).mean())}

# ---- 세그먼트
segs = []
tw = u.words.sum()
for s in SEG:
    v = u[u.seg == s]
    nonret = int((~v.ret1).sum())
    per = round(v.words.sum() / len(v))
    segs.append({"name": s, "n": int(len(v)), "user_pct": P(len(v) / len(u)), "word_pct": P(v.words.sum() / tw),
                 "ret": P(v.ret1.mean()), "ret2": P(v.ret2.mean()), "nonret": nonret,
                 "lost": int(round(nonret * per, -3)),
                 "daily": [P(v["d" + d.strftime("%m%d")].mean()) for d in FOLLOW]})
# 세그먼트별 I1: 후속 기간(3/8~3/10) 학습일 중 다음 날에도 학습한 비율 (노션 3-2. 기준 주간으로 재면 분류 기준을 다시 재는 셈)
fset = set(zip(fd.user_id, fd.date))
l1 = fd[(fd.date <= "2013-03-10") & fd.user_id.isin(u.index)].copy()
l1["nxt"] = [(a, b + day) in fset for a, b in zip(l1.user_id, l1.date)]
l1["seg"] = l1.user_id.map(u.seg)
for s_ in segs:
    s_["i1_later"] = P(l1[l1.seg == s_["name"]].nxt.mean())
wkend = l1.date.isin(pd.to_datetime(["2013-03-09", "2013-03-10"]))
D["i1_later"] = {"all": P(l1.nxt.mean()), "n": int(len(l1)),
                 "d0308": P(l1[l1.date == "2013-03-08"].nxt.mean()), "weekend": P(l1[wkend].nxt.mean())}
D["segments"] = segs
D["daily_all"] = [P(u["d" + d.strftime("%m%d")].mean()) for d in FOLLOW]
km = []
for cl, v in u.groupby("cluster"):
    hab = u[u.seg == "습관 형성형"]
    km.append({"name": cl, "n": int(len(v)), "word_pct": P(v.words.sum() / tw), "ret": P(v.ret1.mean()),
               "habit_share": P((hab.cluster == cl).mean())})
D["kmeans"] = km
top3 = u.seg.isin(["꾸준형", "습관 형성형", "멈춤-몰입형"])
D["concentration"] = {"user_pct": P(top3.mean()), "word_pct": P(u[top3].words.sum() / tw)}

# ---- 탭 3 이탈 곡선
alld = alld[alld.user_id.isin(u.index)].copy()
alld["gap"] = (alld.groupby("user_id").date.shift(-1) - alld.date).dt.days
alld["hist"] = alld.groupby("user_id").cumcount() + 1
base = alld[alld.date <= "2013-03-04"].copy()
base["g"] = base.gap.where(base.gap <= 7, 99).fillna(99)
def hz(b):
    out = []
    for k in range(4):
        risk = int((b.g >= k + 1).sum())
        nx = (b.g == k + 1).sum() / risk; w4 = ((b.g >= k + 1) & (b.g <= k + 4)).sum() / risk
        out.append({"rest": k, "risk_n": risk, "next": P(nx), "within4": P(w4), "_nx": nx, "_w4": w4})
    for k in range(1, 4):  # 직전 쉬는 날 대비 변화율(%), 반올림 전 값으로 계산
        out[k]["chg_next"] = int(round((out[k]["_nx"] / out[k - 1]["_nx"] - 1) * 100))
        out[k]["chg_within4"] = int(round((out[k]["_w4"] / out[k - 1]["_w4"] - 1) * 100))
    for o in out:
        del o["_nx"], o["_w4"]
    return out
H = base["hist"]
D["hazard"] = {"events": int(len(base)), "all": hz(base),
               "h1": hz(base[H == 1]), "h2": hz(base[H == 2]), "h3": hz(base[H >= 3]),
               "h_n": [int((H == 1).sum()), int((H == 2).sum()), int((H >= 3).sum())]}

# A1: 멈춘 사용자 중 고학습(M4~5), 마지막 학습 3/4~5(R3)
st = u[u.R <= 3].copy()
st["dd"] = st.days.clip(upper=3)
a = st[(st.M >= 4) & (st.R == 3)]
D["A1"] = [{"days": int(k), "n": int(len(v)), "ret": P(v.ret1.mean())} for k, v in a.groupby("dd")]
one_r3 = st[(st.dd == 1) & (st.R == 3)]
D["A1_one_day"] = [{"M": int(k), "n": int(len(v)), "ret": P(v.ret1.mean())} for k, v in one_r3.groupby("M") if k in (1, 5)]

# H2: 기준 주간 세션(user_id·timestamp)을 시간순 앞/뒤 절반으로 나눈 정답률 차이, 세션 3개 이상 (노션 2-1, 통합 코드 5절)
raw = pd.read_csv(RAW, dtype={"user_id": "category", "learning_language": "category", "ui_language": "category",
                              "lexeme_id": "category", "lexeme_string": "category"}).drop_duplicates()
# 운영용 북극성 지표(노션 4-5): 기준일 D마다 최근 7일(D-7~D-1) 학습일이 4일 이상인 사용자 수.
# 3/8 이후 처음 나타난 사용자도 세야 하므로 v3 기준 집단이 아니라 원본 전체에서 센다. D=3/12까지(3/12는 하루가 온전하지 않아 창에 넣지 않음)
tall = pd.to_datetime(raw.timestamp, unit="s")
keep = (tall >= "2013-03-01") & (tall < "2013-03-12")
ud = (pd.DataFrame({"uid": raw.user_id[keep].astype(str).values, "date": tall[keep].dt.normalize().values,
                    "seen": raw.session_seen[keep].values})
      .groupby(["uid", "date"], as_index=False).seen.sum())
del tall, keep
M_HIGH = int(m_edges[3]) + 1   # 고학습(M4 이상) 경계. 분석용 3/8 경계(109문항)를 운영용에도 그대로 쓴다


def op_seg(base):
    """노션 5-2 규칙을 기준일 base의 최근 7일(base-7~base-1)에 적용. 최근 이틀 = base-1, base-2"""
    g = ud[(ud.date >= base - 7 * day) & (ud.date < base)].groupby("uid").agg(
        days=("date", "size"), last=("date", "max"), words=("seen", "sum"))
    rec = g["last"] >= base - 2 * day
    g["seg"] = np.select([rec & (g.days >= 4), rec & g.days.between(2, 3), rec & (g.days == 1),
                          ~rec & (g.days >= 3), ~rec & (g.words >= M_HIGH)], SEG[:5], default=SEG[5])
    return g


fmt = lambda t: t.strftime("%m/%d").lstrip("0").replace("/0", "/")
ops, segs_by_d = [], {}
for base in pd.date_range("2013-03-08", "2013-03-12"):
    g = op_seg(base)
    segs_by_d[fmt(base)] = g.seg
    ops.append({"d": fmt(base), "dow": "월화수목금토일"[base.dayofweek], "from": fmt(base - 7 * day), "to": fmt(base - day),
                "n": int((g.days >= 4).sum()), "active": int(len(g)), "pct": P((g.days >= 4).mean()),
                "segs": [int((g.seg == s).sum()) for s in SEG]})
D["ops_nsm"] = ops
# 운영용 3/8 세그먼트는 분석용 세그먼트와 같아야 한다 (노션 4-5: D가 3월 8일이면 운영용 값은 분석용 값과 같다)
assert segs_by_d["3/8"].sort_index().equals(u.seg.sort_index().rename("seg")), "운영용 3/8 세그먼트가 분석용과 다름"

# 세그먼트 이동표: 3/8 세그먼트 → 3/12 세그먼트 (CleverTap RFM Transition·Klaviyo 그룹 변화와 같은 관점)
NONE = "최근 7일 학습 없음"
s0, s1 = segs_by_d["3/8"], segs_by_d["3/12"]
uids = s0.index.union(s1.index)
fr, to = s0.reindex(uids).fillna(NONE), s1.reindex(uids).fillna(NONE)
cols = SEG + [NONE]
mig = []
for r in SEG + [NONE]:
    m = fr == r
    cnt = [int((m & (to == c)).sum()) for c in cols]
    mig.append({"from": r, "n": int(m.sum()), "to": cnt, "pct": [P(x / m.sum()) for x in cnt]})
D["migration"] = {"from_d": "3/8", "to_d": "3/12", "cols": cols, "rows": mig}
del ud
raw = raw[(raw.timestamp >= pd.Timestamp("2013-03-01").timestamp()) & (raw.timestamp < pd.Timestamp("2013-03-08").timestamp())]
# I3: 기준 주간 첫 학습일에 푼 문항 수(session_seen 합)의 중앙값 (노션 3-2 보조 Input, 같은 원본 행 사용)
fw = raw.assign(uid=raw.user_id.astype(str), date=pd.to_datetime(raw.timestamp, unit="s").dt.normalize())
fw = fw[fw.date.values == u["first"].reindex(fw.uid).values].groupby("uid").session_seen.sum().reindex(u.index)
D["kpi"]["I3"] = int(round(fw.median()))
D["kpi"]["I3_n"] = int(fw.notna().sum())
del fw
ses =(raw.groupby(["user_id", "timestamp"], observed=True)
       .agg(seen=("session_seen", "sum"), correct=("session_correct", "sum")).reset_index()
       .sort_values(["user_id", "timestamp"]))
del raw
ses["user_id"] = ses.user_id.astype(str)
ses["n"] = ses.groupby("user_id").timestamp.transform("size")
ses = ses[ses.n >= 3].copy()
ses["rank"] = ses.groupby("user_id").cumcount()
half = ses.n // 2
ses["part"] = np.where(ses["rank"] < half, "early", np.where(ses["rank"] >= ses.n - half, "late", "mid"))
pa = ses[ses.part != "mid"].groupby(["user_id", "part"])[["seen", "correct"]].sum()
acc = (pa.correct / pa.seen).unstack("part")
chg = (acc["late"] - acc["early"]).reindex(u.index)
up, down = chg > 0, chg < 0
dd4 = pd.cut(u.days, [0, 1, 2, 3, 7], labels=["1일", "2일", "3일", "4일 이상"])
hab_m = u.seg == "습관 형성형"
D["H2"] = {"by_days": [{"days": k, "up": P(u[up & (dd4 == k)].ret1.mean()), "down": P(u[down & (dd4 == k)].ret1.mean()),
                        "up_n": int((up & (dd4 == k)).sum()), "down_n": int((down & (dd4 == k)).sum())} for k in dd4.cat.categories],
           "habit": {"up": P(u[up & hab_m].ret1.mean()), "down": P(u[down & hab_m].ret1.mean()),
                     "up_n": int((up & hab_m).sum()), "down_n": int((down & hab_m).sum())}}

# ---- 탭 4
def nxt3(d):
    l3 = d[["d0309", "d0310", "d0311"]].any(axis=1)
    return P(l3[d.d0308].mean()), P(l3[~d.d0308].mean()), int(d.d0308.sum()), int((~d.d0308).sum())
def pair(label, a, b, la, lb, detail=""):
    return {"label": label, "a_label": la, "b_label": lb, "a": P(a.ret1.mean()), "b": P(b.ret1.mean()),
            "a_n": int(len(a)), "b_n": int(len(b)), "detail": detail}
# 비교 이름(label)은 팀 밖 사람이 읽는 행동 중심 문장, 정확한 날짜 조건은 detail(화면 툴팁)에 둔다
hab = u[u.seg == "습관 형성형"]; one = u[u.seg == "최근 단발형"]; stp = u[u.seg == "멈춤-꾸준형"]
o7 = one[one.recency == 1]
h = nxt3(hab); o = nxt3(o7)
# 3/8 복귀자 중 이어서 학습(3/7 학습) vs 하루 쉬고 재개(3/6 학습)의 3/9·3/10 학습 (노션 6-3)
h8 = hab[hab.d0308]
cont, resu = h8[h8.recency == 1], h8[h8.recency == 2]
cr = lambda d: P((d.d0309 | d.d0310).mean())
D["deep"] = {
    "습관 형성형": {"target_label": "학습일 3일", "target_n": int((hab.days == 3).sum()),
               "target_sub_label": "그중 3/7 학습", "target_sub_n": int(((hab.days == 3) & (hab.recency == 1)).sum()),
               "timing": "학습한 다음 날", "metrics": ["E1", "E5"],
               "pairs": [{"label": "다음 날 다시 온 사람 vs 안 온 사람 · 그 뒤 사흘 학습", "a_label": "다음 날 옴", "b_label": "안 옴",
                          "a": h[0], "b": h[1], "a_n": h[2], "b_n": h[3], "detail": "3/8에 학습한 사람과 안 한 사람의 3/9~3/11 학습 비율"},
                         {"label": "다시 온 사람 중 바로 이어 한 사람 vs 하루 쉬고 한 사람 · 그 뒤 이틀 학습", "a_label": "바로 이어", "b_label": "하루 쉬고",
                          "a": cr(cont), "b": cr(resu), "a_n": int(len(cont)), "b_n": int(len(resu)),
                          "detail": "3/8 복귀자 중 마지막 학습이 3/7인 사람과 3/6인 사람의 3/9~3/10 학습 비율"},
                         pair("학습일 3일 vs 2일 · 후속 4일 복귀율", hab[hab.days == 3], hab[hab.days == 2], "3일", "2일", "기준 주간 학습일 수"),
                         pair("많이 푼 사람 vs 적게 푼 사람 · 후속 4일 복귀율", hab[hab.M >= 4], hab[hab.M < 4], "많이 푼", "적게 푼", "기준 주간 109문항 이상과 108문항 이하")]},
    "최근 단발형": {"target_label": "3/7 학습자", "target_n": int(len(o7)),
               "target_sub_label": "이미 하루 쉰 3/6 학습자", "target_sub_n": int((one.recency == 2).sum()),
               "timing": "학습한 다음 날", "metrics": ["E5"],
               "pairs": [pair("어제 학습한 사람 vs 그저께 학습한 사람 · 후속 4일 복귀율", o7, one[one.recency == 2], "어제", "그저께", "3/8 기준 마지막 학습이 3/7인 사람과 3/6인 사람"),
                         {"label": "어제 학습한 사람 중 다음 날 다시 온 사람 vs 안 온 사람 · 그 뒤 사흘 학습", "a_label": "다음 날 옴", "b_label": "안 옴",
                          "a": o[0], "b": o[1], "a_n": o[2], "b_n": o[3], "detail": "3/7 학습자 중 3/8에 학습한 사람과 안 한 사람의 3/9~3/11 학습 비율"},
                         pair("어제 학습한 사람 중 많이 푼 사람 vs 적게 푼 사람 · 후속 4일 복귀율", o7[o7.words >= 120], o7[o7.words < 20], "120문항+", "20문항 미만", "3/7 학습자의 첫날 푼 문항 수")]},
    "멈춤-꾸준형": {"target_label": "북극성 달성 이력", "target_n": int((stp.days >= 4).sum()),
               "target_sub_label": "그중 마지막 학습 3/5", "target_sub_n": int(((stp.days >= 4) & (stp["last"] == "2013-03-05")).sum()),
               "timing": "이틀을 쉬고 멈춤으로 바뀐 날", "metrics": ["E2"],
               "pairs": [pair("막 멈춘 사람 vs 오래 멈춘 사람 · 후속 4일 복귀율", stp[stp["last"] == "2013-03-05"], stp[stp["last"] == "2013-03-03"], "막 멈춤", "오래 멈춤", "마지막 학습이 3/5인 사람과 3/3인 사람"),
                         pair("주 4일을 채워 본 사람 vs 3일만 한 사람 · 후속 4일 복귀율", stp[stp.days >= 4], stp[stp.days == 3], "4일 이상", "3일", "기준 주간 학습일 수. 4일 이상 = 북극성 지표 달성"),
                         pair("많이 푼 사람 vs 적게 푼 사람 · 후속 4일 복귀율", stp[stp.M >= 4], stp[stp.M < 4], "많이 푼", "적게 푼", "기준 주간 109문항 이상과 108문항 이하")]},
}
lg = alld[alld.date <= "2013-03-07"].groupby("user_id").date.apply(lambda x: (x.iloc[-1] - x.iloc[-2]).days if len(x) > 1 else np.nan)
h37 = hab[hab.recency == 1]; cons = lg.reindex(h37.index) == 1
D["habit_consec"] = {"a": P(h37[cons].ret1.mean()), "b": P(h37[~cons].ret1.mean()), "a_n": int(cons.sum()), "b_n": int((~cons).sum())}

# 탭 5는 노션 5-4 "먼저 할 대상" 값(D["deep"])만 쓴다. 노션에 없는 기준일별 트리거 인원은 만들지 않는다.

# ---- 탭 5 실험 계획값: 대조군 비율별 검출 가능 최소 효과(MDE)와 +3%p 검출에 필요한 일수
# 노션에 없는 계획용 계산이다. 양측 α=0.05, 검정력 80%, 사용자 단위 무작위 배정,
# 하루 대상 수가 3/8 기준 인원과 비슷하다고 가정한다. 기준값은 개입 없이 관측된 비율이다.
from statistics import NormalDist
ZS = NormalDist().inv_cdf(0.975) + NormalDist().inv_cdf(0.80)
def mde(p, n, ctrl):
    return 100 * ZS * (p * (1 - p) * (1 / (n * (1 - ctrl)) + 1 / (n * ctrl))) ** 0.5
def days_for(p, n, d=0.03):
    per = ZS ** 2 * (p * (1 - p) + (p + d) * (1 - p - d)) / d ** 2   # 50:50일 때 군당 필요 인원
    return int(np.ceil(2 * per / n))
h3 = hab[(hab.days == 3) & (hab.recency == 1)]
p3 = stp[(stp.days >= 4) & (stp["last"] == "2013-03-05")]
plan = [("습관 형성형", "학습일 3일 · 3/7 학습", h3, "E5 다음 날 복귀", h3.d0308.mean()),
        ("최근 단발형", "3/7 학습자", o7, "E5 다음 날 복귀", o7.d0308.mean()),
        ("멈춤-꾸준형", "북극성 이력 · 마지막 3/5", p3, "E2 4일 내 복귀", p3.ret1.mean())]
D["exp_plan"] = {"alpha": 0.05, "power": 0.8, "lift": 3.0, "rows": [
    {"seg": s, "target": t, "n": int(len(v)), "metric": m, "base": P(p),
     "mde50": round(mde(p, len(v), .5), 1), "mde10": round(mde(p, len(v), .1), 1),
     "days": days_for(p, len(v))} for s, t, v, m, p in plan]}

# ---- 노션 값과 대조 (하나라도 다르면 중단)
K = D["kpi"]; S = {s["name"]: s for s in segs}
NOTION = [
    ("N1", K["N1"], 9834), ("N1%", K["N1_pct"], 11.9), ("B1", K["B1"], 82467), ("I1", K["I1"], 35.8),
    ("I2", K["I2"], 21.8), ("I2 n", K["I2_n"], 43600), ("O1", K["O1"], 35.5), ("O2", K["O2"], 16.3),
    ("O3 n", K["O3_n"], 53227), ("O3", K["O3"], 64.5), ("AC1", K["AC1"], 26.7), ("NSM ret", K["nsm_ret"], 77.8),
    ("rest ret", K["rest_ret"], 29.7), ("2+", K["two_plus"], 42.9), ("I3 (문항)", K["I3"], 47), ("I3 n", K["I3_n"], 82467),
    # 노션 4-5: "D가 3월 8일이면 운영용 값은 분석용 값과 같다" (3/9 이후 값은 노션에 없음)
    ("운영용 NSM D=3/8", (D["ops_nsm"][0]["n"], D["ops_nsm"][0]["active"]), (9834, 82467)),
    # 노션 값은 아니지만 rfm_analysis 문서의 03-05~11 NSM 주간 값(83,325명 활성·9,838명 달성)과 교차 확인
    ("운영용 NSM D=3/12 (rfm_analysis)", (D["ops_nsm"][4]["n"], D["ops_nsm"][4]["active"]), (9838, 83325)),
    ("운영용 세그먼트 D=3/8 = 분석용", D["ops_nsm"][0]["segs"], [8882, 14583, 15402, 3627, 9303, 30670]),
    ("이동표 행 합계 = 3/8 세그먼트", [r["n"] for r in D["migration"]["rows"][:6]], [8882, 14583, 15402, 3627, 9303, 30670]),
    ("실험 대상 인원 = 노션 5-4", [r["n"] for r in D["exp_plan"]["rows"]], [3538, 8444, 732]),
    ("ret by days", [r["ret"] for r in D["ret_by_days"]], [21.8, 39.0, 55.1, 69.7, 80.4, 88.3, 96.6]),
    ("seg n", [S[s]["n"] for s in SEG], [8882, 14583, 15402, 3627, 9303, 30670]),
    ("seg user%", [S[s]["user_pct"] for s in SEG], [10.8, 17.7, 18.7, 4.4, 11.3, 37.2]),
    ("seg word%", [S[s]["word_pct"] for s in SEG], [38.5, 22.0, 7.5, 8.3, 14.9, 8.8]),
    ("seg ret", [S[s]["ret"] for s in SEG], [80.3, 52.2, 32.5, 45.7, 26.4, 17.5]),
    ("nonret", [S[s]["nonret"] for s in SEG], [1747, 6975, 10396, 1969, 6847, 25293]),
    ("lost (만 문항, 노션 5-4 표기)", [round(S[s]["lost"] / 1e4) for s in SEG], [107, 148, 72, 63, 155, 101]),
    ("daily habit", S["습관 형성형"]["daily"], [28.2, 20.2, 18.3, 21.5]),
    ("daily single", S["최근 단발형"]["daily"], [17.1, 11.4, 9.7, 11.4]),
    ("daily paused", S["멈춤-꾸준형"]["daily"], [20.2, 19.8, 18.9, 19.7]),
    ("daily all", D["daily_all"], [18.0, 14.2, 13.6, 15.1]),
    ("hazard 4d", [r["within4"] for r in D["hazard"]["all"]], [59.9, 42.8, 32.6, 25.5]),
    ("hazard next", [r["next"] for r in D["hazard"]["all"]], [34.7, 19.9, 14.7, 10.1]),
    ("hazard h1", [r["within4"] for r in D["hazard"]["h1"]], [51.7, 37.2, 29.1, 22.6]),
    ("hazard h2", [r["within4"] for r in D["hazard"]["h2"]], [72.0, 55.4, 42.6, 34.9]),
    ("hazard h3", [r["within4"] for r in D["hazard"]["h3"]], [85.0, 67.9, 52.4, 42.0]),
    ("events", D["hazard"]["events"], 83079),
    ("hazard chg 4d %", [r["chg_within4"] for r in D["hazard"]["all"][1:]], [-29, -24, -22]),  # 노션 -28%는 반올림 오류(-28.54%), 10/20 노션 수정
    ("hazard chg next %", [r["chg_next"] for r in D["hazard"]["all"][1:]], [-43, -26, -31]),
    ("A1", [r["ret"] for r in D["A1"]], [24.1, 36.4, 47.9]),
    ("A1 one day", [r["ret"] for r in D["A1_one_day"]], [16.4, 25.4]),
    ("habit pairs", [(p["a"], p["b"]) for p in D["deep"]["습관 형성형"]["pairs"]], [(61.7, 33.4), (49.7, 42.0), (60.9, 46.5), (56.9, 43.9)]),
    ("single pairs", [(p["a"], p["b"]) for p in D["deep"]["최근 단발형"]["pairs"]], [(37.5, 26.4), (51.9, 20.7), (54.4, 27.8)]),
    ("paused pairs", [(p["a"], p["b"]) for p in D["deep"]["멈춤-꾸준형"]["pairs"]], [(50.4, 36.6), (54.5, 42.6), (46.5, 41.5)]),
    ("targets", [D["deep"][s][k] for s in ["습관 형성형", "최근 단발형", "멈춤-꾸준형"] for k in ("target_n", "target_sub_n")],
     [5737, 3538, 8444, 6958, 952, 732]),
    ("habit consec", (D["habit_consec"]["a"], D["habit_consec"]["b"]), (62.1, 52.7)),
    ("I1 later seg", [S[s]["i1_later"] for s in SEG], [57.8, 36.3, 29.9, 41.0, 29.8, 24.0]),
    ("I1 later all·3/8·weekend", (D["i1_later"]["all"], D["i1_later"]["d0308"], D["i1_later"]["weekend"]), (40.2, 36.9, 42.4)),
    ("H2 by days", [(r["up"], r["down"]) for r in D["H2"]["by_days"]], [(27.8, 28.6), (41.3, 40.1), (56.2, 54.1), (78.0, 77.8)]),
    ("H2 habit", (D["H2"]["habit"]["up"], D["H2"]["habit"]["down"]), (55.1, 53.6)),
    ("funnel", (D["funnel"]["one_to_two"], D["funnel"]["came_4d"], D["funnel"]["came_4d_excl"], D["funnel"]["not_4d"], D["funnel"]["cohort_n"]),
     (54.1, 61.9, 44.2, 14.7, 21738)),
    ("kmeans n", [k["n"] for k in km], [38552, 20781, 23134]),
    ("kmeans word%", [k["word_pct"] for k in km], [19.7, 10.1, 70.2]),
    ("kmeans ret", [k["ret"] for k in km], [18.9, 35.1, 63.3]),
    ("kmeans habit share C2·C3", [round(k["habit_share"]) for k in km][1:], [37, 63]),
    ("concentration", (round(D["concentration"]["user_pct"]), round(D["concentration"]["word_pct"])), (40, 75)),
    ("segment ret2 (노션 외, 이전 산출값)", [S[s]["ret2"] for s in SEG], [55.9, 24.4, 12.1, 22.3, 9.0, 4.7]),
]
bad = [(k, got, exp) for k, got, exp in NOTION if (list(got) if isinstance(got, (list, tuple)) else got) != (list(exp) if isinstance(exp, (list, tuple)) else exp)]
for k, got, exp in NOTION:
    print(("OK  " if (k, got, exp) not in bad else "FAIL"), k, got)
if bad:
    sys.exit("노션 값과 불일치: " + repr(bad))
D["checks"] = len(NOTION)
# 버전 표시: 대조 기준으로 삼은 노션 분석 확정본의 마지막 수정일. 노션을 다시 대조해 값을 바꾸면 함께 고친다
D["meta"]["notion_edited"] = "2026-10-20"
D["meta"]["built"] = pd.Timestamp.now(tz="Asia/Seoul").strftime("%Y-%m-%d %H:%M KST")
json.dump(D, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", OUT, "checks", len(NOTION))

# ---- 템플릿에 데이터를 넣어 HTML 생성 (<script> 안이므로 "</"를 이스케이프)
tpl = open(TEMPLATE, encoding="utf-8").read()
assert tpl.count("__DATA__") == 1, "템플릿의 __DATA__ 자리가 하나가 아님"
blob = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(HTML, "w", encoding="utf-8").write(tpl.replace("__DATA__", blob))
print("saved", HTML)
