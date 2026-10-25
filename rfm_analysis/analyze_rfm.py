"""Reproduce the Duolingo learning RFM analysis using pandas and NumPy.

M measures lexeme exposures, not money, elapsed time, or unique exercises.
All calendar boundaries use UTC. The public data are a learning trace extract.
"""
import os
os.environ.setdefault('OPENBLAS_NUM_THREADS', '1')
os.environ.setdefault('OMP_NUM_THREADS', '1')

from pathlib import Path
import hashlib
import json
import time
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'settles.acl16.learning_traces.13m.csv.gz'
if not SOURCE.exists():  # .gz는 원본 CSV와 내용 동일(md5 일치)
    SOURCE = ROOT.parent / 'learning_traces.13m.csv' / 'learning_traces.13m.csv'
COLS = ['p_recall', 'timestamp', 'delta', 'user_id', 'learning_language',
        'ui_language', 'lexeme_id', 'lexeme_string', 'history_seen',
        'history_correct', 'session_seen', 'session_correct']
DTYPES = {c: 'int64' for c in ['timestamp', 'delta', 'history_seen',
          'history_correct', 'session_seen', 'session_correct']}
DTYPES.update({c: 'object' for c in ['user_id', 'learning_language',
              'ui_language', 'lexeme_id', 'lexeme_string']})
DTYPES['p_recall'] = 'float64'
SEGMENTS = ['핵심 학습형', '반복 학습형', '집중 성장형', '최근 저강도형',
            '관심 유지형', '우선 복귀형', '저활동·휴면형']

def epoch(s):
    return int(pd.Timestamp(s, tz='UTC').timestamp())

def aggregate_source():
    started = time.time()
    chunks, hashes = [], []
    n, missing, invalid = 0, 0, 0
    for i, c in enumerate(pd.read_csv(SOURCE, dtype=DTYPES, chunksize=250_000)):
        missing += int(c.isna().any(axis=1).sum())
        valid = ((c.session_seen > 0) & (c.session_correct >= 0) &
                 (c.session_correct <= c.session_seen) & (c.timestamp > 0) &
                 (c.delta >= 0) & c.p_recall.between(0, 1))
        invalid += int((~valid).sum())
        hashes.append(pd.util.hash_pandas_object(c[COLS], index=False).to_numpy())
        g = c.groupby(['user_id', 'timestamp'], sort=False).agg(
            exposures=('session_seen', 'sum'), correct=('session_correct', 'sum'),
            traces=('session_seen', 'size'))
        chunks.append(g)
        n += len(c)
        if (i + 1) % 8 == 0:
            print(f'Read {n:,} rows; {time.time()-started:.1f}s', flush=True)
    assert missing == 0 and invalid == 0, (missing, invalid)
    h = np.concatenate(hashes)
    order = np.argsort(h, kind='stable')
    same = h[order[1:]] == h[order[:-1]]
    # Hashes locate candidates only. Full values below verify exact duplicates.
    candidates = np.unique(np.r_[order[:-1][same], order[1:][same]])
    print(f'Checking {len(candidates)} candidate rows for exact duplicates', flush=True)
    candidate_rows, offset = [], 0
    for c in pd.read_csv(SOURCE, dtype=DTYPES, chunksize=250_000):
        ids = candidates[(candidates >= offset) & (candidates < offset+len(c))]
        if len(ids):
            t = c.iloc[ids-offset].copy()
            t.index = ids
            candidate_rows.append(t)
        offset += len(c)
    duplicates = pd.DataFrame(columns=COLS)
    if candidate_rows:
        candidates_df = pd.concat(candidate_rows).sort_index()
        duplicates = candidates_df[candidates_df.duplicated(COLS, keep='first')]
    sessions = pd.concat(chunks).groupby(level=[0, 1], sort=False).sum()
    if len(duplicates):
        adjustments = duplicates.groupby(['user_id', 'timestamp']).agg(
            exposures=('session_seen', 'sum'), correct=('session_correct', 'sum'),
            traces=('session_seen', 'size'))
        sessions.loc[adjustments.index] -= adjustments
    sessions = sessions.reset_index().sort_values(['user_id', 'timestamp'])
    assert (sessions.exposures > 0).all()
    assert int(sessions.traces.sum()) == n-len(duplicates)
    sessions.to_pickle(ROOT / 'sessions.pkl')
    meta = {'raw_rows': n, 'exact_duplicates_removed': len(duplicates),
            'clean_rows': n-len(duplicates), 'missing_rows': missing,
            'invalid_rows': invalid, 'unique_users': int(sessions.user_id.nunique()),
            'session_proxy_count': len(sessions),
            'min_timestamp': int(sessions.timestamp.min()),
            'max_timestamp': int(sessions.timestamp.max()),
            'min_utc': str(pd.to_datetime(sessions.timestamp.min(), unit='s', utc=True)),
            'max_utc': str(pd.to_datetime(sessions.timestamp.max(), unit='s', utc=True)),
            'sha256': hashlib.file_digest(SOURCE.open('rb'), 'sha256').hexdigest()}
    (ROOT / 'quality.json').write_text(json.dumps(meta, indent=2), encoding='utf-8')
    return sessions, meta

