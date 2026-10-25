import pandas as pd
import numpy as np
pd.set_option("display.max_columns", None)

from pathlib import Path
path = Path(__file__).resolve().parent / "learning_traces.13m.csv" / "learning_traces.13m.csv"

# 분석 설정 (NSM 정의: 7일이 온전히 포함된 첫 주 = 3/1~3/7)
OBS_START = "2013-03-01"   # 관측 시작일 (포함)
OBS_END = "2013-03-08"     # 관측 종료일의 다음 날 (미포함) = RFM 기준일
DATA_START = "2013-03-01"  # 하루가 온전한 데이터 구간 (포함)
DATA_END = "2013-03-12"    # 하루가 온전한 데이터 구간 끝 (미포함)

# 세그먼트 6개 (기존 초반 이탈 + 중반 이탈 → "멈춤-저활동형"으로 합침)
# 이름 체계: 위 3개 = 최근 활동 중(R≥4), 아래 3개 = 최근 이틀 미학습(R≤3, "멈춤-")
#   기존 이름 → 새 이름
#   핵심 학습자 → 꾸준형 / 습관 형성 중 → 습관 형성형 / 최근 1일 학습 → 최근 단발형
#   중단 위험 → 멈춤-꾸준형 / 몰입 후 이탈 → 멈춤-몰입형
#   초반 이탈 + 중반 이탈 → 멈춤-저활동형
# 이름을 바꾸려면 여기만 고치면 됨
SEG_ORDER = ["꾸준형", "습관 형성형", "최근 단발형",
             "멈춤-꾸준형", "멈춤-몰입형", "멈춤-저활동형"]

# 1. 불러오기: 12개 열 전부 (문자열 열은 category로 메모리 절약)
df = pd.read_csv(path, dtype={"user_id": "category", "learning_language": "category", "ui_language": "category",
    "lexeme_id": "category", "lexeme_string": "category",})

# 2. EDA: 중복 제거 (12개 열이 전부 같은 행, 첫 행만 남김)
before = len(df)
df = df.drop_duplicates()
print(before - len(df), "행 제거")   # 81행이 나옴

# 2-1. 결측·범위 점검 (전부 0이어야 정상). 아래에서 열을 줄이기 전에 확인
print(df.isna().any(axis=1).sum(), "행: 결측값 있음")
print((df["delta"] < 0).sum(), "행: delta가 음수")
print((~df["p_recall"].between(0, 1)).sum(), "행: p_recall이 0~1 밖")

# 분석에 쓰는 열만 남기기
df = df[["user_id", "timestamp", "learning_language",
         "lexeme_id", "session_seen", "session_correct"]]

# 3. 시간 변환 + 하루가 온전한 기간(3/1~3/11)만 남기기
#    (3/8~3/11은 나중에 세그먼트 검증용으로 보관)
df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
df = df[(df["dt"] >= DATA_START) & (df["dt"] < DATA_END)].copy()
df["date"] = df["dt"].dt.normalize()
print(df["dt"].min(), "~", df["dt"].max())
print(df["user_id"].nunique(), "명 (3/1~3/11 전체)")   # 109504명

# 4. 논리 오류 점검 (둘 다 0이어야 정상)
print((df["session_correct"] > df["session_seen"]).sum(), "행: 정답 수가 출제 수보다 큼")
print((df["session_seen"] <= 0).sum(), "행: 출제 수가 0 이하")

# 5. 관측 기간(3/1~3/7)만 잘라서 유저별 집계
obs = df[(df["dt"] >= OBS_START) & (df["dt"] < OBS_END)]

user = obs.groupby("user_id", observed=True).agg(
    first_active=("date", "min"),               # 관측 주 첫 학습일 (코호트용)
    last_active=("date", "max"),                # R의 재료
    active_days=("date", "nunique"),            # F: 학습한 날짜 수
    words_seen=("session_seen", "sum"),         # M: 학습 문항 수 (팀 정의)
    words_correct=("session_correct", "sum"),   # 정답률 계산용
    sessions=("timestamp", "nunique"),          # 군집 분석용 (세션 = 유저+timestamp 추정)
)

# R: 기준일(3/8) - 마지막 학습일  -> 3/7에 학습했으면 1, 3/1이면 7
user["recency"] = (pd.Timestamp(OBS_END) - user["last_active"]).dt.days

# 파생 지표 (군집 분석 등에서 사용)
user["accuracy"] = user["words_correct"] / user["words_seen"]
user["per_day"] = user["words_seen"] / user["active_days"]            # 활동일당 문항 수
user["sessions_per_day"] = user["sessions"] / user["active_days"]     # 활동일당 세션 수

