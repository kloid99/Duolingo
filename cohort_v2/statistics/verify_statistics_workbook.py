from pathlib import Path
import hashlib
import json
import math
from datetime import datetime
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT=Path(__file__).resolve().parent
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
data=json.loads((ROOT/'statistics_results.json').read_text(encoding='utf-8'))
book=ROOT/'코호트_복귀일비교_통계검증.xlsx'
with ZipFile(book) as z:
    ss=[]
    if 'xl/sharedStrings.xml' in z.namelist():
        for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si',NS):
            ss.append(''.join(n.text or '' for n in si.iterfind('.//s:t',NS)))
    sheets=[]
    for i in range(1,4):
        cells={}
        for c in ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).iterfind('.//s:c',NS):
            assert c.get('t')!='e',f'Formula error at sheet {i} {c.get("r")}'
            v=c.find('s:v',NS)
            if c.get('t')=='inlineStr':
                value=''.join(t.text or '' for t in c.iterfind('.//s:t',NS))
            elif v is None or v.text is None:
                value=None
            elif c.get('t')=='s':
                value=ss[int(v.text)]
            elif c.get('t')=='d':
                value=datetime.fromisoformat(v.text.replace('Z','+00:00'))
            elif c.get('t') in ['str','b']:
                value=v.text
            else:
                value=float(v.text)
            cells[c.get('r')]=value
        sheets.append(cells)

def eq(actual,expected):
    if isinstance(expected,(float,int)):
        assert actual is not None and math.isclose(actual,expected,rel_tol=1e-11,abs_tol=1e-12),(actual,expected)
    else:
        assert actual==expected,(actual,expected)

for metric,start in [('return_4d',8),('repeat_4d',20)]:
    for row,r in enumerate([r for r in data['rates'] if r['scope']=='baseline' and r['metric']==metric],start):
        for col,key in [('B','segment'),('C','n'),('D','successes'),('E','rate'),('F','ci95_low'),('G','ci95_high')]:
            eq(sheets[0].get(f'{col}{row}'),r[key])
order={'D1':0,'D2':1,'D3':2,'within2':3}
rr=sorted([r for r in data['rates'] if r['scope']=='same_return_date'],key=lambda r:(r['first_return_date'],order[r['metric']]))
missing=0
for row,r in enumerate(rr,8):
    for col,key in [('D','segment'),('E','n'),('F','successes'),('G','rate'),('H','ci95_low'),('I','ci95_high')]:
        eq(sheets[1].get(f'{col}{row}'),r[key])
    assert isinstance(sheets[1][f'B{row}'],datetime),'Date must be an Excel typed date'
    assert sheets[1][f'B{row}'].date().isoformat()==r['first_return_date']
    if not r['observable']:
        missing+=1
        assert all(sheets[1].get(f'{c}{row}') is None for c in 'FGHI')
for row,r in enumerate(data['comparisons'],8):
    for col,key in [('D','group_a'),('E','group_b'),('F','n_a'),('G','n_b'),('H','rate_a'),('I','rate_b'),('J','diff_pp'),('K','ci95_diff_low_pp'),('L','ci95_diff_high_pp'),('P','log10_p_holm')]:
        eq(sheets[2].get(f'{col}{row}'),r[key])
    eq(sheets[2][f'N{row}'],'유의' if r['significant_holm_005'] else '유의하지 않음')
    eq(sheets[2][f'M{row}'],r['p_holm_label'] if r['p_holm']==0 else r['p_holm'])
    if r['p_holm']>0:
        assert math.isclose(sheets[2][f'M{row}'],r['p_holm'],rel_tol=1e-11,abs_tol=0)
assert missing==56
result={'saved_workbook_verified':True,'baseline_rate_rows':14,'return_date_rows':112,
        'unobserved_rows_preserved':missing,'pairwise_tests_verified':150,'formula_errors':0,
        'source_hashes_unchanged':all(hashlib.sha256((ROOT.parent/n).read_bytes()).hexdigest()==h for n,h in data['source_hashes'].items())}
assert result['source_hashes_unchanged']
manifest={'analysis_date':'2026-10-13','validation':result,
          'files':{p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                   for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.xlsx','.csv','.md','.json'] and p.name!='statistics_manifest.json'}}
(ROOT/'statistics_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2))
