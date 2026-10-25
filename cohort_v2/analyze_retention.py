"""Marketing retention cohorts using frozen Yeojin segments.

Baseline: 2013-03-01 through 07 UTC, landmark: March 08.
Followup: four complete dates, March 08 through 11 UTC.
Three-day inactivity is an operational flag, not confirmed permanent churn.
"""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
SOURCE=ROOT/'cohort_inputs'
DATES=pd.date_range('2013-03-08',periods=4)
SEGMENTS=['꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형']
STATES=['관측기간 미복귀','1회 재학습 후 3일 비활동','1회 재학습·추적 종료','2일 이상 재학습']

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    original=json.loads((SOURCE/'manifest.json').read_text(encoding='utf-8'))
    metadata=json.loads((SOURCE/'results.json').read_text(encoding='utf-8'))
    source_names=['user_cohort.csv','user_daily_activity.csv','segment_cohort_summary.csv']
    hashes={n:digest(SOURCE/n) for n in source_names}
    assert all(hashes[n]==original['files'][n]['sha256'] for n in source_names)
    u=pd.read_csv(SOURCE/'user_cohort.csv')
    day0=pd.read_csv(SOURCE/'user_daily_activity.csv')
    old=pd.read_csv(SOURCE/'segment_cohort_summary.csv').set_index('segment')
    assert len(u)==82467 and len(day0)==len(u)*4
    assert not u.user_id.duplicated().any() and not day0.duplicated(['user_id','date']).any()
    daymatrix=day0.pivot(index='user_id',columns='date',values='active').reindex(u.user_id)
    active=daymatrix.to_numpy(dtype=int)
    expected=u[['active_'+d.strftime('%Y-%m-%d') for d in DATES]].to_numpy(dtype=int)
    np.testing.assert_array_equal(active,expected)
    cum=active.cumsum(axis=1)
    last_day=pd.to_datetime(u.last_active).to_numpy(dtype='datetime64[D]').astype('int64')
    date_numbers=DATES.to_numpy(dtype='datetime64[D]').astype('int64')
    first=np.where(active.any(axis=1),active.argmax(axis=1),-1)
    previous_gap=np.zeros_like(active)
    current_gap=np.zeros_like(active)
    running_last=last_day.copy()
    for j,number in enumerate(date_numbers):
        previous_gap[:,j]=number-1-running_last
        running_last=np.where(active[:,j]==1,number,running_last)
        current_gap[:,j]=number-running_last
    u['first_return_date']=[DATES[i].strftime('%Y-%m-%d') if i>=0 else None for i in first]
    u['followup_state']=np.select([cum[:,-1]==0,(cum[:,-1]==1)&(current_gap[:,-1]>=3),cum[:,-1]==1],
                                 STATES[:3],default=STATES[3])
    u['inactive_days_at_followup_end']=current_gap[:,-1]
    u['inactive_3day_flag_at_end']=(current_gap[:,-1]>=3).astype(int)
    u['eligible_2day_after_return']=((first>=0)&(first<=1)).astype(int)
    repeat2=np.full(len(u),np.nan)
    nextday=np.full(len(u),np.nan)
    for i in range(3):nextday[first==i]=active[first==i,i+1]
    for i in range(2):repeat2[first==i]=(active[first==i,i+1:i+3].sum(axis=1)>=1).astype(int)
    u['returned_next_day_after_first_return']=nextday
    u['relearned_within_2days_after_first_return']=repeat2
    for j,d in enumerate(DATES):
        key=d.strftime('%Y-%m-%d')
        u['cumulative_active_days_'+key]=cum[:,j]
        u['inactive_days_'+key]=current_gap[:,j]
    panel=[]
    for j,d in enumerate(DATES):
        part=pd.DataFrame({'user_id':u.user_id,'segment':u.segment,'date':d.strftime('%Y-%m-%d'),
            'followup_day':j+1,'active':active[:,j],'cumulative_active_days':cum[:,j],
            'inactive_days_before_date':previous_gap[:,j],'inactive_days_end_of_date':current_gap[:,j],
            'inactive_2day_flag':(current_gap[:,j]>=2).astype(int),
            'inactive_3day_flag':(current_gap[:,j]>=3).astype(int),
            'new_3day_inactive_flag':((previous_gap[:,j]<3)&(current_gap[:,j]>=3)).astype(int),
            'start_3day_inactive_flag':(previous_gap[:,j]>=3).astype(int),
            'relearned_after_3day_inactivity':((previous_gap[:,j]>=3)&(active[:,j]==1)).astype(int)})
        panel.append(part)
    panel=pd.concat(panel,ignore_index=True)
    snapshots=[]
    for seg in SEGMENTS:
        ids=(u.segment==seg).to_numpy();n=int(ids.sum())
        for j,d in enumerate(DATES):
            eligible=previous_gap[ids,j]>=3
            flag=current_gap[ids,j]>=3
            restored=eligible&(active[ids,j]==1)
            snapshots.append({'segment':seg,'date':d.strftime('%Y-%m-%d'),'followup_day':j+1,
                'cohort_users':n,'active_users':int(active[ids,j].sum()),'daily_relearning_rate':float(active[ids,j].mean()),
                'cumulative_returned_users':int((cum[ids,j]>=1).sum()),
                'cumulative_return_rate':float((cum[ids,j]>=1).mean()),
                'cumulative_repeat_users':int((cum[ids,j]>=2).sum()),
                'cumulative_repeat_rate':float((cum[ids,j]>=2).mean()),
                'inactive_2day_users':int((current_gap[ids,j]>=2).sum()),
                'inactive_2day_rate':float((current_gap[ids,j]>=2).mean()),
                'inactive_3day_users':int(flag.sum()),'inactive_3day_rate':float(flag.mean()),
                'new_3day_inactive_users':int(((previous_gap[ids,j]<3)&flag).sum()),
                'start_3day_inactive_users':int(eligible.sum()),
                'relearned_after_3day_inactivity_users':int(restored.sum()),
                'relearning_rate_among_start_3day_inactive':float(restored.sum()/eligible.sum()) if eligible.sum() else None})
    snapshots=pd.DataFrame(snapshots)
    cohorts=[]
    for seg in ['전체']+SEGMENTS:
        for j,d in enumerate(DATES):
            ids=first==j
            if seg!='전체':ids=ids&(u.segment.to_numpy()==seg)
            n=int(ids.sum())
            row={'segment':seg,'first_return_date':d.strftime('%Y-%m-%d'),'return_cohort_users':n}
            for offset in range(4):
                observable=j+offset<4
                value=int(active[ids,j+offset].sum()) if observable else None
                row[f'D{offset}_observable']=observable
                row[f'D{offset}_active_users']=value
                row[f'D{offset}_relearning_rate']=value/n if observable and n else None
            row['within_2days_observable']=j<=1
            row['within_2days_repeat_users']=int((active[ids,j+1:j+3].sum(axis=1)>=1).sum()) if j<=1 else None
            row['within_2days_repeat_rate']=row['within_2days_repeat_users']/n if j<=1 and n else None
            cohorts.append(row)
    cohorts=pd.DataFrame(cohorts)
    summaries=[]
    states=[]
    for seg in SEGMENTS:
        group=u[u.segment==seg];n=len(group)
        nd=group.returned_next_day_after_first_return.dropna()
        twod=group.relearned_within_2days_after_first_return.dropna()
        counts=group.followup_state.value_counts().reindex(STATES,fill_value=0)
        for state,count in counts.items():states.append({'segment':seg,'state':state,'cohort_users':n,'users':int(count),'share':float(count/n)})
        summaries.append({'segment':seg,'cohort_users':n,
            'returned_users':int(group.returned_4d.sum()),'return_4day_rate':float(group.returned_4d.mean()),
            'repeat_users':int(group.returned_2plus_days.sum()),'repeat_4day_rate':float(group.returned_2plus_days.mean()),
            'mean_active_days':float(group.followup_active_days.mean()),
            'nextday_eligible_returners':len(nd),'nextday_repeat_users':int(nd.sum()),
            'nextday_repeat_rate':float(nd.mean()) if len(nd) else None,
            'two_day_eligible_returners':len(twod),'two_day_repeat_users':int(twod.sum()),
            'two_day_repeat_rate':float(twod.mean()) if len(twod) else None,
            'inactive_3day_users_at_end':int(group.inactive_3day_flag_at_end.sum()),
            'inactive_3day_rate_at_end':float(group.inactive_3day_flag_at_end.mean()),
            'no_return_users':int(counts.iloc[0]),'one_return_then_inactive_users':int(counts.iloc[1]),
            'one_return_users_other':int(counts.iloc[2])})
    summary=pd.DataFrame(summaries)
    states=pd.DataFrame(states)
    total=snapshots.groupby(['date','followup_day'],sort=True).sum(numeric_only=True).reset_index()
    for count,rate in [('active_users','daily_relearning_rate'),('cumulative_returned_users','cumulative_return_rate'),
                       ('cumulative_repeat_users','cumulative_repeat_rate'),('inactive_2day_users','inactive_2day_rate'),
                       ('inactive_3day_users','inactive_3day_rate')]:
        total[rate]=total[count]/total.cohort_users
    total['relearning_rate_among_start_3day_inactive']=total.relearned_after_3day_inactivity_users/total.start_3day_inactive_users
    # Historical, as-of-end review pools; these are proposed experiment targets.
    # Priority is a stated NSM-oriented hypothesis, not measured campaign uplift.
    pool_conditions=[
        (u.segment=='습관 형성형')&u.inactive_days_at_followup_end.between(1,2),
        (u.segment=='습관 형성형')&(u.inactive_days_at_followup_end>=3),
        u.segment.isin(['멈춤-꾸준형','멈춤-몰입형'])&(u.inactive_days_at_followup_end>=3),
        (u.segment=='꾸준형')&u.inactive_days_at_followup_end.between(1,2)]
    pool_names=['습관 형성형·1~2일 비활동','습관 형성형·3일 이상 비활동',
                '기존 학습 이력·3일 이상 비활동','꾸준형·1~2일 비활동']
    u['review_pool']=np.select(pool_conditions,pool_names,default='')
    candidates=u[u.review_pool!=''][['user_id','segment','review_pool','inactive_days_at_followup_end',
        'followup_active_days','words_seen','active_days','first_return_date','followup_state']].copy()
    candidates['asof_date_utc']='2013-03-11'
    pools=[]
    for name,condition in zip(pool_names,pool_conditions):
        group=u[condition]
        pools.append({'review_pool':name,'users':len(group),'baseline_exposures':int(group.words_seen.sum()),
                      'repeat_users_in_followup':int(group.returned_2plus_days.sum())})
    checks={
        'source_hashes_unchanged':all(hashes[n]==original['files'][n]['sha256'] for n in source_names),
        'segments_unchanged':summary.set_index('segment').cohort_users.eq(old.users).all(),
        'updated_segment_return_counts_match':summary.set_index('segment').returned_users.eq(old.returned_4d_users).all(),
        'updated_segment_repeat_counts_match':summary.set_index('segment').repeat_users.eq(old.returned_2plus_days_users).all(),
        'fixed_daily_denominators':snapshots.cohort_users.eq(snapshots.segment.map(summary.set_index('segment').cohort_users)).all(),
        'cumulative_return_monotonic':np.all(np.diff((cum>=1).astype(int),axis=1)>=0),
        'cumulative_repeat_monotonic':np.all(np.diff((cum>=2).astype(int),axis=1)>=0),
        'repeat_is_subset_of_return':np.all((cum>=2)<=(cum>=1)),
        'first_return_cohorts_partition_returners':int(cohorts[cohorts.segment=='전체'].return_cohort_users.sum())==int(u.returned_4d.sum()),
        'D0_is_100pct':cohorts.loc[cohorts.return_cohort_users>0,'D0_relearning_rate'].eq(1).all(),
        'unobserved_cells_are_missing':all(cohorts.loc[~cohorts[f'D{k}_observable'],f'D{k}_relearning_rate'].isna().all() for k in range(4)),
        'late_returners_excluded_from_2day_denominator':int(u.eligible_2day_after_return.sum())==int(cohorts[(cohorts.segment=='전체')&cohorts.within_2days_observable].return_cohort_users.sum()),
        'end_states_partition_baseline':int(states.users.sum())==len(u),
        'end_inactive_equals_no_return_plus_return_then_inactive':int(u.inactive_3day_flag_at_end.sum())==int((u.followup_state==STATES[0]).sum()+(u.followup_state==STATES[1]).sum()),
        'daily_gap_state_flow_reconciles':True,
        'source_user_day_activity_matches':np.array_equal(active,expected),
        'panel_user_dates_unique':not panel.duplicated(['user_id','date']).any(),
    }
    for seg in SEGMENTS:
        group=snapshots[snapshots.segment==seg].sort_values('date')
        np.testing.assert_array_equal(group.inactive_3day_users.to_numpy(),
            group.start_3day_inactive_users.to_numpy()+group.new_3day_inactive_users.to_numpy()-group.relearned_after_3day_inactivity_users.to_numpy())
        assert int(group.cumulative_returned_users.iloc[-1])==int(old.loc[seg,'returned_4d_users'])
        assert int(group.cumulative_repeat_users.iloc[-1])==int(old.loc[seg,'returned_2plus_days_users'])
    assert all(checks.values()),{k:bool(v) for k,v in checks.items() if not v}
    frames={'user_retention_cohort.csv':u,'user_daily_retention.csv':panel,
        'segment_retention_summary.csv':summary,'segment_daily_retention.csv':snapshots,
        'first_return_cohorts.csv':cohorts,'segment_followup_states.csv':states,
        'overall_daily_retention.csv':total,'crm_review_candidates.csv':candidates}
    for n,f in frames.items():f.to_csv(ROOT/n,index=False,encoding='utf-8-sig',float_format='%.12g')
    result={'purpose':'Learning repetition and short-term inactivity prevention using frozen Yeojin segments',
        'baseline_window':'2013-03-01 through 2013-03-07 UTC',
        'followup_window':'2013-03-08 through 2013-03-11 UTC',
        'landmark':'2013-03-08 00:00 UTC','baseline_users':len(u),
        'source_files':{n:{'path':str(SOURCE/n),'sha256':h} for n,h in hashes.items()},
        'segment_reference':metadata['analysis']['segment_reference'],
        'checks':{k:bool(v) for k,v in checks.items()},
        'definitions':{
            'behavior_cohort':'fixed baseline segment; all baseline users remain in each denominator',
            'return_cohort':'first observed relearning date within followup; D0 is that return event, not signup',
            'daily_relearning_rate':'active users on date / all fixed baseline segment users',
            'cumulative_return_rate':'users active at least once up to date / all fixed baseline segment users',
            'cumulative_repeat_rate':'users active on at least two distinct dates up to date / all fixed baseline segment users',
            'return_cohort_Dk':'users active exactly k calendar days after their first followup return / original return-date cohort users',
            'within_2days_repeat':'users learning again on D+1 or D+2 / returners with both dates fully observed (first return Mar 08 or 09)',
            'inactive_3day_flag':'no trace on three or more consecutive calendar dates, counting from the last baseline/followup active date',
            'reactivation_after_3day_gap':'active today among users already inactive for at least three calendar days at end of yesterday',
            'inactivity_threshold':'3 calendar days, aligned with the PDF risk theme; analyst operational assumption; 2-day sensitivity also reported'},
        'limitations':['Four followup days cannot establish next-week NSM, D7/D30 retention, permanent churn or campaign lift.',
            'An observed trace extract may not represent every activity in the service.',
            'Later first-return cohorts are right-censored; unobserved offsets are missing, not zero.',
            'Conditional repeat metrics exclude non-returners and late-returners; cannot compare directly with unconditional rates.',
            'Segments differ in baseline recency, activity and amount; comparisons are descriptive, not a causal test.',
            'Calendar-day boundaries use UTC; inactivity flags are not exact 72-hour elapsed-time rules.'],
        'segment_summary':summary.to_dict('records'),'overall_daily':total.to_dict('records'),
        'first_return_cohorts_overall':cohorts[cohorts.segment=='전체'].replace({np.nan:None}).to_dict('records'),
        'states':STATES,'review_pools':pools,
        'overall_summary':{'users':len(u),'returned_users':int(u.returned_4d.sum()),
            'repeated_users':int(u.returned_2plus_days.sum()),
            'repeat_share_among_returners':float(u.returned_2plus_days.sum()/u.returned_4d.sum()),
            'eligible_2day_returners':int(u.eligible_2day_after_return.sum()),
            'within_2day_repeat_users':int(u.relearned_within_2days_after_first_return.sum()),
            'within_2day_repeat_rate':float(u.relearned_within_2days_after_first_return.mean()),
            'one_return_then_inactive_users':int((u.followup_state==STATES[1]).sum())},
        'outputs':{n:{'rows':len(f),'sha256':digest(ROOT/n)} for n,f in frames.items()}}
    (ROOT/'results_retention.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary.to_string(index=False))
    print('FIRST RETURN COHORTS\n',cohorts[cohorts.segment=='전체'].to_string(index=False))
    print('OVERALL DAILY\n',total[['date','active_users','cumulative_return_rate','cumulative_repeat_rate','inactive_3day_rate','new_3day_inactive_users','relearned_after_3day_inactivity_users']].to_string(index=False))
    print('Checks passed:',len(checks))

if __name__=='__main__':main()
