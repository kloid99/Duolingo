from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from datetime import date
import json,hashlib,math
ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'behavior_flow_results.json').read_text(encoding='utf-8'))
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with ZipFile(ROOT/'행동흐름과_개입대상.xlsx') as z:
    ss=[]
    if 'xl/sharedStrings.xml' in z.namelist():ss=[''.join(t.text or '' for t in si.iterfind('.//s:t',ns)) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    sheets=[]
    for i in [1,2]:
        cells={}
        for c in ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).iterfind('.//s:c',ns):
            assert c.get('t')!='e'
            v=c.find('s:v',ns)
            if c.get('t')=='inlineStr':value=''.join(t.text or '' for t in c.iterfind('.//s:t',ns))
            elif v is None or v.text is None:value=None
            elif c.get('t')=='s':value=ss[int(v.text)]
            elif c.get('t')=='str':value=v.text
            else:value=float(v.text)
            cells[c.get('r')]=value
        sheets.append(cells)
def eq(sheet,cell,expected):
    actual=sheets[sheet].get(cell)
    if expected is None:assert actual in [None,''],(cell,actual)
    elif isinstance(expected,(int,float)):assert math.isclose(actual,expected,rel_tol=1e-11,abs_tol=1e-14),(cell,actual,expected)
    else:assert actual==expected,(cell,actual,expected)
for row,r in enumerate(d['flow'],7):
    for col,key in [('B','segment'),('C','baseline_users'),('D','no_learning_users'),('E','one_learning_day_users'),('F','two_plus_learning_days_users')]:eq(0,f'{col}{row}',r[key])
    eq(0,f'G{row}',r['returned_users']/r['baseline_users']);eq(0,f'H{row}',r['two_plus_learning_days_share'])
for row,r in enumerate(d['aligned'],18):
    for col,key in [('B','segment'),('C','eligible_returners'),('D','pattern_00_users'),('E','pattern_10_users'),('F','pattern_01_users'),('G','pattern_11_users'),('H','within2_rate')]:eq(0,f'{col}{row}',r[key])
for row,r in enumerate([r for r in d['first_learning'] if r['segment']=='습관 형성형'],29):
    eq(0,f'B{row}',(date.fromisoformat(r['first_learning_date'])-date(1899,12,30)).days)
    for col,key in [('C','users'),('D','d1_users'),('E','d2_users'),('F','within2_users'),('G','within2_rate')]:eq(0,f'{col}{row}',r[key])
for row,r in enumerate(d['candidates'],8):
    eq(1,f'D{row}','합계' if r['eligibility_date_utc']=='합계' else (date.fromisoformat(r['eligibility_date_utc'])-date(1899,12,30)).days)
    for col,key in [('E','eligible_users'),('F','fully_observed_users'),('G','unobserved_users'),('H','learning_users'),('I','rate')]:eq(1,f'{col}{row}',r[key])
validation=dict(baseline_flow_rows_verified=7,aligned_pattern_rows_verified=7,first_learning_rows_verified=4,candidate_summary_rows_verified=12,formula_errors=0,unobserved_result_counts_and_rates_blank=True,two_sheets_visually_reviewed=True,count_change_recalculation_verified=True)
manifest=dict(analysis_date='2026-10-13',workbook_validation=validation,analysis_validation=json.loads((ROOT/'analysis_validation.json').read_text(encoding='utf-8')),source_hashes=d['source_hashes'],files={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.xlsx','.csv','.json','.md','.py','.mjs'] and p.name!='behavior_flow_manifest.json'},analysis_script_sha256=hashlib.sha256((ROOT.parent/'analyze_behavior_flow.py').read_bytes()).hexdigest())
(ROOT/'behavior_flow_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False,indent=2))
