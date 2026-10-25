"""Planning validity is separate from live-launch readiness."""
import json,math,argparse
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def validate(config):
    p=config['historical_baseline_successes']/config['historical_baseline_n'];m=config['planning_mde_absolute']
    if not 0<p<p+m<1:raise ValueError('baseline + MDE must be below 1')
    if not 0<config['alpha_two_sided']<1 or not .5<config['target_power']<1:raise ValueError('invalid alpha/power')
    for k in ['minimum_enrollment_utc_days','maximum_enrollment_utc_days','data_lateness_allowance_days']:
        if type(config[k]) is not int or config[k]<0:raise ValueError('nonnegative integer days required')
    if not 1<=config['minimum_enrollment_utc_days']<=config['maximum_enrollment_utc_days']:raise ValueError('max enrollment must be >= min >= 1')
    if config['outcome_day_offsets']!=[1,2]:raise ValueError('primary offsets changed; redefine analysis first')
    if config['secondary_day_offsets']!=list(range(1,8)) or config['secondary_minimum_active_days']!=4:raise ValueError('secondary definition changed')
    rate=config['actual_new_eligible_users_per_day']
    if rate is not None and (type(rate) not in [int,float] or not math.isfinite(rate) or rate<=0):raise ValueError('positive actual inflow required')
    return True
def readiness(config):
    validate(config)
    required=['service_event_contract_verified','coverage_and_identity_verified','target_baseline_recalibrated','business_mde_approved','guardrail_thresholds_approved','actual_pool_and_inflow_verified','card_usability_and_date_choices_verified','assignment_and_exposure_integration_verified']
    pending=[k for k in required if config['launch_gates'].get(k) is not True]
    if config['actual_launch_date'] is None:pending.append('actual_launch_date')
    if config['actual_new_eligible_users_per_day'] is None:pending.append('actual_new_eligible_users_per_day')
    return dict(ready=not pending,pending=pending,status='blocked_pending_external_validation' if pending else 'ready_for_launch_review')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--require-ready',action='store_true');a=p.parse_args()
    result=readiness(json.loads((ROOT/'experiment_config.json').read_text(encoding='utf-8')))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    if a.require_ready and not result['ready']:raise SystemExit(2)