# 6. 확인
print("\n관측 기간 유저 수:", len(user), "명")
print("recency 범위:", user["recency"].min(), "~", user["recency"].max())   # 1~7이어야 정상
print(user.head())

print("\n[active_days 분포]")
print(user["active_days"].value_counts().sort_index())

# NSM: 7일 중 4일 이상 학습한 유저 수 (팀 정의)
nsm = (user["active_days"] >= 4).sum()
print(f"\nNSM 지속 학습 사용자: {nsm}명 ({nsm / len(user):.1%})")

print("\n[요약 통계]")
print(user[["recency", "active_days", "words_seen", "accuracy", "per_day"]]
      .describe(percentiles=[.5, .9, .99, .999]))

print("\n[words_seen 상위 10명]")
print(user.sort_values("words_seen", ascending=False).head(10))

# F 점수: 구간을 직접 지정 (4일 = 팀 NSM 경계)
user["F"] = pd.cut(user["active_days"], bins=[0, 1, 2, 3, 4, 7],
                   labels=[1, 2, 3, 4, 5]).astype(int)
print(user["F"].value_counts().sort_index())

# M 점수: 5분위 (문항 수가 많을수록 5점)
# [수정] rank(method="first")를 빼서 같은 문항 수는 같은 점수를 받도록 함.
#        경계값과 같은 유저는 아래 구간에 포함 (예: 경계가 108이면 108문항은 3점)
#        → 점수별 인원이 정확히 20%씩은 아님
user["M"], m_edges = pd.qcut(user["words_seen"], 5, labels=[1, 2, 3, 4, 5], retbins=True)
user["M"] = user["M"].astype(int)
print("\nM 경계값:", m_edges)
print(user.groupby("M")["words_seen"].agg(["min", "max", "count"]))

# R: 점수를 매기기 전에 분포부터 확인
print(user["recency"].value_counts().sort_index())

# R 점수
user["R"] = pd.cut(user["recency"], bins=[0, 1, 2, 4, 6, 7],
                   labels=[5, 4, 3, 2, 1]).astype(int)
print(user["R"].value_counts().sort_index())

# 맨 마지막
print(pd.crosstab(user["R"], user["F"]))

# 세그먼트 규칙 (위에서부터 순서대로 적용, 처음 충족한 그룹에 배정)
#   순서를 반영한 실제 조건
#   1 꾸준형         : R≥4 & F≥4
#   2 습관 형성형    : R≥4 & F 2~3
#   3 최근 단발형    : R≥4 & F=1
#   4 멈춤-꾸준형    : R 2~3 & F≥3   (R=1은 학습일이 1일뿐이라 해당 없음)
#   5 멈춤-몰입형    : R≤3 & F≤2 & M≥4 (109문항 이상)
#   6 멈춤-저활동형  : R≤3 & F≤2 & M≤3 (나머지 전부)
conditions = [
    (user["R"] >= 4) & (user["F"] >= 4),                       # 1
    (user["R"] >= 4) & (user["F"].isin([2, 3])),               # 2
    (user["R"] >= 4) & (user["F"] == 1),                       # 3
    (user["R"] <= 3) & (user["F"] >= 3),                       # 4
    (user["R"] <= 3) & (user["M"] >= 4),                       # 5
]
# [수정] 기존 6번 규칙(R == 1, 초반 이탈)을 지우고, 나머지를 모두 하나의 그룹으로 받음
#        초반/중반 이탈은 마지막 학습일만 다르고 액션이 같으며,
#        관측 기간이 짧아 복귀율 차이를 성향 차이와 경과 시간 차이로 분리할 수 없어서 합침
labels = SEG_ORDER[:5]
user["segment"] = np.select(conditions, labels, default=SEG_ORDER[5])

# 규칙 점검 1: 모든 유저가 6개 중 하나에 배정됐는지
assert user["segment"].isin(SEG_ORDER).all()
# 규칙 점검 2: 나머지 그룹(default)에 의도한 조합만 들어갔는지
#              R 1~3점, F 1~2점, M 1~3점 조합만 나와야 정상
print(f"\n[{SEG_ORDER[5]}에 들어간 점수 조합]")
print(user.loc[user["segment"] == SEG_ORDER[5], ["R", "F", "M"]].value_counts().sort_index())

print(user["segment"].value_counts().reindex(SEG_ORDER))
print((user["segment"].value_counts(normalize=True) * 100).round(1).reindex(SEG_ORDER))

