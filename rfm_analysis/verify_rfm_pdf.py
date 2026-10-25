from pathlib import Path
import json
from PIL import Image, ImageDraw, ImageFont
import pdfplumber
from pypdf import PdfReader

root = Path(__file__).resolve().parent.parent
tmp = root/'tmp'/'pdfs'
pdf = root/'output'/'pdf'/'듀오링고_RFM_분석과_파이썬코드.pdf'
files = sorted(tmp.glob('rfm_page-*.png'))
assert len(files) == 14
font = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 18)
for start in range(0,len(files),5):
    sheet = Image.new('RGB',(1578,1534),'#DCE5EB')
    draw = ImageDraw.Draw(sheet)
    for j,f in enumerate(files[start:start+5]):
        im = Image.open(f).convert('RGB')
        im.thumbnail((510,722))
        x = 12+(j%3)*522
        y = 26+(j//3)*754
        sheet.paste(im,(x,y))
        draw.text((x,y-22),f'PAGE {start+j+1}',font=font,fill='#17304C')
    sheet.save(tmp/f'contact_{start//5+1}.png')

outside = []
with pdfplumber.open(pdf) as document:
    for i,page in enumerate(document.pages):
        for char in page.chars:
            if char['x0'] < 15 or char['x1'] > page.width-15 or char['top'] < 15 or char['bottom'] > page.height-15:
                outside.append((i+1,char['text'],char['x0'],char['top']))
assert not outside, outside[:10]
reader = PdfReader(pdf)
original = (root/'rfm_analysis'/'analyze_rfm.py').read_bytes()
assert reader.attachments['analyze_rfm.py'][0] == original
text = '\n'.join(p.extract_text() for p in reader.pages)
assert '\ufffd' not in text
for word in ['115,222','23,353','11,014','8,171','12,535','14,060','23,912','22,177','0.3734','0.4492','def aggregate_source','def quintile','def main']:
    assert word in text, word
summary = {'pages':len(reader.pages),'page_images':len(files),'characters_outside_page':len(outside),
           'embedded_python_identical':True,'size_bytes':pdf.stat().st_size}
(tmp/'pdf_quality_checks.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