def quintile(values, reverse=False):
    cuts = np.quantile(values, [0.2, 0.4, 0.6, 0.8], method='linear')
    # Right-closed intervals: a tie at a boundary stays in the lower raw bin.
    raw_score = 1 + np.searchsorted(cuts, values, side='left')
    return (6-raw_score if reverse else raw_score), cuts

def assign_segment(u):
    r, f, m = u.R_score, u.F_score, u.M_score
    masks = [
        (r >= 4) & (f >= 4) & (m >= 4),
        (r >= 3) & (f >= 4),
        (r >= 4) & (f <= 3) & (m >= 3),
        (r >= 4) & (f <= 3) & (m <= 2),
        (r == 3) & (f <= 3),
        (r <= 2) & ((f >= 3) | (m >= 3)),
        (r <= 2) & (f <= 2) & (m <= 2)]
    u['segment'] = np.select(masks, SEGMENTS, default='UNASSIGNED')
    assert (u.segment != 'UNASSIGNED').all()
    return u

def user_snapshot(s, start, cutoff):
    p = s[(s.timestamp >= start) & (s.timestamp < cutoff)].copy()
    p['day'] = p.timestamp // 86400
    u = p.groupby('user_id').agg(last_timestamp=('timestamp', 'max'),
        first_timestamp=('timestamp', 'min'), F=('timestamp', 'size'),
        M=('exposures', 'sum'), correct=('correct', 'sum'),
        active_days=('day', 'nunique'))
    u['R'] = (cutoff-u.last_timestamp)/86400
    u['recall_rate'] = u.correct/u.M
    thresholds = {}
    for name in ['R', 'F', 'M']:
        u[name+'_score'], cuts = quintile(u[name].to_numpy(), name == 'R')
        thresholds[name] = cuts.tolist()
    u['RFM_code'] = (100*u.R_score + 10*u.F_score + u.M_score).astype(int)
    return assign_segment(u), thresholds

def summary(u):
    g = u.groupby('segment').agg(users=('R', 'size'), exposures=('M', 'sum'),
        correct=('correct', 'sum'), R_median=('R', 'median'),
        F_median=('F', 'median'), M_median=('M', 'median'),
        active_days_median=('active_days', 'median'))
    g = g.reindex(SEGMENTS)
    g['user_pct'] = g.users/len(u)*100
    g['exposure_pct'] = g.exposures/u.M.sum()*100
    g['weighted_recall_pct'] = g.correct/g.exposures*100
    g['revenue_pct'] = np.nan
    assert int(g.users.sum()) == len(u)
    assert int(g.exposures.sum()) == int(u.M.sum())
    return g