# 1) 세그먼트별 평균 프로필
profile = user.groupby("segment").agg(
    users=("R", "size"),
    recency=("recency", "mean"),
    active_days=("active_days", "mean"),
    words_seen=("words_seen", "median"),
    accuracy=("accuracy", "mean"),
).round(2).reindex(SEG_ORDER)
print(profile)

# 2) 관측 이후(3/8~3/11)에 다시 학습했는지
later = df[df["dt"] >= OBS_END]
user["returned"] = user.index.isin(later["user_id"].unique())
print(user.groupby("segment")["returned"].mean().round(3).reindex(SEG_ORDER))
# -> 활동이 많은 세그먼트일수록 복귀율이 높음. 세그먼트 규칙이 이후 행동을 어느 정도 구분한다고 볼 수 있음
#    (단, 세그먼트가 학습 활동으로 정의되어 있으므로 개입 효과가 아니라 분류의 타당성 확인임)

print("\n[활동일 수별 복귀율]")
print(user.groupby("active_days")["returned"].mean().round(3))

# 3) 세그먼트 요약표 (보고서 요약표 열 전부)
summary = user.groupby("segment").agg(
    users=("R", "size"),
    words_seen=("words_seen", "sum"),
    returned=("returned", "mean"),
).reindex(SEG_ORDER)
summary["고객 비중(%)"] = (summary["users"] / summary["users"].sum() * 100).round(1)
summary["학습량 비중(%)"] = (summary["words_seen"] / summary["words_seen"].sum() * 100).round(1)
summary["인당 문항 수"] = (summary["words_seen"] / summary["users"]).round(0)
summary["집중도"] = (summary["학습량 비중(%)"] / summary["고객 비중(%)"]).round(2)
summary["4일 복귀율(%)"] = (summary["returned"] * 100).round(1)
summary = summary.drop(columns="returned")
print(summary)

# 합계 점검: 세그먼트별 인원·학습량을 더하면 전체와 같아야 함
assert summary["users"].sum() == len(user)
assert summary["words_seen"].sum() == user["words_seen"].sum()
print("합계 점검 통과: 인원", summary["users"].sum(), "/ 학습량", summary["words_seen"].sum())

# 세그먼트 결과 저장 (아래 가설 검증 코드가 이 파일을 읽음)
user[["segment"]].to_csv("user_rfm.csv", encoding="utf-8-sig")
print("user_rfm.csv 저장 완료")

# =====================================================================
# 아래부터: Input Metrics 산출 + 세그먼트 안에서 가설 검증 (코호트)
# =====================================================================
"""
Input Metrics 3개 산출 + 세그먼트별 가설 검증 (코호트 결과 지표)

(이 파일 하나로 실행: 위 세그먼트 부분이 user_rfm.csv를 만들고, 아래 부분이 그 파일을 읽음)
결과 파일:
  im_overall_by_segment.csv  : Input Metrics 현재 값 (전체 + 세그먼트별)
  h1_by_segment.csv          : 가설 1 - 세그먼트 안에서 규칙적 vs 불규칙, 후속 재학습률
  h1_by_segment_days.csv     : 가설 1 점검 - 학습일 수까지 같은 사람끼리
  h2_by_segment.csv          : 가설 2 - 세그먼트 안에서 정답률 상승/동일/하락, 후속 재학습률
  h3_by_segment.csv          : 가설 3 - 세그먼트 안에서 복습 간격(7일 이내/초과)별 정답률
"""
import pandas as pd
import numpy as np
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 200)

from pathlib import Path
path = Path(__file__).resolve().parent / "learning_traces.13m.csv" / "learning_traces.13m.csv"
SEG_FILE = "user_rfm.csv"

# =====================================================================
# 0. 설정 (지표 정의서와 같은 기준)
# =====================================================================
OBS_START = "2013-03-01"   # 기준 주간 시작 (포함)
OBS_END = "2013-03-08"     # 기준 주간 끝 다음 날 (미포함) = 후속 관측 시작
DATA_END = "2013-03-12"    # 후속 관측 끝 다음 날 (미포함)
SEG_ORDER = ["꾸준형", "습관 형성형", "최근 단발형", "멈춤-꾸준형", "멈춤-몰입형", "멈춤-저활동형"]

REG_CV = 0.5               # 가설 1: 학습일 간격 변동계수 0.5 이하 = 규칙적
REVIEW_DAYS = 7            # 가설 3: delta 7일 이하 = 7일 이내 복습
MIN_N = 300                # 인원(또는 행 수)이 이보다 적은 칸은 해석하지 않음

