"""Reference ITT outcome calculation; accepts future logs, not historical invented arms."""
from datetime import datetime,timedelta,timezone,time
from zoneinfo import ZoneInfo
from collections import defaultdict
from statistics import NormalDist
import math,json,argparse
def utc(value):
    dt=datetime.fromisoformat(value.replace('Z','+00:00'))
    if dt.tzinfo is None:raise ValueError('timezone required')
    return dt.astimezone(timezone.utc)
def wilson(k,n):
    z=NormalDist().inv_cdf(.975);p=k/n;den=1+z*z/n
    center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return center-half,center+half
def allowed_plan_dates(eligibility_at_utc,display_timezone):
    d0=utc(eligibility_at_utc).replace(hour=0,minute=0,second=0,microsecond=0)
    start,end=d0+timedelta(days=1),d0+timedelta(days=3);tz=ZoneInfo(display_timezone)
    day=start.astimezone(tz).date();last=(end-timedelta(microseconds=1)).astimezone(tz).date();out=[]
    while day<=last:
        lo=datetime.combine(day,time.min,tzinfo=tz).astimezone(timezone.utc)
        hi=datetime.combine(day+timedelta(days=1),time.min,tzinfo=tz).astimezone(timezone.utc)
        a,b=max(start,lo),min(end,hi)
        if a<b:out.append(dict(local_date=day.isoformat(),allowed_start_local=a.astimezone(tz).isoformat(),allowed_end_exclusive_local=b.astimezone(tz).isoformat(),display_timezone=display_timezone))
        day+=timedelta(days=1)
    return out