def kmeans(x, k, seed, n_init=20):
    rng = np.random.default_rng(seed)
    best = None
    for _ in range(n_init):
        centers = [x[rng.integers(len(x))]]
        while len(centers) < k:
            d = np.min(np.stack([np.sum((x-c)**2, axis=1) for c in centers]), axis=0)
            centers.append(x[rng.choice(len(x), p=d/d.sum())])
        centers = np.array(centers)
        for iteration in range(200):
            d = np.stack([np.sum((x-c)**2, axis=1) for c in centers], axis=1)
            labels = d.argmin(axis=1)
            new = np.array([x[labels == j].mean(axis=0) if np.any(labels == j)
                           else x[np.argmax(d.min(axis=1))] for j in range(k)])
            shift = float(np.sum((new-centers)**2))
            centers = new
            if shift < 1e-8:
                break
        d = np.stack([np.sum((x-c)**2, axis=1) for c in centers], axis=1)
        labels = d.argmin(axis=1)
        inertia = float(d[np.arange(len(x)), labels].sum())
        if best is None or inertia < best[0]:
            best = (inertia, labels, centers, iteration+1)
    return best

def silhouette(x, labels, indices):
    a, y = x[indices], labels[indices]
    sq = np.sum(a*a, axis=1)
    distances = np.sqrt(np.maximum(sq[:, None]+sq[None, :]-2*a@a.T, 0))
    np.fill_diagonal(distances, 0)
    intra = np.zeros(len(a))
    inter = np.full(len(a), np.inf)
    counts = np.bincount(y)
    for j in np.unique(y):
        mask = y == j
        mean_distance = distances[:, mask].sum(axis=1)/counts[j]
        inter[~mask] = np.minimum(inter[~mask], mean_distance[~mask])
        if counts[j] > 1:
            intra[mask] = distances[mask][:, mask].sum(axis=1)/(counts[j]-1)
    score = (inter-intra)/np.maximum(intra, inter)
    score[counts[y] == 1] = 0
    return float(score.mean())

def ari(a, b):
    c = pd.crosstab(a, b).to_numpy(dtype=float)
    choose2 = lambda v: np.sum(v*(v-1)/2)
    n = c.sum()
    both, row, col = choose2(c), choose2(c.sum(axis=1)), choose2(c.sum(axis=0))
    expected = row*col/(n*(n-1)/2)
    maximum = (row+col)/2
    return float((both-expected)/(maximum-expected)) if maximum != expected else 1.0

