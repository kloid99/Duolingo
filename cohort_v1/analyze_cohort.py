"""Reproduce Yeojin's PDF segmentation and add the four-day activity cohort.

Run with bundled Python: python analyze_cohort.py
No future data are used to assign R, F, M or segment. Original files are read-only.
"""
from pathlib import Path
import hashlib
import json
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT.parent / 'learning_traces.13m.csv' / 'learning_traces.13m.csv'
REFERENCE = ROOT.parent / '세그먼트 분석' / '세그먼트1.pdf'
COLS = ['p_recall','timestamp','delta','user_id','learning_language','ui_language',
        'lexeme_id','lexeme_string','history_seen','history_correct','session_seen','session_correct']
DTYPES = {c:'int64' for c in ['timestamp','delta','history_seen','history_correct','session_seen','session_correct']}
DTYPES.update({c:'object' for c in ['user_id','learning_language','ui_language','lexeme_id','lexeme_string']})
DTYPES['p_recall'] = 'float64'
SEGMENTS = ['핵심 학습자','습관 형성 중','최근 1일 학습','중단 위험','몰입 후 이탈','초반 이탈','중반 이탈']
EXPECTED_COUNTS = [8882,14583,15402,3627,9359,6350,24264]
EXPECTED_RETURN_PCT = [80.3,52.2,32.5,45.7,26.3,13.6,18.6]

def epoch(s):
    return int(pd.Timestamp(s, tz='UTC').timestamp())

START, CUTOFF, END = map(epoch, ['2013-03-01','2013-03-08','2013-03-12'])
DATES = pd.date_range('2013-03-08', periods=4, tz='UTC')

def sha256(p):
    with p.open('rb') as f:
        return hashlib.file_digest(f,'sha256').hexdigest()

def aggregate_source():
    # Global row hashes locate duplicate candidates, verified using all 12 values.
    # Chunk aggregation avoids loading the 1.3 GB CSV as a single DataFrame.
    chunks, hashes, raw_users = [], [], set()
    raw_rows = missing = invalid = 0
    min_ts, max_ts = None, None
    started = time.time()
    for i,c in enumerate(pd.read_csv(SOURCE, dtype=DTYPES, chunksize=250_000)):
        missing += int(c.isna().any(axis=1).sum())
        bad = ((c.session_seen <= 0) | (c.session_correct < 0) |
               (c.session_correct > c.session_seen) | (c.delta < 0) |
               (~c.p_recall.between(0,1)))
        invalid += int(bad.sum())
        hashes.append(pd.util.hash_pandas_object(c[COLS],index=False).to_numpy())
        raw_rows += len(c)
        raw_users.update(c.user_id.unique())
        mn,mx=int(c.timestamp.min()),int(c.timestamp.max())
        min_ts=mn if min_ts is None else min(min_ts,mn)
        max_ts=mx if max_ts is None else max(max_ts,mx)
        w=c[(c.timestamp>=START)&(c.timestamp<END)]
        chunks.append(w.groupby(['user_id','timestamp'],sort=False).agg(
            exposures=('session_seen','sum'),correct=('session_correct','sum'),
            trace_rows=('session_seen','size')))
        if (i+1)%8==0:
            print(f'Read {raw_rows:,} rows ({time.time()-started:.1f}s)',flush=True)
    assert missing==0 and invalid==0,(missing,invalid)
    h=np.concatenate(hashes)
    order=np.argsort(h,kind='stable')
    same=h[order[1:]]==h[order[:-1]]
    candidates=np.unique(np.r_[order[:-1][same],order[1:][same]])
    candidate_rows=[]
    offset=0
    for c in pd.read_csv(SOURCE,dtype=DTYPES,chunksize=250_000):
        ids=candidates[(candidates>=offset)&(candidates<offset+len(c))]
        if len(ids):
            part=c.iloc[ids-offset].copy();part.index=ids
            candidate_rows.append(part)
        offset+=len(c)
    duplicates=pd.DataFrame(columns=COLS)
    if candidate_rows:
        cand=pd.concat(candidate_rows).sort_index()
        duplicates=cand[cand.duplicated(COLS,keep='first')]
    sessions=pd.concat(chunks).groupby(level=[0,1],sort=False).sum()
    d=duplicates[(duplicates.timestamp>=START)&(duplicates.timestamp<END)]
    if len(d):
        adj=d.groupby(['user_id','timestamp']).agg(exposures=('session_seen','sum'),
            correct=('session_correct','sum'),trace_rows=('session_seen','size'))
        sessions.loc[adj.index]-=adj
    sessions=sessions.reset_index().sort_values(['user_id','timestamp'])
    assert (sessions.exposures>0).all()
    sessions['day_number']=sessions.timestamp//86400
    quality={'source':str(SOURCE),'raw_rows':raw_rows,
        'exact_duplicates_removed':len(duplicates),'clean_rows':raw_rows-len(duplicates),
        'duplicates_removed_in_analysis_window':len(d),
        'missing_rows':missing,'invalid_rows':invalid,'raw_unique_users':len(raw_users),
        'raw_min_utc':str(pd.to_datetime(min_ts,unit='s',utc=True)),
        'raw_max_utc':str(pd.to_datetime(max_ts,unit='s',utc=True)),
        'complete_window_users':int(sessions.user_id.nunique()),
        'complete_window_trace_rows':int(sessions.trace_rows.sum()),
        'source_sha256':sha256(SOURCE),'reference_sha256':sha256(REFERENCE),
        'source_bytes':SOURCE.stat().st_size,
        'pandas_version':pd.__version__,'numpy_version':np.__version__}
    return sessions,quality

