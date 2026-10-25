from pathlib import Path
import os,sys,runpy,json,hashlib,contextlib
ROOT=Path(__file__).resolve().parent
os.environ['OMP_NUM_THREADS']='1'
os.environ['OPENBLAS_NUM_THREADS']='1'
os.environ['MKL_NUM_THREADS']='1'
sys.path.append(str(ROOT/'tmp'/'python_deps'))
import pandas as pd
import numpy as np
from sklearn.cluster import KMeans  # Dependency preflight before reading the CSV.

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    segdir=ROOT/'segmentation'
    previous=ROOT.parent/'cohort_v1'
    oldmeta=json.loads((previous/'manifest.json').read_text(encoding='utf-8'))
    raw=ROOT.parent/'learning_traces.13m.csv'/'learning_traces.13m.csv'
    raw_hash=sha(raw)
    oldresults=json.loads((previous/'results.json').read_text(encoding='utf-8'))
    assert raw_hash==oldresults['quality']['source_sha256']
    print('Running the supplied code, with only the source path adapted.',flush=True)
    os.chdir(segdir)
    with (segdir/'execution_log.txt').open('w',encoding='utf-8') as log:
        with contextlib.redirect_stdout(log):
            ns=runpy.run_path(str(segdir/'segment_code_local.py'))
    u=ns['user'].copy()
    old=pd.read_csv(previous/'user_cohort.csv').set_index('user_id')
    assert set(u.index)==set(old.index) and len(u)==82467
    for col in ['active_days','words_seen','words_correct','sessions','recency','R','F']:
        np.testing.assert_allclose(u[col].to_numpy(),old.loc[u.index,col].to_numpy(),rtol=0,atol=1e-10)
    assert u.groupby('words_seen').M.nunique().max()==1
    assert u.segment.nunique()==6
    rest=u[u.segment=='멈춤-저활동형']
    assert rest.R.le(3).all() and rest.F.le(2).all() and rest.M.le(3).all()
    inputs=ROOT/'cohort_inputs';inputs.mkdir(exist_ok=True)
    # Keep previous time-axis fields, replace all scoring/labels with the executed code outputs.
    current=u.reset_index()
    current['first_observed_in_baseline']=current.first_active.dt.strftime('%Y-%m-%d')
    current['first_active']=current.first_active.dt.strftime('%Y-%m-%d')
    current['last_active']=current.last_active.dt.strftime('%Y-%m-%d')
    current['segment_asof_utc']='2013-03-08T00:00:00Z'
    current['baseline_sustained']=current.active_days>=4
    for col in ['active_2013-03-08','active_2013-03-09','active_2013-03-10','active_2013-03-11',
                'followup_active_days','returned_4d','returned_2plus_days']:
        current[col]=current.user_id.map(old[col])
    assert current.returned.astype(int).eq(current.returned_4d).all()
    day=pd.read_csv(previous/'user_daily_activity.csv')
    day['segment']=day.user_id.map(u.segment)
    assert day.segment.notna().all()
    summary=current.groupby('segment',sort=False).agg(users=('user_id','size'),
        returned_4d_users=('returned_4d','sum'),returned_2plus_days_users=('returned_2plus_days','sum')).reindex(ns['SEG_ORDER']).reset_index()
    frames={'user_cohort.csv':current,'user_daily_activity.csv':day,'segment_cohort_summary.csv':summary}
    for name,df in frames.items():df.to_csv(inputs/name,index=False,encoding='utf-8-sig')
    m={'files':{name:{'sha256':sha(inputs/name),'rows':len(df)} for name,df in frames.items()}}
    (inputs/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
    (inputs/'results.json').write_text(json.dumps({'analysis':{'segment_reference':str(segdir/'segment_code_provided.py')},
        'source_sha256':raw_hash,'segments':ns['SEG_ORDER']},ensure_ascii=False,indent=2),encoding='utf-8')
    changes=pd.DataFrame({'user_id':u.index,'old_segment':old.loc[u.index,'segment'].to_numpy(),
        'new_segment':u.segment.to_numpy(),'old_M':old.loc[u.index,'M'].to_numpy(),'new_M':u.M.to_numpy(),
        'words_seen':u.words_seen.to_numpy()})
    changes.to_csv(segdir/'segment_change_audit.csv',index=False,encoding='utf-8-sig')
    oldmap={'핵심 학습자':'꾸준형','습관 형성 중':'습관 형성형','최근 1일 학습':'최근 단발형',
        '중단 위험':'멈춤-꾸준형','몰입 후 이탈':'멈춤-몰입형','초반 이탈':'멈춤-저활동형','중반 이탈':'멈춤-저활동형'}
    changed=int((changes.old_segment.map(oldmap)!=changes.new_segment).sum())
    audit={'provided_code_executed':True,'only_supplied_code_change':'source CSV path',
        'm_quantile_edges':ns['m_edges'].tolist(),'segment_order':ns['SEG_ORDER'],
        'baseline_users':len(u),'all_previous_baseline_values_match':True,'equal_amount_equal_M':True,
        'membership_changes_after_name_mapping':changed,'M_score_changed_users':int((changes.old_M!=changes.new_M).sum()),
        'selected_k':ns['best_k'],'ARI':float(ns['ari']),
        'packages':{'pandas':pd.__version__,'numpy':np.__version__,'sklearn':__import__('sklearn').__version__},
        'source_sha256':raw_hash,'segment_summary':summary.to_dict('records')}
    (segdir/'revision_validation.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2),encoding='utf-8')
    print(summary.to_string(index=False),flush=True)
    print(json.dumps({k:v for k,v in audit.items() if k!='segment_summary'},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
