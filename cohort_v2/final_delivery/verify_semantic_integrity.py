"""In-memory negative tests; never corrupt the published report/config."""
import json,sys,copy
from report_semantics import ROOT,verify,freshness
from validate_experiment_config import validate,readiness
report=(ROOT/'최종_코호트분석_보고서.md').read_text(encoding='utf-8');plan=json.loads((ROOT/'sample_size_results.json').read_text(encoding='utf-8'));config=json.loads((ROOT/'experiment_config.json').read_text(encoding='utf-8'))
passed=0;verify(report);freshness(plan);validate(config)
def rejected(callback):
    global passed
    try:callback()
    except (AssertionError,ValueError):passed+=1;return
    raise AssertionError('invalid mutation was accepted')
swapped=report.replace('| 꾸준형 |','| TEMP |').replace('| 최근 단발형 |','| 꾸준형 |').replace('| TEMP |','| 최근 단발형 |')
rejected(lambda:verify(swapped))
rejected(lambda:verify(report.replace('추적 기록 없음(명)','추적 기록 없음(%)')))
rejected(lambda:verify(report.replace('기준 주간 2013-03-01~07 UTC','기준 주간 2013-03-02~08 UTC')))
rejected(lambda:verify(report.replace('분모는 모든 배정 사용자','분모는 노출 사용자')))
rejected(lambda:verify(report.replace('| D1만 |','| D2만 |')))
changed=copy.deepcopy(config);changed['planning_mde_absolute']=.04;rejected(lambda:freshness(plan,changed))
rejected(lambda:freshness(plan,config,'0'*64))
changed_plan=copy.deepcopy(plan);changed_plan['source_hashes']['primary_candidate_outcomes.csv']='0'*64;rejected(lambda:freshness(changed_plan))
for key,value in [('maximum_enrollment_utc_days',7),('target_power',.5),('planning_mde_absolute',.6),('data_lateness_allowance_days',-1),('actual_new_eligible_users_per_day',0)]:
    c=copy.deepcopy(config);c[key]=value;rejected(lambda c=c:validate(c))
assert not readiness(config)['ready'] and len(readiness(config)['pending'])==10
from verify_final_delivery import audit_manifest,sha,PROJECT
snapshot=dict(files={p.name:{'sha256':sha(p)} for p in ROOT.iterdir() if p.is_file() and p.name!='final_delivery_manifest.json'},project_index_sha256=sha(PROJECT/'최종_산출물_인덱스.md'),report_source_hashes={})
audit_manifest(snapshot)
modified=copy.deepcopy(snapshot);modified['files']['experiment_config.json']['sha256']='0'*64;rejected(lambda:audit_manifest(modified))
modified=copy.deepcopy(snapshot);modified['files'].pop('experiment_config.json');rejected(lambda:audit_manifest(modified))
result=dict(negative_mutations_rejected=passed,valid_report_and_fresh_config_accepted=True,launch_blocked_on_missing_external_inputs=True)
result['validated_source_hashes']={name:sha(ROOT/name) for name in ['verify_semantic_integrity.py','report_semantics.py','validate_experiment_config.py','verify_final_delivery.py','experiment_config.json','최종_코호트분석_보고서.md']}
if '--write-validation' in sys.argv:(ROOT/'semantic_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
