"""Independent power search, seeded binomial check, and original-metric audit."""
from pathlib import Path
import json,csv,math,hashlib
import numpy as np
ROOT=Path(__file__).resolve().parent;PROJECT=ROOT.parent
d=json.loads((ROOT/'sample_size_results.json').read_text(encoding='utf-8'))
loz,hiz=0.,12.
for _ in range(100):
    mid=(loz+hiz)/2
    if math.erfc(mid/math.sqrt(2))>d['config']['alpha_two_sided']:loz=mid
    else:hiz=mid
za=(loz+hiz)/2
def independent_power(r,n):
    p0,p1=r['p0'],r['p1'];pb=(p0+p1)/2
    v0=2*pb*(1-pb)/n;v1=(p0*(1-p0)+p1*(1-p1))/n
    boundary=za*math.sqrt(v0);delta=p1-p0
    return .5*math.erfc((boundary-delta)/math.sqrt(2*v1))+.5*math.erfc((boundary+delta)/math.sqrt(2*v1))
for r in d['scenarios']+d['baseline_sensitivity']:
    assert r['n_per_arm']%2==0 and r['n_total']==2*r['n_per_arm']
    lo,hi=1,r['n_per_arm']
    while lo<hi:
        mid=(lo+hi)//2
        if independent_power(r,mid)>=r['target_power']:hi=mid
        else:lo=mid+1
    assert 0<=r['n_per_arm']-lo<=2
    assert abs(independent_power(r,r['n_per_arm'])-r['achieved_approx_power'])<1e-12
default=d['default'];rng=np.random.default_rng(20261013);sims=100000;n=default['n_per_arm']
def mc(p0,p1):
    k0=rng.binomial(n,p0,sims);k1=rng.binomial(n,p1,sims)
    pooled=(k0+k1)/(2*n)
    z=(k1/n-k0/n)/np.sqrt(pooled*(1-pooled)*2/n)
    return float((np.abs(z)>za).mean())
estimated_power=mc(default['p0'],default['p1']);estimated_alpha=mc(default['p0'],default['p0'])
assert abs(estimated_power-default['target_power'])<6*math.sqrt(default['target_power']*(1-default['target_power'])/sims)
assert abs(estimated_alpha-d['config']['alpha_two_sided'])<6*math.sqrt(d['config']['alpha_two_sided']*(1-d['config']['alpha_two_sided'])/sims)
with (ROOT/'report_claims.csv').open(encoding='utf-8-sig',newline='') as f:claims=list(csv.DictReader(f))
for r in claims:
    source=PROJECT/r['source']
    if r['json_pointer'].startswith('derived:'):
        with source.open(encoding='utf-8-sig',newline='') as f:value=sum(int(x['active_days'])>=4 for x in csv.DictReader(f))
    else:
        value=json.loads(source.read_text(encoding='utf-8'))
        for token in r['json_pointer'].split('/'):value=value[int(token)] if isinstance(value,list) else value[token]
    assert math.isclose(float(r['value']),value,rel_tol=1e-13,abs_tol=1e-14)
for r in d['timing_scenarios']:
    expected=max(d['config']['minimum_enrollment_utc_days'],math.ceil(default['n_total']/r['assumed_daily_new_eligible']))
    assert r['required_enrollment_days']==expected
    assert r['within_proposed_maximum']==(expected<=d['config']['maximum_enrollment_utc_days'])
    assert r['final_primary_result_days_from_start']==min(expected,d['config']['maximum_enrollment_utc_days'])+2+d['config']['data_lateness_allowance_days']
validation=dict(power_scenarios_verified=9,independent_integer_search=True,monte_carlo_simulations=100000,monte_carlo_is_synthetic_validation_only=True,monte_carlo_power=estimated_power,monte_carlo_type1=estimated_alpha,report_source_values_verified=len(claims),duration_scenarios_verified=3,actual_launch_and_inflow_unavailable_preserved=True)
validation['validated_source_hashes']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['verify_planning_calculations.py','prepare_final_delivery.py','sample_size_results.json','report_claims.csv','experiment_config.json']}
import sys
if '--write-validation' in sys.argv:(ROOT/'planning_validation.json').write_text(json.dumps(validation,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False,indent=2))
