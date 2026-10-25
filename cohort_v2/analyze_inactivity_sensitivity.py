"""Descriptive 2/3-calendar-day inactivity sensitivity on the fixed v3 cohort."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'sensitivity'
SEGMENTS=['꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형']
DATES=[f'2013-03-{d:02d}' for d in range(8,12)]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=True)
    meta=json.loads((ROOT/'results_retention.json').read_text(encoding='utf-8'))
    files=['user_retention_cohort.csv','user_daily_retention.csv','segment_daily_retention.csv','overall_daily_retention.csv']
    hashes={f:sha(ROOT/f) for f in files}
    assert all(hashes[f]==meta['outputs'][f]['sha256'] for f in files)
    u=pd.read_csv(ROOT/files[0],low_memory=False)
    panel=pd.read_csv(ROOT/files[1])
    saved=pd.read_csv(ROOT/files[2]).set_index(['segment','date'])
    overall=pd.read_csv(ROOT/files[3]).set_index('date')
    assert len(u)==82467 and u.user_id.is_unique and set(u.segment)==set(SEGMENTS)
    assert len(panel)==len(u)*4 and not panel.duplicated(['user_id','date']).any()
    a=u[[f'active_{d}' for d in DATES]].to_numpy(int)
    assert np.isin(a,[0,1]).all()
    cum=a.cumsum(axis=1)
    last=pd.to_datetime(u.last_active).to_numpy(dtype='datetime64[D]').astype(int)
    daynums=np.array(DATES,dtype='datetime64[D]').astype(int)
    initial_gap=daynums[0]-1-last
    assert np.all(initial_gap>=0)
    before=np.empty_like(a)
    gap=np.empty_like(a)
    for j,num in enumerate(daynums):
        before[:,j]=num-1-last
        last=np.where(a[:,j]==1,num,last)
        gap[:,j]=num-last
        check=panel.loc[panel.date.eq(DATES[j])].set_index('user_id').loc[u.user_id]
        assert np.array_equal(check.segment.to_numpy(),u.segment.to_numpy())
        for col,values in [('active',a[:,j]),('inactive_days_before_date',before[:,j]),
                           ('inactive_days_end_of_date',gap[:,j]),('inactive_2day_flag',gap[:,j]>=2),
                           ('inactive_3day_flag',gap[:,j]>=3)]:
            assert np.array_equal(check[col].to_numpy(),values)
    assert np.array_equal(gap[:,-1],u.inactive_days_at_followup_end)
    rows=[]
    following=[]
    for s in ['전체']+SEGMENTS:
        mask=np.ones(len(u),bool) if s=='전체' else u.segment.eq(s).to_numpy()
        n=int(mask.sum())
        for j,date in enumerate(DATES):
            g=gap[mask,j]
            b=before[mask,j]
            activity=a[mask,j]
            count2,count3=int((g>=2).sum()),int((g>=3).sum())
            exact2=int((g==2).sum())
            assert count2-count3==exact2
            r=dict(segment=s,date=date,cohort_users=n,inactive_2day_users=count2,inactive_3day_users=count3,
                   inactive_2day_rate=count2/n,inactive_3day_rate=count3/n,
                   added_exact2_users=exact2,added_pp=100*exact2/n,
                   relative_expansion=exact2/count3 if count3 else None,
                   overlap_share_of_2day=count3/count2 if count2 else None,
                   initial_2day_users=int((initial_gap[mask]>=2).sum()),initial_3day_users=int((initial_gap[mask]>=3).sum()),
                   exact1_users=int((g==1).sum()),same_day_active_users=int(activity.sum()))
            for t in [2,3]:
                start=int((b>=t).sum())
                new=int(((b<t)&(g>=t)).sum())
                relearn=int(((b>=t)&(activity==1)).sum())
                end=int((g>=t).sum())
                assert start+new-relearn==end
                if j>0:
                    assert start==int((gap[mask,j-1]>=t).sum())
                r.update({f'start_{t}day_users':start,f'new_{t}day_users':new,f'relearned_{t}day_users':relearn})
            source=overall.loc[date] if s=='전체' else saved.loc[(s,date)]
            for col in ['inactive_2day_users','inactive_3day_users']:
                assert r[col]==source[col]
            assert r['start_3day_users']==source.start_3day_inactive_users
            assert r['new_3day_users']==source.new_3day_inactive_users
            assert r['relearned_3day_users']==source.relearned_after_3day_inactivity_users
            rows.append(r)
            # Disjoint gap strata at one snapshot, identical next-day observation window.
            for label,selection in [('정확히 2일',g==2),('3일 이상',g>=3)]:
                eligible=int(selection.sum())
                observed=j<3
                successes=int(a[mask,j+1][selection].sum()) if observed else None
                following.append(dict(segment=s,signal_date=date,next_date=f'2013-03-{9+j:02d}',
                    gap_group=label,eligible_users=eligible,nextday_users=successes,
                    nextday_rate=successes/eligible if observed and eligible else None,
                    observable=observed,observation_status='관측' if observed else '미관측'))
    frame=pd.DataFrame(rows)
    # Next-day group counts independently reconcile with the next date's state flow.
    for q in following:
        if q['observable']:
            nxt=next(x for x in rows if x['segment']==q['segment'] and x['date']==q['next_date'])
            if q['gap_group']=='정확히 2일':
                assert q['eligible_users']==nxt['start_2day_users']-nxt['start_3day_users']
                assert q['nextday_users']==nxt['relearned_2day_users']-nxt['relearned_3day_users']
            else:
                assert q['eligible_users']==nxt['start_3day_users']
                assert q['nextday_users']==nxt['relearned_3day_users']
    rank_summaries=[]
    for date in DATES:
        ix=(frame.date==date)&(frame.segment!='전체')
        for measure in ['users','rate']:
            for t in [2,3]:
                frame.loc[ix,f'rank_{t}day_{measure}']=frame.loc[ix,f'inactive_{t}day_{measure}'].rank(method='min',ascending=False)
            rank_summaries.append(dict(date=date,measure=measure,
                unchanged=bool((frame.loc[ix,f'rank_2day_{measure}']==frame.loc[ix,f'rank_3day_{measure}']).all()),
                changed_segments=frame.loc[ix&(frame[f'rank_2day_{measure}']!=frame[f'rank_3day_{measure}']),'segment'].tolist()))
        for col in ['cohort_users','inactive_2day_users','inactive_3day_users','added_exact2_users']:
            assert frame.loc[ix,col].sum()==frame.loc[(frame.date==date)&(frame.segment=='전체'),col].iloc[0]
    # The additional end-of-follow-up users are all last active on Mar 09.
    added=u.loc[gap[:,-1]==2,['user_id','segment','active_days','words_seen','followup_active_days','first_return_date']].copy()
    added['as_of_utc_date']='2013-03-11'
    added['last_observed_learning_date']='2013-03-09'
    added['inactive_calendar_days']=2
    added['inactive_under_2day_rule']=1
    added['inactive_under_3day_rule']=0
    added['meaning']='역사적 분석 후보; 캠페인 대상 확정 아님'
    assert len(added)==4798 and added.user_id.is_unique
    assert added.followup_active_days.ge(1).all()
    final=frame[frame.date.eq(DATES[-1])].copy()
    # Missing ranks for the pooled overall group must stay null in JSON.
    records=json.loads(frame.to_json(orient='records',force_ascii=False,double_precision=15))
    final_records=json.loads(final.to_json(orient='records',force_ascii=False,double_precision=15))
    pools=[]
    for s in ['습관 형성형','꾸준형']:
        r=next(r for r in final_records if r['segment']==s)
        pools.append(dict(segment=s,exact1_users=r['exact1_users'],exact2_users=r['added_exact2_users'],
            inactive3plus_users=r['inactive_3day_users'],inactive2plus_users=r['inactive_2day_users'],
            inactive1or2_users=r['exact1_users']+r['added_exact2_users']))
    paused=[r for r in final_records if r['segment'] in ['멈춤-꾸준형','멈춤-몰입형']]
    pools.append(dict(segment='멈춤-꾸준형 + 멈춤-몰입형',
        inactive3plus_users=sum(r['inactive_3day_users'] for r in paused),
        inactive2plus_users=sum(r['inactive_2day_users'] for r in paused),
        exact2_users=sum(r['added_exact2_users'] for r in paused)))
    checks=dict(source_hashes_match=True,baseline_users_unique=True,panel_keys_unique=True,
                reconstructed_gaps_match_saved_panel=True,final_gaps_match_user_table=True,
                thresholds_nested=True,threshold_difference_equals_exact2=True,
                both_threshold_state_flows_reconcile=True,consecutive_day_state_continuity=True,
                saved_daily_counts_and_3day_flows_match=True,segment_totals_reconcile=True,
                nextday_end_date_unobserved=True,added_candidates_unique=True,
                added_candidates_previously_returned=True,nextday_counts_match_next_date_flows=True)
    assert all(r['nextday_users'] is None for r in following if not r['observable'])
    result=dict(analysis_date='2026-10-13',as_of_date='2013-03-11',baseline_users=len(u),
      source_hashes=hashes,checks=checks,daily=records,final=final_records,
      nextday=following,rank_comparison=rank_summaries,operating_pools=pools,
      definitions={'inactivity':'No recorded learning on at least 2 or 3 consecutive UTC calendar dates at end of day; baseline last learning date included.',
        'added_users':'Exactly 2 inactive calendar dates; nested difference between >=2 and >=3 at the same snapshot.',
        'rank':'Separate descending ranks by headcount and within-segment inactivity rate; ties use minimum rank. Not a marketing ROI ranking.',
        'flow':'Previous end-of-day stock + newly crossing threshold - relearned today = current stock. Not cumulative unique churn.',
        'nextday':'Next-day observed relearning for disjoint exactly-2 and >=3 gap groups at the same snapshot. No campaign intervention is recorded.',
        'nextday_pooling':'Date-specific estimates only; do not pool repeated user-days as independent users. March 11 next-day outcome is unavailable.'})
    (OUT/'sensitivity_results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    frame.to_csv(OUT/'daily_threshold_comparison.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    final.to_csv(OUT/'final_threshold_comparison.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    pd.DataFrame(following).to_csv(OUT/'nextday_relearning_by_gap.csv',index=False,encoding='utf-8-sig',float_format='%.12g')
    added.to_csv(OUT/'additional_2day_candidates.csv',index=False,encoding='utf-8-sig')
    write_report(result)
    print(json.dumps({'final':final_records,'ranks':rank_summaries,'pools':pools,'checks':checks},ensure_ascii=False,indent=2))


def write_report(r):
    lines=['# 2일·3일 비활동 기준 민감도 분석','','분석일: 2026-10-13. 기준집단: 2013-03-01~07 학습자 82,467명, 6개 고정 세그먼트. 추적: 03-08~11 UTC.',
      '', '## 1. 핵심 결과', '',
      '- 3/11 종료 기준으로 3일 비활동자는 58,758명(71.3%), 2일 비활동자는 63,556명(77.1%)이다. 2일 기준은 4,798명, 전체 기준집단 대비 5.82%p를 추가한다. 3일 기준 인원 대비 증가율은 8.17%다.',
      '- 3일 비활동 집단은 2일 비활동 집단의 부분집합이다. 추가되는 4,798명은 정확히 2일 비활동 사용자이며, 3/9에 마지막으로 학습하고 3/10·11에 기록이 없는 사람이다.',
      '- 종료일의 세그먼트별 인원 순위와 비활동률 순위는 각각 두 기준에서 동일하다. 이는 대상 규모·비율 순위의 안정성이며 캠페인 효과나 투자수익 순위의 안정성을 뜻하지 않는다.',
      '- 추가 인원은 습관 형성형 1,281명으로 가장 많다. 기존 3일 대상 대비 증가율은 꾸준형이 31.7%로 가장 크다.',
      '', '## 2. 종료일 세그먼트 비교', '',
      '분모는 각 세그먼트의 기준 인원 전체다. 날짜별 신규 이탈 인원이나 영구 이탈률이 아니다.', '',
      '| 세그먼트 | 기준 인원 | 3일 이상 인원 | 3일 비율 | 2일 이상 인원 | 2일 비율 | 추가 인원 | 증가 %p | 기존 대상 대비 증가 |',
      '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for x in r['final']:
        lines.append(f"| {x['segment']} | {x['cohort_users']:,} | {x['inactive_3day_users']:,} | {x['inactive_3day_rate']:.1%} | {x['inactive_2day_users']:,} | {x['inactive_2day_rate']:.1%} | {x['added_exact2_users']:,} | {x['added_pp']:.2f} | {x['relative_expansion']:.1%} |")
    lines += ['', '종료일 인원 순위(두 기준 공통): 멈춤-저활동형 > 최근 단발형 > 습관 형성형 > 멈춤-몰입형 > 꾸준형 > 멈춤-꾸준형.',
      '', '종료일 비활동률 순위(두 기준 공통): 멈춤-저활동형 > 멈춤-몰입형 > 최근 단발형 > 멈춤-꾸준형 > 습관 형성형 > 꾸준형.',
      '', '## 3. 날짜에 따른 민감도', '',
      '| 날짜 | 3일 이상 | 2일 이상 | 추가 인원 | 추가 비율 %p | 인원 순위 변화 | 비율 순위 변화 |', '|---|---:|---:|---:|---:|---|---|']
    for x in [x for x in r['daily'] if x['segment']=='전체']:
        ranks=[next(q for q in r['rank_comparison'] if q['date']==x['date'] and q['measure']==m) for m in ['users','rate']]
        status=['없음' if q['unchanged'] else ', '.join(q['changed_segments']) for q in ranks]
        lines.append(f"| {x['date']} | {x['inactive_3day_users']:,} | {x['inactive_2day_users']:,} | {x['added_exact2_users']:,} | {x['added_pp']:.2f} | {status[0]} | {status[1]} |")
    lines += ['', '매일의 대상 집합은 서로 겹치므로 날짜별 인원을 합해 고유 사용자 수로 해석하지 않는다. 종료 시점 차이만 보고 전 기간에서 차이가 작다고 판단하지 않는다.',
      '', '## 4. 정확히 2일 비활동자의 다음날 재학습', '',
      '각 날짜 종료 시점에서 정확히 2일 비활동 집단과 3일 이상 비활동 집단을 나눠 다음날 실제 학습을 비교했다. 서로 겹치지 않는 집단이며 동일 날짜에서만 비교한다. 이 자료에서 개입 여부는 알 수 없으므로 자연 복귀율 또는 캠페인 반응률로 단정하지 않는다.', '',
      '| 신호 기준일 | 다음 관측일 | 정확히 2일: 학습/대상 | 다음날 학습률 | 3일 이상: 학습/대상 | 다음날 학습률 |', '|---|---|---:|---:|---:|---:|']
    for d in DATES:
        pair=[next(x for x in r['nextday'] if x['segment']=='전체' and x['signal_date']==d and x['gap_group']==g) for g in ['정확히 2일','3일 이상']]
        a,b=pair
        if a['observable']:
            lines.append(f"| {d} | {a['next_date']} | {a['nextday_users']:,}/{a['eligible_users']:,} | {a['nextday_rate']:.1%} | {b['nextday_users']:,}/{b['eligible_users']:,} | {b['nextday_rate']:.1%} |")
        else:
            lines.append(f"| {d} | {a['next_date']} | 미관측 (대상 {a['eligible_users']:,}) | — | 미관측 (대상 {b['eligible_users']:,}) | — |")
    lines += ['', '2일 기준으로 추가되는 사용자 중 일부는 다음날 학습했다. 따라서 2일 신호를 확정 이탈로 해석할 수 없다. 날짜별 차이에는 세그먼트 구성과 기존 활동 이력이 작용할 수 있으며, 3일째까지 기다리는 정책과 2일째 개입하는 정책의 인과 효과를 비교한 결과가 아니다. 세그먼트별 분자·분모는 엑셀과 CSV에 함께 제공했다.',
      '', '## 5. 기존 액션 후보에 미치는 영향', '',
      '- 습관 형성형: 3일 이상 8,549명 → 2일 이상 9,830명, +1,281명(+15.0%). 기존 1~2일 비활동 후보 2,902명은 정확히 1일 1,621명과 정확히 2일 1,281명으로 나뉜다. 2일 기준으로 운영하면 이 1,281명이 단계 사이에서 이동한다. 두 단계에 중복 배정하지 않는다.',
      '- 멈춤-꾸준형·멈춤-몰입형: 3일 이상 9,520명 → 2일 이상 10,287명, +767명(+8.1%). 복귀 안내 검토 대상 규모가 증가한다.',
      '- 꾸준형: 3일 이상 2,559명 → 2일 이상 3,370명, +811명(+31.7%). 기존 1~2일 비활동 후보 2,280명은 정확히 1일 1,469명과 정확히 2일 811명이다. 짧은 휴식도 비활동에 포함시키는 영향이 상대적으로 크다.',
      '', '제안: 정확히 2일은 조기 관찰 단계, 3일 이상은 지속 비활동 단계로 함께 표시한다. 어느 단계에서 실제 개입할지는 세그먼트별 무작위 실험과 비용·가드레일로 결정한다. 3일이 최적 임계값이라는 결론은 내리지 않는다. 이번 분석은 기존 CRM 후보 파일을 변경하지 않았다.',
      '', '## 6. 검증과 한계', '',
      '- 원천 CSV 4개 해시를 기존 v3 기록과 대조했다. 사용자별 마지막 기준 주간 학습일과 4일 활동으로 비활동 일수를 재계산하고 329,868행 패널과 대조했다.',
      '- 두 임계값 모두 전일 비활동 + 신규 신호 − 당일 재학습 = 당일 종료 비활동의 상태 흐름을 검증했다. 세그먼트 합계, 기존 3일 상태 흐름, 부분집합 관계와 추가 4,798명의 고유성을 검증했다.',
      '- 기준 주간부터 쉬던 사용자도 포함한다. 2일·3일은 연속 UTC 달력 날짜 기준으로 정확한 48시간·72시간과 다르다.',
      '- 임계값별 집단은 중첩되므로 독립 두 집단 검정을 적용하지 않았다. 순위는 인원·비율 각각의 내림차순이며 동점은 최소 순위다. 별도 종합점수나 효과 순위를 만들지 않았다.',
      '- 다음날 학습 비교는 날짜별로만 제시한다. 같은 사용자가 여러 날짜에 나타날 수 있어 사용자-날짜를 독립 표본처럼 합쳐 추론하지 않았다. 3/11 다음날은 완전 관측이 안 되므로 제외했다.',
      '- 관측된 기록의 부재는 서비스 전체 활동의 부재 또는 영구 이탈을 입증하지 않는다. 장기 지속과 개입 효과는 후속 검증 대상이다.',
      '', '## 7. 파일과 후속 작업', '',
      '- 비활동_2일3일_민감도분석.xlsx: 종료일 비교·날짜별 신호·다음날 재학습.',
      '- final_threshold_comparison.csv, daily_threshold_comparison.csv: 인원·비율·순위와 두 임계값의 상태 흐름.',
      '- nextday_relearning_by_gap.csv: 날짜·세그먼트·비활동 기간별 다음날 재학습.',
      '- additional_2day_candidates.csv: 3/11 시점에 2일 기준으로만 포함되는 4,798명의 역사적 분석 목록.',
      '- sensitivity_results.json: 정의·결과·원천 해시·계산 검증.',
      '', '요청한 3번(2일·3일 비활동 민감도 비교)을 완료했다. 다음은 기준 주간의 복습 규칙성과 이후 반복학습의 관계를 활동일 수·학습량 등을 고려해 분석하는 단계다.', '']
    (OUT/'비활동_기준_민감도_결과와해석.md').write_text('\n'.join(lines),encoding='utf-8')


if __name__=='__main__':
    main()
