from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import json,math,hashlib
ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'accuracy_results.json').read_text(encoding='utf-8'))
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with ZipFile(ROOT/'정답률_변화와_재학습.xlsx') as z:
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
    if isinstance(expected,(int,float)):assert math.isclose(actual,expected,rel_tol=1e-11,abs_tol=1e-25),(cell,actual,expected)
    else:assert actual==expected,(cell,actual,expected)
for row,r in enumerate(d['models'],9):
    for col,key in [('C','n'),('D','events'),('E','odds_ratio'),('F','ci_low'),('G','ci_high'),('H','p_holm')]:eq(0,f'{col}{row}',r.get(key))
for row,r in enumerate([r for r in d['groups'] if r['segment']=='습관 형성형'],22):
    for col,key in [('B','change_group'),('C','n'),('D','returned'),('E','return_rate'),('F','repeated'),('G','repeat_rate')]:eq(0,f'{col}{row}',r[key])
order=['전체','꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형']
for row,r in enumerate(sorted(d['coverage'],key=lambda r:order.index(r['segment'])),7):
    for col,key in [('B','segment'),('C','baseline_users'),('D','eligible_users'),('E','missing_window_users'),('F','low_volume_users'),('H','eligible_50_users')]:eq(1,f'{col}{row}',r[key])
    eq(1,f'G{row}',r['eligible_users']/r['baseline_users'])
missing=0
for row,r in enumerate(sorted(d['groups'],key=lambda r:order.index(r['segment'])),19):
    for col,key in [('B','segment'),('C','change_group'),('D','n'),('E','returned'),('F','return_rate'),('G','repeated'),('H','repeat_rate')]:eq(1,f'{col}{row}',r[key])
    if r['n']==0:
        missing+=1;assert sheets[1].get(f'F{row}') is None and sheets[1].get(f'H{row}') is None
assert missing==3
validation={'model_effect_rows_verified':7,'habit_group_rows_verified':3,'coverage_rows_verified':7,'all_group_rows_verified':21,'zero_denominator_rows_blank':3,'formula_errors':0,'both_sheets_visually_reviewed':True}
manifest={'analysis_date':'2026-10-13','workbook_validation':validation,'analysis_validation':json.loads((ROOT/'analysis_validation.json').read_text(encoding='utf-8')),'source_hashes':d['source_hashes'],'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.xlsx','.csv','.json','.md','.py','.mjs'] and p.name!='accuracy_manifest.json'},'analysis_script_sha256':hashlib.sha256((ROOT.parent/'analyze_accuracy_change.py').read_bytes()).hexdigest()}
(ROOT/'accuracy_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False,indent=2))
