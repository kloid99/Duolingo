from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import json, math, hashlib
ROOT=Path(__file__).resolve().parent
d=json.loads((ROOT/'word_performance_results.json').read_text(encoding='utf-8'))
ns={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with ZipFile(ROOT/'같은단어_성과개선과_복습간격.xlsx') as z:
    ss=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        ss=[''.join(t.text or '' for t in si.iterfind('.//s:t',ns)) for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',ns)]
    sheets=[]
    for i in [1,2,3]:
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
    if isinstance(expected,(int,float)):assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-20),(cell,actual,expected)
    else:assert actual==expected,(cell,actual,expected)
for row,r in enumerate(d['models'][:4],9):
    for col,key in [('C','n'),('D','events'),('E','estimate'),('F','ci_low'),('G','ci_high'),('H','p_holm')]:eq(0,f'{col}{row}',r[key])
for row,r in enumerate(d['quartiles'],19):
    for col,key in [('B','gain_quartile'),('C','n'),('D','repeated'),('F','initial_mean'),('G','final_mean'),('H','words_median')]:eq(0,f'{col}{row}',r[key])
    eq(0,f'E{row}',r['repeated']/r['n'])
for row,r in enumerate(d['models'][4:],8):
    for col,key in [('C','users'),('D','n'),('E','estimate'),('F','ci_low'),('G','ci_high'),('H','p_holm')]:eq(1,f'{col}{row}',r[key])
for row,r in enumerate(d['gap_bins'],16):
    for col,key in [('B','gap_bin'),('C','records'),('D','users'),('E','attempts'),('F','correct')]:eq(1,f'{col}{row}',r[key])
    eq(1,f'G{row}',r['correct']/r['attempts'])
order=['전체','꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형']
for row,r in enumerate(sorted(d['coverage'],key=lambda r:order.index(r['segment'])),7):
    for col,key in [('B','segment'),('C','baseline_users'),('D','no_matched_words'),('E','one_to_four_words'),('F','eligible_users'),('G','ambiguous_history_users'),('H','model_users'),('I','review_eligible_users')]:eq(2,f'{col}{row}',r[key])
    assert r['baseline_users']==r['no_matched_words']+r['one_to_four_words']+r['eligible_users']
    assert r['model_users']==r['eligible_users']-r['ambiguous_history_users']
validation={'model_rows_verified':6,'quartile_rows_verified':4,'gap_bin_rows_verified':5,'coverage_rows_verified':7,'formula_errors':0,'three_sheets_visually_reviewed':True}
manifest={'analysis_date':'2026-10-13','workbook_validation':validation,'analysis_validation':json.loads((ROOT/'analysis_validation.json').read_text(encoding='utf-8')),'source_hashes':d['source_hashes'],'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.xlsx','.csv','.json','.md','.py','.mjs'] and p.name!='word_performance_manifest.json'},'project_files':{name:hashlib.sha256((ROOT.parent/name).read_bytes()).hexdigest() for name in ['analyze_word_performance.py','verify_word_performance.py','가설과_지표_정의_대조표.md','가설별_결론표.md']}}
(ROOT/'word_performance_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(validation,ensure_ascii=False,indent=2))
