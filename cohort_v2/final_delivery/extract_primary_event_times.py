"""Resolve historical A1 first-event timestamps without inventing lesson/assignment logs."""
from pathlib import Path
import json,hashlib
import pandas as pd
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
RAW=PROJECT.parent/'learning_traces.13m.csv'/'learning_traces.13m.csv'
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()
def main():
    candidates=pd.read_csv(PROJECT/'behavior_flow/primary_candidate_eligibility.csv')
    assert len(candidates)==4809 and candidates.user_id.is_unique
    wanted=set(candidates.user_id);begin=int(pd.Timestamp('2013-03-08',tz='UTC').timestamp());end=begin+4*86400
    baseline_begin=begin-7*86400
    prior=json.loads((PROJECT/'word_performance/word_performance_results.json').read_text(encoding='utf-8'))
    raw_hash=sha(RAW);assert raw_hash==prior['source_hashes']['raw_csv']
    output=ROOT/'primary_candidate_event_times.csv'
    metadata=ROOT/'event_time_extraction.json'
    if output.exists() and metadata.exists():
        old=json.loads(metadata.read_text(encoding='utf-8'))
        if old['raw_sha256']==raw_hash and old['candidate_sha256']==sha(PROJECT/'behavior_flow/primary_candidate_eligibility.csv') and old['output_sha256']==sha(output):
            print('Verified historical event-time cache',flush=True);return
    first={};last={};read=0
    for chunk in pd.read_csv(RAW,usecols=['user_id','timestamp'],dtype={'user_id':'str'},chunksize=1000000):
        read+=len(chunk);q=chunk[chunk.user_id.isin(wanted)]
        for uid,ts in q[q.timestamp.ge(begin)&q.timestamp.lt(end)].groupby('user_id').timestamp.min().items():first[uid]=min(first.get(uid,ts),ts)
        for uid,ts in q[q.timestamp.ge(baseline_begin)&q.timestamp.lt(begin)].groupby('user_id').timestamp.max().items():last[uid]=max(last.get(uid,ts),ts)
        print(f'Rows read: {read:,}',flush=True)
    assert read==12854226 and set(first)==set(last)==wanted
    c=candidates.copy();c['historical_first_learning_timestamp']=c.user_id.map(first).astype('int64')
    c['historical_first_learning_at_utc']=pd.to_datetime(c.historical_first_learning_timestamp,unit='s',utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    c['historical_previous_learning_timestamp']=c.user_id.map(last).astype('int64')
    c['historical_previous_learning_at_utc']=pd.to_datetime(c.historical_previous_learning_timestamp,unit='s',utc=True).dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    assert (c.historical_first_learning_at_utc.str[:10]==c.eligibility_date_utc).all()
    assert (c.historical_previous_learning_at_utc.str[:10]==c.last_learning_date_before_trigger).all()
    assert (c.historical_previous_learning_timestamp<c.historical_first_learning_timestamp).all()
    c['record_meaning']='역사적 첫 학습 기록. 레슨 완료·실험 배정·화면 노출 기록은 아님'
    c.to_csv(output,index=False,encoding='utf-8-sig')
    result=dict(raw_rows=read,candidate_users=len(c),raw_sha256=raw_hash,candidate_sha256=sha(PROJECT/'behavior_flow/primary_candidate_eligibility.csv'),output_sha256=sha(output),checks=dict(all_candidate_ids_resolved=True,first_event_dates_match=True,previous_event_dates_match=True,previous_events_before_trigger=True),timestamp_semantics='minimum raw learning timestamp within fixed followup, not lesson completion or assignment')
    metadata.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