# =====================================================================
# 1. 불러오기 + 전처리 (세그먼트·코호트·가설 검증과 동일)
# =====================================================================
df = pd.read_csv(path, dtype={"user_id": "category", "learning_language": "category", "ui_language": "category",
    "lexeme_id": "category", "lexeme_string": "category"})
before = len(df)
df = df.drop_duplicates()
print(before - len(df), "행 제거")   # 81행

df = df[["user_id", "timestamp", "delta", "session_seen", "session_correct"]]
df["dt"] = pd.to_datetime(df["timestamp"], unit="s")
df = df[(df["dt"] >= OBS_START) & (df["dt"] < DATA_END)].copy()
df["date"] = df["dt"].dt.normalize()
df["user_id"] = df["user_id"].astype(str)

obs = df[df["dt"] < OBS_END]       # 기준 주간
later = df[df["dt"] >= OBS_END]    # 후속 관측

# =====================================================================
# 2. 사용자 표 + 결과 지표 + 세그먼트 붙이기
# =====================================================================
user = obs.groupby("user_id").agg(active_days=("date", "nunique"))
ret_days = later.groupby("user_id")["date"].nunique()
user["ret_days"] = ret_days.reindex(user.index).fillna(0).astype(int)
user["ret1"] = user["ret_days"] >= 1
user["ret2"] = user["ret_days"] >= 2

seg = pd.read_csv(SEG_FILE, usecols=["user_id", "segment"], dtype=str).set_index("user_id")["segment"]
user["segment"] = seg.reindex(user.index)
assert user["segment"].notna().all(), "세그먼트가 없는 사용자가 있음: user_rfm.csv를 다시 만들어 주세요"
user["segment"] = pd.Categorical(user["segment"], SEG_ORDER, ordered=True)

print("\n대상 사용자:", len(user), "명")   # 82,467명
print(user["segment"].value_counts().reindex(SEG_ORDER))
print(f"후속 1일 이상 재학습률 {user.ret1.mean():.1%}, 2일 이상 {user.ret2.mean():.1%}")   # 35.5%, 16.3%

# =====================================================================
# 3. Input Metric 재료 계산
# =====================================================================
# 3-1. 가설 1: 학습일 간격 변동계수 (학습일 3일 이상만 계산 가능)
days = obs[["user_id", "date"]].drop_duplicates().sort_values(["user_id", "date"])
days["gap"] = days.groupby("user_id")["date"].diff().dt.days
g = days.dropna(subset=["gap"]).groupby("user_id")["gap"]
cv = g.std(ddof=0) / g.mean()
user["cv"] = cv.reindex(user.index)
user.loc[user["active_days"] < 3, "cv"] = np.nan          # 간격이 2개 이상일 때만 의미 있음
user["regular"] = np.where(user["cv"].isna(), np.nan, (user["cv"] <= REG_CV).astype(float))

# 3-2. 가설 2: 정답률 변화 (세션 3개 이상만)
ses = (obs.groupby(["user_id", "timestamp"])
          .agg(seen=("session_seen", "sum"), correct=("session_correct", "sum"))
          .reset_index()
          .sort_values(["user_id", "timestamp"]))
ses["n"] = ses.groupby("user_id")["timestamp"].transform("size")
ses = ses[ses["n"] >= 3].copy()
ses["rank"] = ses.groupby("user_id").cumcount()
half = ses["n"] // 2
ses["part"] = np.where(ses["rank"] < half, "early",
                       np.where(ses["rank"] >= ses["n"] - half, "late", "mid"))
pa = ses[ses["part"] != "mid"].groupby(["user_id", "part"])[["seen", "correct"]].sum()
acc = (pa["correct"] / pa["seen"]).unstack("part")
change = acc["late"] - acc["early"]
user["acc_change"] = change.reindex(user.index)
user["acc_group"] = pd.Categorical(
    np.select([user["acc_change"] > 0, user["acc_change"] < 0, user["acc_change"] == 0],
              ["상승", "하락", "동일"], default=None),
    ["상승", "동일", "하락"], ordered=True)
user["acc_up"] = np.where(user["acc_change"].isna(), np.nan, (user["acc_change"] > 0).astype(float))

# 3-3. 가설 3: 7일 이내 복습 (학습 기록 단위)
rows = obs[["user_id", "delta", "session_seen", "session_correct"]].copy()
rows["within7"] = rows["delta"] <= REVIEW_DAYS * 86400
rows["segment"] = pd.Categorical(user["segment"].astype(str).reindex(rows["user_id"]).values,
                                 SEG_ORDER, ordered=True)

