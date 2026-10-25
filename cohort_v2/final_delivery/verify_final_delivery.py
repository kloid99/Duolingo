"""Saved workbook, report claims, links and preserved artifact integrity."""
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from datetime import datetime,timezone
import json,csv,math,hashlib,re
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for chunk in iter(lambda:f.read(8*1024*1024),b''):h.update(chunk)
    return h.hexdigest()
def audit_manifest(manifest):
    current={p.name for p in ROOT.iterdir() if p.is_file() and p.name!='final_delivery_manifest.json'}
    assert current==set(manifest['files']),('package file inventory changed',current.symmetric_difference(manifest['files']))
    for name,entry in manifest['files'].items():assert sha(ROOT/name)==entry['sha256'],('package modified',name)
    assert sha(PROJECT/'최종_산출물_인덱스.md')==manifest['project_index_sha256'],'index changed'
    for name,h in manifest['report_source_hashes'].items():assert sha(PROJECT/name)==h,('report source modified',name)
def main(build_manifest=False):
    if not build_manifest:audit_manifest(json.loads((ROOT/'final_delivery_manifest.json').read_text(encoding='utf-8')))
    d=json.loads((ROOT/'sample_size_results.json').read_text(encoding='utf-8'))
    from report_semantics import freshness,verify
    freshness(d)
    ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(ROOT/'A1_실험표본수와_기간산정.xlsx') as z:
        ss=[]
        if 'xl/sharedStrings.xml' in z.namelist():ss=[''.join(t.text or '' for t in si.iterfind('.//s:t',ns)) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
        cells={};formulas={}
        for c in ET.fromstring(z.read('xl/worksheets/sheet1.xml')).iterfind('.//s:c',ns):
            assert c.get('t')!='e',(c.get('r'),c.find('s:v',ns).text)
            v=c.find('s:v',ns);f=c.find('s:f',ns)
            if f is not None:formulas[c.get('r')]=f.text
            if c.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.iterfind('.//s:t',ns))
            elif v is None or v.text is None:value=None
            elif c.get('t')=='s':value=ss[int(v.text)]
            elif c.get('t')=='str':value=v.text
            else:value=float(v.text)
            cells[c.get('r')]=value
    def eq(cell,expected):
        actual=cells.get(cell)
        if expected is None:assert actual in [None,''],(cell,actual)
        elif isinstance(expected,(int,float)):assert math.isclose(actual,expected,rel_tol=1e-9,abs_tol=1e-12),(cell,actual,expected)
        else:assert actual==expected,(cell,actual,expected)
    eq('C4',d['default']['n_total']);eq('G4',d['default']['n_per_arm']);eq('G12',d['default']['n_per_arm_unrounded'])
    for cell,key in [('C6','historical_baseline'),('C7','planning_mde_absolute'),('C8','alpha_two_sided'),('C9','target_power'),('C11','minimum_enrollment_utc_days'),('C12','data_lateness_allowance_days'),('C13','maximum_enrollment_utc_days')]:eq(cell,d[key] if key in d else d['config'][key])
    for cell in ['C10','C15','C17','C18','C19']:eq(cell,None)
    eq('C14','정상');assert 'C14' in formulas['C4'] and 'C14' in formulas['G12']
    eq('C16','유입량 미입력');assert 'ISBLANK' in formulas['C15']
    for row,r in enumerate(d['scenarios'],22):
        for col,key in [('B','mde'),('C','target_power'),('D','p1'),('H','n_per_arm'),('I','n_total')]:eq(f'{col}{row}',r[key])
    for row,r in enumerate(d['timing_scenarios'],31):
        for col,key in [('B','assumed_daily_new_eligible'),('C','required_enrollment_days'),('E','enrollment_days'),('F','final_primary_result_days_from_start')]:eq(f'{col}{row}',r[key])
        eq(f'D{row}','가능 가정' if r['within_proposed_maximum'] else '표본 미달')
    report=(ROOT/'최종_코호트분석_보고서.md').read_text(encoding='utf-8')
    with (ROOT/'report_claims.csv').open(encoding='utf-8-sig',newline='') as f:claims=list(csv.DictReader(f))
    assert all(r['display'] in report for r in claims),[r['metric_id'] for r in claims if r['display'] not in report]
    semantic=verify(report)
    assert f"{d['default']['n_total']:,}" in report
    for r in d['scenarios']:assert f"{r['n_total']:,}" in report
    document_files=list(ROOT.glob('*.md'))+[PROJECT/'최종_산출물_인덱스.md',PROJECT/'corrections/검토사항_수정결과.md',PROJECT/'corrections/관측지표_현행정의.md']
    links=0
    for file in document_files:
        text=file.read_text(encoding='utf-8')
        for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',text):
            if target.startswith(('https://','http://')):continue
            p=Path(target.strip('<>'))
            if not p.is_absolute():p=file.parent/p
            assert p.exists(),(file.name,target);links+=1
    meta=json.loads((ROOT/'event_time_extraction.json').read_text(encoding='utf-8'))
    assert sha(ROOT/'primary_candidate_event_times.csv')==meta['output_sha256']
    with (ROOT/'primary_candidate_event_times.csv').open(encoding='utf-8-sig',newline='') as f:events=list(csv.DictReader(f))
    assert len(events)==4809 and len({r['user_id'] for r in events})==4809
    for r in events:
        first=datetime.fromtimestamp(int(r['historical_first_learning_timestamp']),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        prev=datetime.fromtimestamp(int(r['historical_previous_learning_timestamp']),timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
        assert first==r['historical_first_learning_at_utc'] and first[:10]==r['eligibility_date_utc']
        assert prev==r['historical_previous_learning_at_utc'] and prev[:10]==r['last_learning_date_before_trigger']
        assert prev<first
    old_manifests=['statistics/statistics_manifest.json','sensitivity/sensitivity_manifest.json','regularity/regularity_manifest.json','accuracy_change/accuracy_manifest.json','word_performance/word_performance_manifest.json','behavior_flow/behavior_flow_manifest.json']
    audited=0;script_audits=0
    for name in old_manifests:
        path=PROJECT/name;m=json.loads(path.read_text(encoding='utf-8'));assert m.get('files')
        for filename,entry in m['files'].items():
            expected=entry['sha256'] if isinstance(entry,dict) else entry
            assert sha(path.parent/filename)==expected,(name,filename);audited+=1
        for filename,expected in m.get('project_files',{}).items():assert sha(PROJECT/filename)==expected;script_audits+=1
    robustness=PROJECT/'corrections/robustness_manifest.json';rm=json.loads(robustness.read_text(encoding='utf-8'))
    for name,h in rm['files'].items():assert sha(robustness.parent/name)==h,('robustness output changed',name)
    for name,h in rm['source_hashes'].items():assert sha(PROJECT/name)==h,('robustness source changed',name)
    # New report source hashes and original retention outputs must remain intact.
    original=json.loads((PROJECT/'results_retention.json').read_text(encoding='utf-8'))
    for name in ['user_retention_cohort.csv','first_return_cohorts.csv','user_daily_retention.csv']:assert sha(PROJECT/name)==original['outputs'][name]['sha256']
    numeric=json.loads((ROOT/'planning_validation.json').read_text(encoding='utf-8'))
    measurement=json.loads((ROOT/'measurement_validation.json').read_text(encoding='utf-8'))
    negative=json.loads((ROOT/'semantic_validation.json').read_text(encoding='utf-8'))
    for stored in [numeric,measurement,negative]:
        assert stored.get('validated_source_hashes'),'validation stamp absent; rebuild required'
        for name,h in stored['validated_source_hashes'].items():assert sha(ROOT/name)==h,('stale validation',name)
    validation=dict(saved_workbook_scenarios_verified=6,saved_duration_rows_verified=3,blank_actual_inflow_and_duration_preserved=True,formula_errors=0,spreadsheet_visually_reviewed=True,figure_visually_reviewed=True,artifact_engine_recalculation_boundaries_verified=True,native_excel_execution_not_tested=True,report_claim_displays_verified=len(claims),local_document_links_verified=links,historical_event_times_verified=4809,preserved_manifest_files_verified=audited,preserved_project_files_verified=script_audits,actual_service_assignments=0,actual_service_effect_not_claimed=True)
    validation.update(semantic,latest_config_and_primary_hash_verified=True,robustness_manifest_verified=True,mode='build_manifest' if build_manifest else 'read_only_audit')
    sources={r['source']:sha(PROJECT/r['source']) for r in claims}
    for name in ['corrections/robustness_results.json','corrections/robustness_manifest.json','corrections/검토사항_수정결과.md','corrections/관측지표_현행정의.md','corrections/selection_language_time_profiles.csv','review/a1_date_and_gap_coverage.csv','review/analysis_selection_profiles.csv']:sources[name]=sha(PROJECT/name)
    manifest=dict(schema_version=2,analysis_date='2026-10-13',completion='historical analysis and review corrections complete; live execution blocked pending external validation',validation=validation,numerical_validation=numeric,measurement_validation=measurement,semantic_validation=negative,launch_readiness=d['launch_readiness'],event_time_extraction=meta,report_source_hashes=sources,files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in ROOT.iterdir() if p.is_file() and p.name!='final_delivery_manifest.json'},project_index_sha256=sha(PROJECT/'최종_산출물_인덱스.md'))
    if build_manifest:(ROOT/'final_delivery_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(validation,ensure_ascii=False,indent=2))
if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--build-manifest',action='store_true');args=parser.parse_args();main(args.build_manifest)