def main():
    cache=ROOT/'tmp'
    cache.mkdir(exist_ok=True)
    stat=SOURCE.stat()
    signature={'size':stat.st_size,'mtime_ns':stat.st_mtime_ns}
    cache_meta=cache/'source_quality.json'
    if cache_meta.exists() and (cache/'sessions.pkl').exists():
        saved=json.loads(cache_meta.read_text(encoding='utf-8'))
        assert saved['signature']==signature,'Source changed; move the tmp cache before rerunning.'
        assert sha256(SOURCE)==saved['quality']['source_sha256'],'Source hash differs from cache.'
        quality=saved['quality'];s=pd.read_pickle(cache/'sessions.pkl')
    else:
        s,quality=aggregate_source()
        s.to_pickle(cache/'sessions.pkl')
        cache_meta.write_text(json.dumps({'signature':signature,'quality':quality},ensure_ascii=False,indent=2),encoding='utf-8')
    b=s[s.timestamp<CUTOFF].copy()
    u=b.groupby('user_id',sort=True).agg(last_day_number=('day_number','max'),
        first_day_number=('day_number','min'),active_days=('day_number','nunique'),
        words_seen=('exposures','sum'),words_correct=('correct','sum'),
        sessions=('timestamp','size'))
    # The PDF reads user_id as category. pandas' low_memory CSV reader retains
    # a category union order across parser blocks; this need not be lexical.
    # Preserve that order before rank(method='first') to reproduce M ties.
    order_path=cache/'user_category_order.json'
    if order_path.exists():
        category_order=json.loads(order_path.read_text(encoding='utf-8'))
    else:
        ids=pd.read_csv(SOURCE,usecols=['user_id'],dtype={'user_id':'category'})
        category_order=ids.user_id.cat.categories.tolist()
        order_path.write_text(json.dumps(category_order),encoding='utf-8')
    assert set(category_order).issuperset(u.index)
    u=u.reindex([x for x in category_order if x in u.index])
    u['last_active']=pd.to_datetime(u.last_day_number,unit='D',utc=True).dt.strftime('%Y-%m-%d')
    u['first_observed_in_baseline']=pd.to_datetime(u.first_day_number,unit='D',utc=True).dt.strftime('%Y-%m-%d')
    u['recency']=CUTOFF//86400-u.last_day_number
    u['accuracy']=u.words_correct/u.words_seen
    u['per_day']=u.words_seen/u.active_days
    u['sessions_per_day']=u.sessions/u.active_days
    # Exact PDF scoring, including tie-breaking by source category order.
    u['F']=pd.cut(u.active_days,bins=[0,1,2,3,4,7],labels=[1,2,3,4,5]).astype(int)
    u['M']=pd.qcut(u.words_seen.rank(method='first'),5,labels=[1,2,3,4,5]).astype(int)
    u['R']=pd.cut(u.recency,bins=[0,1,2,4,6,7],labels=[5,4,3,2,1]).astype(int)
    cond=[(u.R>=4)&(u.F>=4),(u.R>=4)&u.F.isin([2,3]),(u.R>=4)&(u.F==1),
          (u.R<=3)&(u.F>=3),(u.R<=3)&(u.M>=4),(u.R==1)]
    u['segment']=np.select(cond,SEGMENTS[:6],default=SEGMENTS[6])
    u['segment_asof_utc']='2013-03-08T00:00:00Z'
    u['baseline_sustained']=u.active_days>=4
    u=u.drop(columns=['first_day_number','last_day_number'])

    future=s[(s.timestamp>=CUTOFF)&(s.timestamp<END)]
    future_only=set(future.user_id)-set(u.index)
    future_baseline=future[future.user_id.isin(u.index)]
    activity=future_baseline.groupby(['user_id','day_number']).agg(
        sessions=('timestamp','size'),exposures=('exposures','sum'),correct=('correct','sum'))
    idx=pd.MultiIndex.from_product([u.index,[int(d.timestamp())//86400 for d in DATES]],
                                  names=['user_id','day_number'])
    day=activity.reindex(idx,fill_value=0).reset_index()
    day['date']=pd.to_datetime(day.day_number,unit='D',utc=True).dt.strftime('%Y-%m-%d')
    day['active']=(day.sessions>0).astype('int8')
    day['segment']=day.user_id.map(u.segment)
    day['segment_asof_utc']='2013-03-08T00:00:00Z'
    day['followup_day']=day.day_number-CUTOFF//86400+1
    day=day[['user_id','segment','segment_asof_utc','date','followup_day','active',
             'sessions','exposures','correct']]
    wide=day.pivot(index='user_id',columns='date',values='active').reindex(u.index)
    wide.columns=['active_'+c for c in wide.columns]
    u=u.join(wide)
    u['followup_active_days']=wide.sum(axis=1).astype(int)
    u['returned_4d']=(u.followup_active_days>=1).astype(int)
    u['returned_2plus_days']=(u.followup_active_days>=2).astype(int)

    records=[]
    for seg in SEGMENTS:
        g=u[u.segment==seg];n=len(g)
        r={'segment':seg,'users':n,'user_share':n/len(u),
           'returned_4d_users':int(g.returned_4d.sum()),'return_4d_rate':float(g.returned_4d.mean()),
           'returned_2plus_days_users':int(g.returned_2plus_days.sum()),
           'return_2plus_days_rate':float(g.returned_2plus_days.mean()),
           'followup_active_days_sum':int(g.followup_active_days.sum()),
           'mean_followup_active_days':float(g.followup_active_days.mean())}
        for date in [d.strftime('%Y-%m-%d') for d in DATES]:
            r['active_users_'+date]=int(g['active_'+date].sum())
            r['activity_rate_'+date]=float(g['active_'+date].mean())
        for k in range(5):r[f'users_active_{k}_days']=int((g.followup_active_days==k).sum())
        records.append(r)
    summary=pd.DataFrame(records)
    daily=day.groupby(['segment','date'],sort=False).agg(
        cohort_users=('user_id','size'),active_users=('active','sum')).reset_index()
    daily['activity_rate']=daily.active_users/daily.cohort_users
    daily['_order']=daily.segment.map({v:i for i,v in enumerate(SEGMENTS)})
    daily=daily.sort_values(['_order','date']).drop(columns='_order')
    reproduction=pd.DataFrame({'segment':SEGMENTS,'pdf_users':EXPECTED_COUNTS,
        'actual_users':summary.users,'pdf_return_pct':EXPECTED_RETURN_PCT,
        'actual_return_pct':summary.return_4d_rate*100})
    reproduction['count_matches']=reproduction.pdf_users==reproduction.actual_users
    reproduction['return_matches_at_1dp']=(reproduction.actual_return_pct.round(1)==reproduction.pdf_return_pct)

    # Meaningful checks: source totals, published reference, zero-filling and joins.
    checks={
        'raw_rows_match_reference':quality['raw_rows']==12854226,
        'exact_duplicates_match_reference':quality['exact_duplicates_removed']==81,
        'baseline_users_match_reference':len(u)==82467,
        'complete_window_users_match_reference':quality['complete_window_users']==109504,
        'baseline_nsm_match_reference':int(u.baseline_sustained.sum())==9834,
        'baseline_activity_days_distribution_match':bool(
            u.active_days.value_counts().reindex([1,2,3,4]).tolist()==[47087,17134,8412,4748]
            and (u.active_days>=5).sum()==5086 and (u.active_days>=6).sum()==2363),
        'recency_range_is_1_to_7':int(u.recency.min())==1 and int(u.recency.max())==7,
        'all_segment_counts_match_pdf':bool(reproduction.count_matches.all()),
        'all_return_rates_match_pdf_at_1dp':bool(reproduction.return_matches_at_1dp.all()),
        'user_ids_unique':bool(u.index.is_unique),
        'one_segment_per_baseline_user':bool(u.segment.notna().all() and u.segment.isin(SEGMENTS).all()),
        'four_rows_per_baseline_user':bool(len(day)==4*len(u) and day.groupby('user_id').size().eq(4).all()),
        'user_date_pairs_unique':not day.duplicated(['user_id','date']).any(),
        'daily_activity_is_binary':bool(day.active.isin([0,1]).all()),
        'all_segment_denominators_fixed':bool(daily.cohort_users.eq(daily.segment.map(summary.set_index('segment').users)).all()),
        'segment_users_reconcile':int(summary.users.sum())==len(u),
        'active_days_reconcile':int(summary.followup_active_days_sum.sum())==int(day.active.sum()),
        'direct_future_return_ids_match':bool(u.returned_4d.astype(bool).eq(u.index.isin(future_baseline.user_id.unique())).all()),
        'no_followup_only_users_in_cohort':not bool(set(day.user_id)&future_only),
        'future_exposures_reconcile':int(day.exposures.sum())==int(future_baseline.exposures.sum()),
        'zero_filled_users_preserved':int((u.followup_active_days==0).sum())==len(u)-int(u.returned_4d.sum()),
        'followup_day_range_1_to_4':int(day.followup_day.min())==1 and int(day.followup_day.max())==4,
    }
    print(reproduction.to_string(index=False),flush=True)
    assert all(checks.values()),{k:v for k,v in checks.items() if not v}

    outputs={'user_cohort.csv':u.reset_index(),'user_daily_activity.csv':day,
        'segment_cohort_summary.csv':summary,'segment_daily_activity.csv':daily,
        'reference_reproduction.csv':reproduction}
    for name,frame in outputs.items():frame.to_csv(ROOT/name,index=False,encoding='utf-8-sig',float_format='%.12g')
    result={'analysis':{'baseline_start_utc':'2013-03-01T00:00:00Z',
        'baseline_end_exclusive_utc':'2013-03-08T00:00:00Z',
        'followup_start_utc':'2013-03-08T00:00:00Z',
        'followup_end_exclusive_utc':'2013-03-12T00:00:00Z',
        'timezone':'UTC','unit':'user','segment_reference':str(REFERENCE),
        'segment_rules_unchanged':True,'M_ties':'rank(method=first), original CSV category order; unchanged from PDF',
        'followup_day_axis':'common calendar dates, not days since signup or individual first learning'},
        'quality':quality,'checks':checks,
        'baseline_users':len(u),'baseline_trace_rows':int(b.trace_rows.sum()),
        'baseline_nsm':int(u.baseline_sustained.sum()),
        'followup_only_users_excluded':len(future_only),
        'daily_activity_rows':len(day),'returned_users':int(u.returned_4d.sum()),
        'no_return_users':int((u.returned_4d==0).sum()),
        'overall_return_4d_rate':float(u.returned_4d.mean()),
        'overall_return_2plus_days_rate':float(u.returned_2plus_days.mean()),
        'overall_mean_followup_active_days':float(u.followup_active_days.mean()),
        'active_days_distribution':{str(k):int(v) for k,v in u.active_days.value_counts().sort_index().items()},
        'segment_summary':summary.to_dict('records'),
        'reproduction':reproduction.to_dict('records'),
        'metric_definitions':{
            'activity_rate':'active users on calendar date / all fixed baseline segment users',
            'return_4d_rate':'users active at least once in four followup days / all fixed baseline segment users',
            'return_2plus_days_rate':'users active on at least two followup dates / all fixed baseline segment users',
            'mean_followup_active_days':'total user-active-days / all fixed baseline segment users, including zero days',
            'exposures':'sum(session_seen), lexeme exposures, not unique exercises'},
        'limitations':['Four-day descriptive followup, not D7 retention or a causal intervention effect.',
            'No learning record is coded inactive within the extract; this does not prove permanent churn.',
            'Segment labels and order are preserved from the PDF; first observed date is not signup date.'],
        'outputs':{name:{'rows':len(frame),'sha256':sha256(ROOT/name)} for name,frame in outputs.items()}}
    (ROOT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary[['segment','users','returned_4d_users','return_4d_rate','returned_2plus_days_users',
                   'return_2plus_days_rate','mean_followup_active_days']].to_string(index=False),flush=True)
    print(json.dumps({k:v for k,v in result.items() if k not in ['segment_summary','reproduction','outputs','metric_definitions']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