def evaluate(assignments,events,coverage,freeze_at_utc,data_lateness_allowance_days=2):
    if type(data_lateness_allowance_days) is not int or data_lateness_allowance_days<0:raise ValueError('lateness must be nonnegative integer days')
    freeze=utc(freeze_at_utc);seen=set();users=set();ev={};by_user=defaultdict(list);cov={}
    versions=set();history=defaultdict(list)
    for c in coverage:
        if type(c['complete']) is not bool:raise ValueError('coverage complete must be boolean')
        datetime.strptime(c['date_utc'],'%Y-%m-%d')
        if type(c.get('version')) is not int or c['version']<1:raise ValueError('positive coverage version required')
        checked=utc(c['checked_at_utc']);day_end=utc(c['date_utc']+'T00:00:00Z')+timedelta(days=1)
        if checked<day_end:raise ValueError('coverage checked before date ended')
        key=(c['date_utc'],c['version'])
        if key in versions:raise ValueError('duplicate coverage version')
        versions.add(key);history[c['date_utc']].append((c['version'],checked,c['complete']))
    for day,entries in history.items():
        ordered=sorted(entries)
        if any(x[1]>y[1] for x,y in zip(ordered,ordered[1:])):raise ValueError('coverage version time decreased')
        known=[e for e in ordered if e[1]<=freeze]
        if known:cov[day]=known[-1][2]
    for e in events:
        if e['event_id'] in ev:
            if ev[e['event_id']]!=e:raise ValueError('conflicting event_id')
            continue
        ev[e['event_id']]=e
        if type(e['valid']) is not bool:raise ValueError('event valid must be boolean')
        occurred,received=utc(e['occurred_at_utc']),utc(e['received_at_utc'])
        if received<occurred:raise ValueError('received before occurrence')
        if e['valid'] and received<=freeze:by_user[e['user_id']].append(occurred)
    outcomes=[];counts={v:dict(n=0,successes=0,missing=0) for v in ['control','treatment']}
    experiments={a['experiment_id'] for a in assignments}
    if len(experiments)>1:raise ValueError('one experiment per evaluation')
    for a in assignments:
        uid=a['user_id'];variant=a['variant'];key=(a['experiment_id'],uid)
        if a['assignment_id'] in seen or key in users:raise ValueError('duplicate assignment/user')
        seen.add(a['assignment_id']);users.add(key)
        if variant not in counts:raise ValueError('invalid variant')
        eligibility,assigned=utc(a['eligibility_at_utc']),utc(a['assigned_at_utc'])
        if assigned<eligibility or assigned.date()!=eligibility.date():raise ValueError('assignment must follow eligibility on same UTC date')
        if assigned>freeze:raise ValueError('assignment after freeze')
        d0=eligibility.replace(hour=0,minute=0,second=0,microsecond=0);start=d0+timedelta(days=1);end=d0+timedelta(days=3)
        ready=end+timedelta(days=data_lateness_allowance_days)
        complete=freeze>=ready and all(cov.get((d0+timedelta(days=i)).date().isoformat(),False) for i in [1,2])
        y=int(any(start<=dt<end for dt in by_user[uid])) if complete else None
        counts[variant]['n']+=1
        counts[variant]['missing']+=int(y is None)
        counts[variant]['successes']+=int(y==1)
        secondary_end=d0+timedelta(days=8);secondary_ready=secondary_end+timedelta(days=data_lateness_allowance_days)
        secondary_complete=freeze>=secondary_ready and all(cov.get((d0+timedelta(days=i)).date().isoformat(),False) for i in range(1,8))
        active_dates=len({dt.date() for dt in by_user[uid] if start<=dt<secondary_end}) if secondary_complete else None
        outcomes.append(dict(assignment_id=a['assignment_id'],user_id=uid,variant=variant,outcome_start_utc=start.isoformat(),outcome_end_exclusive_utc=end.isoformat(),ready_at_utc=ready.isoformat(),y=y,fully_observed=complete,secondary_end_exclusive_utc=secondary_end.isoformat(),secondary_ready_at_utc=secondary_ready.isoformat(),secondary_active_days=active_dates,secondary_nsm=int(active_dates>=4) if active_dates is not None else None))
    for v,g in counts.items():
        g['rate']=g['successes']/g['n'] if g['n'] and not g['missing'] else None
        g['missing_value_bounds']=[g['successes']/g['n'],(g['successes']+g['missing'])/g['n']] if g['n'] else [None,None]
    c,t=counts['control'],counts['treatment'];result=dict(outcomes=outcomes,groups=counts,primary_test=None)
    if c['n'] and t['n']:
        result['difference_missing_bounds']=[t['missing_value_bounds'][0]-c['missing_value_bounds'][1],t['missing_value_bounds'][1]-c['missing_value_bounds'][0]]
        if c['missing']==t['missing']==0:
            pc,pt=c['rate'],t['rate'];diff=pt-pc;lt,ut=wilson(t['successes'],t['n']);lc,uc=wilson(c['successes'],c['n'])
            low=diff-math.sqrt((pt-lt)**2+(uc-pc)**2);high=diff+math.sqrt((ut-pt)**2+(pc-lc)**2)
            pooled=(t['successes']+c['successes'])/(t['n']+c['n'])
            expected=[pooled*c['n'],(1-pooled)*c['n'],pooled*t['n'],(1-pooled)*t['n']]
            if min(expected)>=5:
                se=math.sqrt(pooled*(1-pooled)*(1/c['n']+1/t['n']));z=diff/se;p=math.erfc(abs(z)/math.sqrt(2))
                result['primary_test']=dict(difference=diff,ci95_low=low,ci95_high=high,z=z,p_two_sided=p)
            else:result['primary_test']=dict(difference=diff,ci95_low=low,ci95_high=high,p_two_sided=None,reason='normal approximation requires expected cell counts >=5')
    result['secondary_groups']={v:dict(n=g['n'],missing=sum(r['secondary_nsm'] is None for r in outcomes if r['variant']==v),successes=sum(r['secondary_nsm']==1 for r in outcomes if r['variant']==v)) for v,g in counts.items()}
    for g in result['secondary_groups'].values():
        g['rate']=g['successes']/g['n'] if g['n'] and not g['missing'] else None
        g['missing_value_bounds']=[g['successes']/g['n'],(g['successes']+g['missing'])/g['n']] if g['n'] else [None,None]
    result['data_lateness_allowance_days']=data_lateness_allowance_days
    return result
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('input_json');parser.add_argument('--freeze-at',required=True);parser.add_argument('--output',required=True);args=parser.parse_args()
    with open(args.input_json,encoding='utf-8') as f:data=json.load(f)
    from pathlib import Path
    config=json.loads((Path(__file__).resolve().parent/'experiment_config.json').read_text(encoding='utf-8'))
    lag=config['data_lateness_allowance_days']
    if data.get('data_lateness_allowance_days',lag)!=lag:raise ValueError('input lateness differs from experiment config')
    out=evaluate(data['assignments'],data['learning_events'],data['coverage'],args.freeze_at,lag)
    with open(args.output,'w',encoding='utf-8') as f:json.dump(out,f,ensure_ascii=False,indent=2)