# =====================================================================
# 4. Input Metrics 현재 값 (전체 + 세그먼트별)
# =====================================================================
def im_table(u, r):
    return pd.Series({
        "사용자 수": len(u),
        "규칙적 학습자 비율(%)": round(u["regular"].mean() * 100, 1),
        "  └ 대상(학습일 3일 이상)": int(u["regular"].notna().sum()),
        "정답률 상승 사용자 비율(%)": round(u["acc_up"].mean() * 100, 1),
        "  └ 대상(세션 3개 이상)": int(u["acc_up"].notna().sum()),
        "7일 이내 복습 비율(%)": round(r["within7"].mean() * 100, 1),
        "  └ 대상(학습 기록 행 수)": len(r),
    })

im = pd.DataFrame({s: im_table(user[user["segment"] == s], rows[rows["segment"] == s]) for s in SEG_ORDER})
im["전체"] = im_table(user, rows)
print("\n" + "=" * 70)
print("Input Metrics 현재 값 (전체 + 세그먼트별)")
print("=" * 70)
print(im.T.to_string())

# =====================================================================
# 5. 세그먼트 안에서 가설 검증 (결과 = 후속 4일 재학습률)
# =====================================================================
def rates(d, by):
    t = d.groupby(by, observed=True).agg(인원=("ret1", "size"), r1=("ret1", "mean"), r2=("ret2", "mean"))
    t["1일 이상(%)"] = (t["r1"] * 100).round(1)
    t["2일 이상(%)"] = (t["r2"] * 100).round(1)
    t["해석"] = np.where(t["인원"] >= MIN_N, "O", f"X ({MIN_N}명 미만)")
    return t.drop(columns=["r1", "r2"])

# 5-1. 가설 1: 학습일 3~6일 사용자만 (7일 학습자는 항상 규칙적이라 비교 불가)
h1 = user[user["active_days"].between(3, 6)].copy()
h1["규칙성"] = pd.Categorical(np.where(h1["regular"] == 1, "규칙적", "불규칙"), ["규칙적", "불규칙"], ordered=True)
h1_seg = rates(h1, ["segment", "규칙성"])
h1_days = rates(h1, ["segment", "active_days", "규칙성"])
print("\n" + "=" * 70)
print("가설 1. 규칙성 → 리텐션 (세그먼트 안에서, 학습일 3~6일)")
print("=" * 70)
print(h1_seg.to_string())
print("\n[점검: 같은 세그먼트 + 같은 학습일 수끼리]")
print(h1_days.to_string())

# 5-2. 가설 2: 세션 3개 이상 사용자
h2 = user[user["acc_group"].notna()]
h2_seg = rates(h2, ["segment", "acc_group"])
print("\n" + "=" * 70)
print("가설 2. 정답률 변화 → 리텐션 (세그먼트 안에서, 세션 3개 이상)")
print("=" * 70)
print(h2_seg.to_string())

# =====================================================================
# 6. 세그먼트 안에서 가설 3 (결과 = 정답률)
# =====================================================================
rows["간격"] = pd.Categorical(np.where(rows["within7"], "7일 이내", "7일 초과"), ["7일 이내", "7일 초과"], ordered=True)
a = rows.groupby(["segment", "간격"], observed=True).agg(
    행수=("session_seen", "size"), seen=("session_seen", "sum"), correct=("session_correct", "sum"))
a["정답률(%)"] = (a["correct"] / a["seen"] * 100).round(1)
a["해석"] = np.where(a["행수"] >= MIN_N, "O", f"X ({MIN_N}행 미만)")
h3_seg = a.drop(columns=["seen", "correct"])
print("\n" + "=" * 70)
print("가설 3. 복습 간격 → 학습 성과 (세그먼트 안에서)")
print("=" * 70)
print(h3_seg.to_string())

# =====================================================================
# 7. 저장
# =====================================================================
im.T.to_csv("im_overall_by_segment.csv", encoding="utf-8-sig")
h1_seg.to_csv("h1_by_segment.csv", encoding="utf-8-sig")
h1_days.to_csv("h1_by_segment_days.csv", encoding="utf-8-sig")
h2_seg.to_csv("h2_by_segment.csv", encoding="utf-8-sig")
h3_seg.to_csv("h3_by_segment.csv", encoding="utf-8-sig")
print("\n저장 완료")