def main():
    if (ROOT/'sessions.pkl').exists():
        s = pd.read_pickle(ROOT/'sessions.pkl')
        meta = json.loads((ROOT/'quality.json').read_text(encoding='utf-8'))
    else:
        s, meta = aggregate_source()
    T = epoch('2013-03-13')
    u, thresholds = user_snapshot(s, int(s.timestamp.min()), T)
    # Last completely observed calendar week; exclude both partial boundary dates.
    w = s[(s.timestamp >= epoch('2013-03-05')) & (s.timestamp < epoch('2013-03-12'))].copy()
    w['day'] = w.timestamp//86400
    days = w.groupby('user_id').day.nunique()
    u['week_active_days'] = days.reindex(u.index, fill_value=0)
    u['week_sustained'] = u.week_active_days >= 4
    pair = w[['user_id', 'day']].drop_duplicates().sort_values(['user_id', 'day'])
    pair['next_day'] = pair.groupby('user_id').day.shift(-1)
    eligible = pair[pair.day < epoch('2013-03-11')//86400].copy()
    eligible['return_next_day'] = eligible.next_day == eligible.day+1
    d1 = eligible.groupby('user_id').agg(d1_eligible=('day', 'size'),
        d1_return=('return_next_day', 'sum'))
    u = u.join(d1).fillna({'d1_eligible': 0, 'd1_return': 0})
    g = summary(u)
    wg = u.groupby('segment').agg(weekly_active=('week_active_days', lambda x: int((x >= 1).sum())),
        weekly_sustained=('week_sustained', 'sum'), d1_eligible=('d1_eligible', 'sum'),
        d1_return=('d1_return', 'sum'))
    g = g.join(wg)
    g['weekly_sustained_pct_among_weekly_active'] = g.weekly_sustained/g.weekly_active*100
    g['next_day_return_pct'] = g.d1_return/g.d1_eligible*100
    g.to_csv(ROOT/'segment_summary.csv', encoding='utf-8-sig')
    # Short forward validation uses only pre-cutoff data to assign segments.
    baseline, base_thresholds = user_snapshot(s, epoch('2013-03-01'), epoch('2013-03-08'))
    future = s[(s.timestamp >= epoch('2013-03-08')) & (s.timestamp < epoch('2013-03-12'))]
    baseline['return_in_next_4_days'] = baseline.index.isin(future.user_id.unique())
    bg = baseline.groupby('segment').agg(baseline_users=('R', 'size'),
        returned_users=('return_in_next_4_days', 'sum')).reindex(SEGMENTS)
    bg['subsequent_4day_return_pct'] = bg.returned_users/bg.baseline_users*100
    bg.to_csv(ROOT/'forward_validation.csv', encoding='utf-8-sig')
    # Cluster the same continuous R/F/M variables for a fair comparison.
    logx = np.log1p(u[['R', 'F', 'M']].to_numpy(dtype=float))
    x = (logx-logx.mean(axis=0))/logx.std(axis=0)
    rng = np.random.default_rng(20261012)
    indices = rng.choice(len(x), min(2000, len(x)), replace=False)
    candidates = []
    for k in [3, 4, 5]:
        inertia, labels, centers, iterations = kmeans(x, k, 20261012+k)
        sil = silhouette(x, labels, indices)
        candidates.append({'k': k, 'inertia': inertia, 'silhouette_2000': sil,
                           'iterations_best_start': iterations, 'labels': labels})
        print(f'K={k}: silhouette={sil:.4f}, inertia={inertia:.1f}', flush=True)
    best = max(candidates, key=lambda q: q['silhouette_2000'])
    # Stable display IDs sort cluster medians by F, then R.
    temp = u[['R', 'F', 'M']].copy()
    temp['cluster'] = best['labels']
    cluster_order = temp.groupby('cluster').agg(F=('F', 'median'), R=('R', 'median')).sort_values(['F', 'R']).index
    mapping = {old: 'C'+str(i+1) for i, old in enumerate(cluster_order)}
    u['cluster'] = pd.Series(best['labels'], index=u.index).map(mapping)
    cg = u.groupby('cluster').agg(users=('R', 'size'), exposures=('M', 'sum'),
        R_median=('R', 'median'), F_median=('F', 'median'), M_median=('M', 'median'),
        weekly_sustained=('week_sustained', 'sum'))
    cg['user_pct'] = cg.users/len(u)*100
    cg['exposure_pct'] = cg.exposures/u.M.sum()*100
    cg.to_csv(ROOT/'cluster_summary.csv', encoding='utf-8-sig')
    cross = pd.crosstab(u.segment, u.cluster).reindex(SEGMENTS)
    cross.to_csv(ROOT/'segment_cluster_counts.csv', encoding='utf-8-sig')
    cross.div(cross.sum(axis=1), axis=0).mul(100).to_csv(ROOT/'segment_cluster_row_pct.csv', encoding='utf-8-sig')
    assert abs(ari(u.segment.to_numpy(), u.segment.to_numpy())-1) < 1e-12
    assert int(cross.to_numpy().sum()) == len(u)
    u.to_csv(ROOT/'user_rfm.csv', encoding='utf-8-sig')
    result = {'quality': meta, 'reference_utc': '2013-03-13 00:00:00+00:00',
        'thresholds': thresholds, 'baseline_thresholds': base_thresholds,
        'score_distribution': {col: u[col].value_counts().sort_index().to_dict()
            for col in ['R_score', 'F_score', 'M_score']},
        'RFM_F_M_pearson': float(u[['F', 'M']].corr().iloc[0, 1]),
        'total_exposures': int(u.M.sum()),
        'weekly_active': int((u.week_active_days >= 1).sum()),
        'weekly_sustained': int(u.week_sustained.sum()),
        'next_day_return_pct': float(u.d1_return.sum()/u.d1_eligible.sum()*100),
        'kmeans_candidates': [{key: val for key, val in q.items() if key != 'labels'} for q in candidates],
        'selected_k': best['k'], 'adjusted_rand_index': ari(u.segment.to_numpy(), u.cluster.to_numpy()),
        'segment_summary': json.loads(g.reset_index().to_json(orient='records')),
        'cluster_summary': json.loads(cg.reset_index().to_json(orient='records')),
        'forward_validation': json.loads(bg.reset_index().to_json(orient='records'))}
    (ROOT/'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)

if __name__ == '__main__':
    main()
