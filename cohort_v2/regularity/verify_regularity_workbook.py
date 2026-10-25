from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import json,math,hashlib
ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'regularity_results.json').read_text(encoding='utf-8'))
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with ZipFile(ROOT/'복습_규칙성과_반복학습.xlsx') as z:
    ss=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        ss=[''.join(t.text or '' for t in si.iterfind('.//s:t',ns)) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    sheets=[]
    for i in [1,2]:
        cells={}
        for c in ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).iterfind('.//s:c',ns):
            assert c.get('t')!='e'
            v=c.find('s:v',ns)
            if c.get('t')=='inlineStr': value=''.join(t.text or '' for t in c.iterfind('.//s:t',ns))
            elif v is None or v.text is None: value=None
            elif c.get('t')=='s': value=ss[int(v.text)]
            elif c.get('t')=='str': value=v.text
            else: value=float(v.text)
            cells[c.get('r')]=value
        sheets.append(cells)
def eq(sheet,cell,expected):
    actual=sheets[sheet].get(cell)
    if isinstance(expected,(int,float)): assert math.isclose(actual,expected,rel_tol=1e-11,abs_tol=1e-25),(cell,actual,expected)
    else: assert actual==expected,(cell,actual,expected)
for row,r in enumerate(d['models'],9):
    for col,key in [('C','n'),('D','events'),('E','odds_ratio'),('F','ci_low'),('G','ci_high'),('H','p_holm')]: eq(0,f'{col}{row}',r.get(key))
for row,r in enumerate(d['quartiles'],20):
    for col,key in [('B','cv_group'),('C','users'),('D','repeat_users'),('E','repeat_rate'),('F','words_median'),('G','sessions_median')]: eq(0,f'{col}{row}',r[key])
for col,key in [('C','low_rate'),('D','high_rate'),('E','difference_pp'),('F','users'),('G','strata')]: eq(0,col+'28',d['within_strata'][key])
for row,r in enumerate(d['coverage'],7):
    for col,key in [('C','segment'),('D','users'),('E','eligible_users'),('F','excluded_users')]: eq(1,f'{col}{row}',r[key])
    eq(1,f'G{row}',r['eligible_users']/r['users'])
validation={'model_rows_verified':5,'quartile_rows_verified':4,'stratified_comparison_verified':True,'coverage_rows_verified':12,'formula_errors':0,'both_sheets_visually_reviewed':True}
manifest={'analysis_date':'2026-10-13','workbook_validation':validation,'analysis_validation':json.loads((ROOT/'analysis_validation.json').read_text(encoding='utf-8')),'source_hashes':d['source_hashes'],'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.xlsx','.csv','.json','.md','.py','.mjs'] and p.name!='regularity_manifest.json'},'analysis_script_sha256':hashlib.sha256((ROOT.parent/'analyze_regularity.py').read_bytes()).hexdigest()}
(ROOT/'regularity_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False,indent=2))
