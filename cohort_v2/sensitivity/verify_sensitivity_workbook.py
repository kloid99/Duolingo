from pathlib import Path
from datetime import datetime
from zipfile import ZipFile
from xml.etree import ElementTree as ET
from collections import Counter
import csv
import hashlib
import json
import math

ROOT = Path(__file__).resolve().parent
data = json.loads((ROOT / 'sensitivity_results.json').read_text(encoding='utf-8'))
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
with ZipFile(ROOT / '비활동_2일3일_민감도분석.xlsx') as z:
    ss = []
    if 'xl/sharedStrings.xml' in z.namelist():
        ss = [''.join(t.text or '' for t in si.iterfind('.//s:t', NS))
              for si in ET.fromstring(z.read('xl/sharedStrings.xml')).findall('s:si', NS)]
    sheets = []
    for i in range(1, 4):
        cells = {}
        for c in ET.fromstring(z.read(f'xl/worksheets/sheet{i}.xml')).iterfind('.//s:c', NS):
            assert c.get('t') != 'e', (i, c.get('r'))
            v = c.find('s:v', NS)
            if c.get('t') == 'inlineStr':
                value = ''.join(t.text or '' for t in c.iterfind('.//s:t', NS))
            elif v is None or v.text is None:
                value = None
            elif c.get('t') == 's':
                value = ss[int(v.text)]
            elif c.get('t') == 'd':
                value = datetime.fromisoformat(v.text.replace('Z', '+00:00')).date().isoformat()
            elif c.get('t') in ['str', 'b']:
                value = v.text
            else:
                value = float(v.text)
            cells[c.get('r')] = value
        sheets.append(cells)

def check(sheet, row, record, mapping):
    for col, key in mapping:
        actual, expected = sheets[sheet].get(f'{col}{row}'), record[key]
        if isinstance(expected, (float, int)):
            assert actual is not None and math.isclose(actual, expected, rel_tol=1e-11, abs_tol=1e-11), (sheet, row, key, actual, expected)
        else:
            assert actual == expected, (sheet, row, key, actual, expected)

for row, r in enumerate(data['final'], 9):
    check(0, row, r, [('B','segment'),('C','cohort_users'),('D','inactive_3day_users'),('E','inactive_3day_rate'),('F','inactive_2day_users'),('G','inactive_2day_rate'),('H','added_exact2_users'),('I','added_pp'),('J','relative_expansion')])
for row, r in enumerate(data['final'][1:], 20):
    check(0, row, r, [('B','segment'),('C','rank_3day_users'),('D','rank_2day_users'),('E','rank_3day_rate'),('F','rank_2day_rate')])
for row, r in enumerate(data['operating_pools'][:2], 31):
    check(0, row, r, [('B','segment'),('C','exact1_users'),('D','exact2_users'),('E','inactive3plus_users'),('F','inactive2plus_users')])
order = {r['segment']: i for i, r in enumerate(data['final'])}
for row, r in enumerate(sorted(data['daily'], key=lambda r: (r['date'], order[r['segment']])), 8):
    check(1, row, r, [('B','date'),('C','segment'),('D','inactive_3day_users'),('E','inactive_2day_users'),('F','added_exact2_users'),('G','inactive_3day_rate'),('H','inactive_2day_rate'),('I','added_pp'),('J','rank_3day_users'),('K','rank_2day_users'),('L','rank_3day_rate'),('M','rank_2day_rate')])
missing = 0
empty_denominator = 0
for row, r in enumerate(sorted(data['nextday'], key=lambda r: (r['signal_date'], order[r['segment']], 0 if r['gap_group']=='3일 이상' else 1)), 8):
    check(2, row, r, [('B','signal_date'),('C','next_date'),('D','segment'),('E','gap_group'),('F','eligible_users'),('G','nextday_users'),('H','nextday_rate'),('I','observation_status')])
    if not r['observable']:
        missing += 1
        assert sheets[2].get(f'G{row}') is None and sheets[2].get(f'H{row}') is None
    if r['observable'] and r['eligible_users'] == 0:
        empty_denominator += 1
        assert sheets[2].get(f'H{row}') is None
assert missing == 14
with (ROOT / 'additional_2day_candidates.csv').open(encoding='utf-8-sig', newline='') as f:
    candidates = list(csv.DictReader(f))
assert len(candidates) == 4798
assert len({r['user_id'] for r in candidates}) == 4798
assert Counter(r['segment'] for r in candidates) == {r['segment']: r['added_exact2_users'] for r in data['final'][1:]}
assert all(data['checks'].values())
assert all(hashlib.sha256((ROOT.parent / n).read_bytes()).hexdigest() == h for n, h in data['source_hashes'].items())
result = {'saved_workbook_verified': True, 'analysis_checks_passed': len(data['checks']), 'summary_rows': 7, 'rank_rows': 6, 'operating_pool_rows': 2, 'daily_rows': 28, 'nextday_rows': 56, 'unobserved_rows_preserved': missing, 'zero_denominator_rates_blank': empty_denominator, 'candidate_users_verified': len(candidates), 'formula_errors': 0, 'source_hashes_unchanged': True}
manifest = {'analysis_date': '2026-10-13', 'validation': result, 'source_hashes': data['source_hashes'], 'files': {p.name: {'bytes': p.stat().st_size, 'sha256': hashlib.sha256(p.read_bytes()).hexdigest()} for p in ROOT.iterdir() if p.is_file() and p.suffix in ['.xlsx', '.csv', '.md', '.json', '.py', '.mjs'] and p.name != 'sensitivity_manifest.json'}}
(ROOT / 'sensitivity_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(result, ensure_ascii=False, indent=2))
