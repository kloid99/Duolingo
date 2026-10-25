"""Create a typeset Korean analysis PDF with the full executed source attached."""
from pathlib import Path
from html import escape
import io
import itertools
import json
import keyword
import math
import platform
import token
import tokenize
import pandas as pd
import numpy as np
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Flowable, KeepTogether
from pypdf import PdfReader, PdfWriter

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent / 'output' / 'pdf'
TMP = ROOT.parent / 'tmp' / 'pdfs'
OUT.mkdir(parents=True, exist_ok=True)
TMP.mkdir(parents=True, exist_ok=True)
FINAL = OUT / '듀오링고_RFM_분석과_파이썬코드.pdf'
INTERMEDIATE = TMP / 'rfm_typeset.pdf'
R = json.loads((ROOT / 'results.json').read_text(encoding='utf-8'))
SOURCE = (ROOT / 'analyze_rfm.py').read_text(encoding='utf-8')

pdfmetrics.registerFont(TTFont('Malgun', 'C:/Windows/Fonts/malgun.ttf'))
pdfmetrics.registerFont(TTFont('MalgunBold', 'C:/Windows/Fonts/malgunbd.ttf'))
pdfmetrics.registerFont(TTFont('Consolas', 'C:/Windows/Fonts/consola.ttf'))
pdfmetrics.registerFontFamily('Malgun', normal='Malgun', bold='MalgunBold', italic='Malgun', boldItalic='MalgunBold')

PW, PH = A4
MARGIN = 42
W = PW - MARGIN * 2
NAVY = colors.HexColor('#17304C')
TEAL = colors.HexColor('#007B83')
TEXT = colors.HexColor('#243747')
MUTED = colors.HexColor('#637787')
LINE = colors.HexColor('#DCE5EB')
LIGHT = colors.HexColor('#F4F7FA')
PALE = colors.HexColor('#EAF5F4')

styles = {
    'body': ParagraphStyle('body', fontName='Malgun', fontSize=9.6, leading=16, textColor=TEXT, wordWrap='CJK', spaceAfter=9),
    'small': ParagraphStyle('small', fontName='Malgun', fontSize=8.1, leading=12.6, textColor=MUTED, wordWrap='CJK', spaceAfter=7),
    'title': ParagraphStyle('title', fontName='MalgunBold', fontSize=28, leading=40, textColor=NAVY, wordWrap='CJK', spaceAfter=13),
    'h1': ParagraphStyle('h1', fontName='MalgunBold', fontSize=19, leading=29, textColor=NAVY, wordWrap='CJK', spaceAfter=13),
    'h2': ParagraphStyle('h2', fontName='MalgunBold', fontSize=11.5, leading=18, textColor=TEAL, wordWrap='CJK', spaceBefore=10, spaceAfter=8),
    'eyebrow': ParagraphStyle('eyebrow', fontName='Consolas', fontSize=10, leading=16, textColor=TEAL, spaceAfter=8),
    'cell': ParagraphStyle('cell', fontName='Malgun', fontSize=8.5, leading=13, textColor=TEXT, wordWrap='CJK'),
    'head': ParagraphStyle('head', fontName='MalgunBold', fontSize=8.2, leading=12.5, textColor=colors.white, wordWrap='CJK'),
    'num': ParagraphStyle('num', fontName='Malgun', fontSize=8.5, leading=13, textColor=TEXT, alignment=2, wordWrap='CJK'),
}

story = []
pages = []

def p(text, style='body'):
    return Paragraph(text, styles[style])

def para(text, style='body'):
    story.append(p(text, style))

def sub(text):
    para(text, 'h2')

def new_page(kicker, title):
    if story:
        story.append(PageBreak())
    pages.append(title)
    para(kicker, 'eyebrow')
    para(title, 'h1')

def note(text):
    t = Table([[p(text, 'small')]], colWidths=[W])
    t.setStyle(TableStyle([('BACKGROUND', (0,0), (-1,-1), PALE),
        ('BOX', (0,0), (-1,-1), 0.6, LINE), ('LEFTPADDING',(0,0),(-1,-1),12),
        ('RIGHTPADDING',(0,0),(-1,-1),12), ('TOPPADDING',(0,0),(-1,-1),10),
        ('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.extend([t, Spacer(1, 12)])

def table(headers, rows, widths, right=()):
    data = [[p(escape(str(v)), 'head') for v in headers]]
    for row in rows:
        data.append([p(escape(str(v)).replace('\n','<br/>').replace(' ↑','&nbsp;↑'), 'num' if i in right else 'cell') for i,v in enumerate(row)])
    t = Table(data, colWidths=widths, repeatRows=1, hAlign='LEFT')
    commands = [('BACKGROUND',(0,0),(-1,0),NAVY), ('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LEFTPADDING',(0,0),(-1,-1),9), ('RIGHTPADDING',(0,0),(-1,-1),9),
        ('TOPPADDING',(0,0),(-1,-1),8), ('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('LINEBELOW',(0,0),(-1,0),0.7,NAVY)]
    for i in range(1,len(data)):
        commands += [('BACKGROUND',(0,i),(-1,i), colors.white if i%2 else LIGHT),
                     ('LINEBELOW',(0,i),(-1,i),0.45,LINE)]
    t.setStyle(TableStyle(commands))
    story.extend([t, Spacer(1, 12)])

class SegmentBars(Flowable):
    def __init__(self, rows):
        Flowable.__init__(self)
        self.rows, self.width, self.height = rows, W, 175
    def draw(self):
        c = self.canv
        x0, available = 102, W - 155
        c.setFont('Malgun', 7.6)
        c.setFillColor(MUTED)
        c.drawString(x0, self.height-9, '사용자 비중')
        c.setFillColor(TEAL)
        c.rect(x0-10,self.height-9,5,5,stroke=0,fill=1)
        c.setFillColor(MUTED)
        c.drawString(x0+94,self.height-9, '학습량 비중')
        c.setFillColor(NAVY)
        c.rect(x0+84,self.height-9,5,5,stroke=0,fill=1)
        for i, r in enumerate(self.rows):
            y = self.height - 31 - i*21
            c.setFillColor(TEXT)
            c.setFont('Malgun',7.7)
            c.drawString(0,y-2,r['segment'])
            for j,(value,color) in enumerate([(r['user_pct'],TEAL),(r['exposure_pct'],NAVY)]):
                yy = y+2-j*7
                c.setFillColor(color)
                length = value/60*available
                c.roundRect(x0,yy,length,4.5,2,stroke=0,fill=1)
                c.setFont('Malgun',6.8)
                c.drawString(x0+length+5,yy-1, f'{value:.1f}%')

def footer(c, doc):
    c.saveState()
    c.setStrokeColor(LINE)
    c.setLineWidth(.65)
    c.line(MARGIN,PH-45,PW-MARGIN,PH-45)
    c.setFont('Malgun',8)
    c.setFillColor(MUTED)
    c.drawString(MARGIN,PH-34,'DUOLINGO  /  학습 기반 RFM 분석')
    c.setFont('Consolas',8)
    c.drawRightString(PW-MARGIN,PH-34,'2026-10-12')
    c.line(MARGIN,37,PW-MARGIN,37)
    c.setFont('Malgun',7.5)
    c.drawString(MARGIN,25,'공식 원본 직접 집계 | 분석 결과와 실행 코드')
    c.setFont('Consolas',8)
    c.drawRightString(PW-MARGIN,25,str(doc.page))
    c.restoreState()

# 1
new_page('01 / SCORING', 'RFM 기준일과 점수')
para('<b>기준일: 2013-03-13 00:00:00 UTC</b> (한국시간 09:00). 데이터의 마지막 관측일 다음 날을 공통 기준으로 사용합니다. 현재 날짜로 계산하면 역사 데이터의 최근성을 비교할 수 없습니다.')
table(['요소','사용자별 산식','점수 방향'],[
    ['R 최근성','(기준시각 - 마지막 timestamp) / 86,400','작을수록 높음'],
    ['F 빈도','count(distinct timestamp)','클수록 높음'],
    ['M 학습량','sum(session_seen)','클수록 높음']], [74,329,W-403])
para('사용자 분포의 20·40·60·80백분위로 5개 구간을 만들고, R만 점수 방향을 뒤집었습니다. 같은 경계값을 가진 사용자는 같은 점수로 유지하므로 각 점수의 인원이 정확히 20%씩은 아닙니다.')
table(['점수','R 경과 일수','F 세션 수','M 어휘 노출'],[
    ['5','≤ 1.263963','≥ 11','≥ 277'],
    ['4','1.263963 초과~3.193275 이하','5~10','119~276'],
    ['3','3.193275 초과~5.761671 이하','3~4','56~118'],
    ['2','5.761671 초과~8.499238 이하','2','26~55'],
    ['1','> 8.499238','1','≤ 25']], [40,235,100,W-375])
para('R의 표시값은 소수 6자리로 반올림했습니다. 실제 계산은 반올림 전 경계값을 사용합니다. F=1인 33,874명은 모두 F=1점을 받습니다. RFM_code = 100×R점수 + 10×F점수 + M점수는 식별 코드이며, 숫자 크기 자체를 종합 가치로 해석하지 않습니다.', 'small')
sub('계산 단위를 구분해야 하는 이유')
para('한 세션에 여러 단어 행이 있으므로 행 수를 세션 수로 세지 않습니다. F는 사용자별 서로 다른 timestamp의 수인 세션 대리값입니다. M은 단어 노출 합계이며 고유 문항 수·학습 시간·매출이 아닙니다. 과거 누적값인 history_seen은 M에 합산하지 않습니다.')
note('delta는 같은 단어의 이전 학습 이후 시간입니다. 사용자 접속 간격과 구분해야 하며, 전체 delta 분산을 곧바로 학습 습관의 규칙성으로 해석하지 않습니다.')

# 2
new_page('02 / SEGMENT RULES', '7개 세그먼트 규칙')
para('아래 R·F·M은 원래 값이 아닌 1~5점 스코어입니다. <b>위에서 아래 순서로 처음 충족하는 그룹</b>에 배정합니다. 125개 점수 조합이 모두 분류되는지 확인했고 사용자마다 한 그룹만 부여했습니다.')
rules = [
    ['핵심 학습형','R≥4, F≥4, M≥4','최근 활동·반복 빈도·학습량이 모두 높음'],
    ['반복 학습형','R≥3, F≥4; 핵심군 제외','반복 경험은 있으나 최근성 또는 학습량이 핵심군보다 낮음'],
    ['집중 성장형','R≥4, F≤3, M≥3','최근 학습량은 있으나 반복 빈도가 낮아 습관화 여지가 있음'],
    ['최근 저강도형','R≥4, F≤3, M≤2','최근 활동했지만 학습 빈도와 양이 적음'],
    ['관심 유지형','R=3, F≤3','최근성이 중간 수준이며 반복 습관이 부족함'],
    ['우선 복귀형','R≤2, F≥3 또는 M≥3','최근 활동은 뜸하지만 기존 학습 경험이 상대적으로 있음'],
    ['저활동·휴면형','R≤2, F≤2, M≤2','최근 활동과 관측된 학습 경험이 모두 적음']]
table(['세그먼트','규칙','행동 해석'], rules, [104,155,W-259])
sub('분류 예시')
para('RFM 555는 핵심 학습형, 432는 최근 저강도형, 133은 우선 복귀형에 해당합니다. 단순 점수 합계 대신 최근성과 반복 경험의 조합을 사용해 액션을 다르게 설계합니다.')
note('집중 성장형은 성장 가능성을 나타내는 운영 이름입니다. 실제 성과 상승을 확인했다는 뜻은 아닙니다. 가입일이 없어 최근 저강도형을 신규 사용자로, 약 12일간 관측한 휴면형을 영구 이탈 고객으로 단정할 수 없습니다.')
para('마지막 관측일 가까이에 처음 등장한 사용자는 F와 M을 쌓을 기회가 짧습니다. 운영 데이터에서는 가입·최초 관측 경과일과 학습 언어를 함께 확인하고, 코호트별로 규칙을 재검증하는 것이 필요합니다.', 'small')

# 3a
new_page('03 / SEGMENT SUMMARY', '사용자 규모와 학습량 비중')
para('사용자 비중의 분모는 <b>115,222명</b>, 학습량 비중의 분모는 <b>23,364,844회</b>의 어휘 노출입니다. 매출 정보가 없으므로 매출 비중은 모든 그룹에서 산출 불가입니다.')
summ = R['segment_summary']
rows = [[v['segment'],f"{v['users']:,}",f"{v['user_pct']:.2f}%",'산출 불가',f"{v['exposure_pct']:.2f}%"] for v in summ]
rows.append(['합계','115,222','100.00%','산출 불가','100.00%'])
table(['세그먼트','사용자 수','사용자 비중','매출 비중','학습량 비중'],rows,[116,85,99,96,W-396],right=(1,2,4))
story.append(SegmentBars(summ))
story.append(Spacer(1,8))
sub('집계에서 확인한 우선순위')
para('<b>핵심·반복 학습형 34,367명</b>은 사용자 29.83%지만 학습량 71.92%를 차지합니다. 기존 학습 활동을 유지하는 대상 풀입니다. <b>우선 복귀형 23,912명</b>은 사용자 20.75%, 학습량 17.72%로 기존 학습 이력을 활용한 복귀 실험의 우선 대상입니다.')
para('최근 저강도형 12,535명은 짧은 복습을 통해 다음 학습을 유도하는 대상으로 분리할 수 있습니다. 비중 표시값은 반올림 때문에 합계와 조금 다를 수 있습니다.', 'small')

# 3b
new_page('03 / FORWARD VALIDATION', '이후 재학습과 연결되는가')
para('전체 기간으로 만든 세그먼트와 같은 기간의 활동을 비교하면 최근성과 결과가 겹칩니다. 별도 검증에서는 <b>3월 1~7일의 데이터만으로</b> 점수 경계를 다시 계산하고, <b>3월 8~11일 중 한 번 이상 재학습</b>했는지 확인했습니다.')
para('검증 모집단은 앞 기간에 관측된 <b>82,467명</b>입니다. 이 표의 사용자 수와 기준 경계는 전체 기간 요약표와 다릅니다.', 'small')
table(['세그먼트','검증 대상','이후 재학습','4일 재학습률'],
    [[v['segment'],f"{v['baseline_users']:,}",f"{v['returned_users']:,}",f"{v['subsequent_4day_return_pct']:.2f}%"] for v in R['forward_validation']],
    [154,110,121,W-385],right=(1,2,3))
note('핵심 학습형 70.31%, 최근 저강도형 30.67%, 우선 복귀형 23.51%, 저활동·휴면형 14.57%로 이후 활동에 차이가 관측됐습니다. 이 지표는 D7 리텐션 또는 주간 4일 지속 학습률이 아니며, 마케팅의 인과 효과도 아닙니다.')
sub('노션 NSM의 별도 주간 집계')
table(['집계 기간','주간 활성 사용자','4일 이상 학습','지속 학습 비율'],
    [['3월 5~11일','83,325명','9,838명','11.81%']], [116,131,126,W-373])
para('첫날과 마지막 날은 부분 관측이므로 NSM은 온전히 관측된 7일을 사용했습니다. 위 지속 학습 비율의 분모는 주간 활성 사용자입니다. 새 A/B 실험의 효과를 평가할 때는 배정된 전체 사용자를 분모로 쓰는 지표를 함께 사용합니다.', 'small')

# 4
new_page('04 / MARKETING ACTIONS', '대상별 액션과 움직일 지표')
para('대상 규모는 전체 기간 스냅샷의 <b>분석상 대상 풀</b>입니다. 실제 운영에는 계정 매핑, 도달 가능 여부, 수신 동의 및 중복 캠페인 제외 조건을 적용합니다. 지표 방향은 검증할 가설입니다.')
actions = [
    ['핵심 학습형','23,353명','개인 진행 리포트와 주간 4일 학습 미션','주간 지속 학습 사용자 수 ↑'],
    ['반복 학습형','11,014명','오답 단어 복습 큐와 학습 시간대 리마인더','다음날 재학습률 ↑'],
    ['집중 성장형','8,171명','집중 학습을 여러 날의 짧은 복습으로 연결하는 3일 미션','활동일 수·재학습률 ↑'],
    ['최근 저강도형','12,535명','최근 학습 단어로 시작하는 3분 복습 진입점','48시간 내 재학습률 ↑'],
    ['관심 유지형','14,060명','마지막 학습 단어를 활용한 개인화 복습 안내','7일 내 재활성률 ↑'],
    ['우선 복귀형','23,912명','전에 배운 단어 3개로 시작하는 복귀 안내','7일 내 재활성률 ↑\n복귀 후 재학습률 ↑'],
    ['저활동·휴면형','22,177명','기초 복습으로 바로 시작하는 간단한 복귀 동선','재활성률·이후 반복 활동 ↑']]
table(['세그먼트','대상 풀','제안 액션','움직일 지표'],actions,[92,70,220,W-382])
sub('실험 우선순위와 분모')
para('<b>우선 복귀형과 최근 저강도형부터 실험</b>합니다. 세그먼트 안에서 사용자 단위로 실험군·대조군을 무작위 배정하고 학습 언어와 관측 경과일을 균형 있게 맞춥니다. 표본 수는 기준 재학습률과 검출하려는 차이를 정한 뒤 계산합니다.')
para('7일 내 재활성률 = 7일 내 한 번 이상 학습한 배정 사용자 / 전체 배정 사용자.<br/>개입 후 4일 이상 학습률 = 7일 중 4일 이상 학습한 배정 사용자 / 전체 배정 사용자.<br/>다음날 재학습률 = 다음날도 활동한 사용자-활동일 / 다음날까지 관측 가능한 사용자-활동일.', 'small')
note('학습 성과는 sum(session_correct) / sum(session_seen)로 함께 관찰합니다. 언어·어휘 난이도를 고려하고, 반복 사용자-활동일의 통계 추론은 사용자 단위로 묶어 처리합니다.')

# 5a
new_page('05 / K-MEANS', '4개 군집으로 비교')
para('같은 115,222명의 연속형 R·F·M을 log1p 변환 후 표준화했습니다. NumPy 구현의 Lloyd K-means와 k-means++ 초기화를 사용하고, K별로 20회 초기화 중 군집 내 제곱거리 합이 최소인 결과를 선택했습니다.')
table(['군집 수 K','실루엣 점수','군집 내 제곱거리 합'],
    [[v['k'],f"{v['silhouette_2000']:.4f}",f"{v['inertia']:,.2f}"] for v in R['kmeans_candidates']],
    [122,177,W-299],right=(1,2))
para('실루엣은 같은 무작위 표본 2,000명에서 계산했습니다. 비교한 K=3~5 범위에서 점수가 가장 높은 <b>K=4</b>를 채택했습니다. 전체 모집단의 최적 K를 확정하는 결론은 아닙니다.', 'small')
behavior = ['비활성·저학습량','최근 활동·낮은 반복 빈도','활동이 뜸해진 중간 빈도·학습량','최근 활동·고빈도·고학습량']
rows = [[v['cluster'],f"{v['users']:,}",f"{v['R_median']:.2f}",f"{v['F_median']:.0f}",f"{v['M_median']:.0f}",behavior[i]] for i,v in enumerate(R['cluster_summary'])]
table(['군집','사용자 수','R 중앙값\n일','F 중앙값','M 중앙값','행동 해석'],rows,[43,80,68,68,68,W-327],right=(1,2,3,4))
sub('군집에서 드러난 구조')
para('C4는 최근성과 반복 경험이 높은 핵심 활동군입니다. C2는 최근 활동했지만 반복 빈도가 낮은 군집입니다. C3는 기존 학습 경험이 있으나 활동이 뜸해진 사용자가 많고, C1은 비활성·저학습량 사용자를 포괄합니다.')
note('F와 M의 피어슨 상관은 0.9085로 높습니다. 행동 유형 연구를 확장할 때는 활동일 수, 동일 단어별 복습 간격, 세션 간격의 규칙성 등을 추가한 별도 분석이 필요합니다.')

# 5b
new_page('05 / SEGMENT COMPARISON', '규칙형 분류와 군집의 연결')
para('다음 값은 <b>각 RFM 세그먼트 안에서</b> K-means 군집이 차지하는 비중입니다. 행의 합이 약 100%이며, 반올림으로 약간의 차이가 있습니다.')
cross = pd.read_csv(ROOT/'segment_cluster_row_pct.csv', index_col=0)
table(['RFM 세그먼트','C1','C2','C3','C4'],
    [[seg]+[f'{cross.loc[seg,c]:.1f}%' for c in ['C1','C2','C3','C4']] for seg in cross.index],
    [155,89,89,89,W-422],right=(1,2,3,4))
note('<b>ARI = 0.4492.</b> 두 분류의 일부 구분은 겹치지만 군집 수와 경계가 다릅니다. 이 수치는 정확도 44.92%를 의미하지 않습니다.')
sub('운영에 반영할 해석')
para('핵심 학습형의 <b>83.6%</b>는 C4, 우선 복귀형의 <b>72.1%</b>는 C3에 속합니다. 집중 성장형과 최근 저강도형은 각각 <b>96.7%, 94.1%</b>가 C2에 속해 큰 행동 유형은 비슷하지만 학습량에 따라 액션을 다르게 설계할 수 있습니다.')
para('관심 유지형은 C1과 C3로 나뉩니다. 같은 규칙형 세그먼트 안에서도 군집을 보조 태그로 붙여 액션 효과가 달라지는지 확인할 수 있습니다.')
para('<b>캠페인 대상 선정에는 7개 RFM 규칙, 내부 행동 차이 확인에는 4개 K-means 군집</b>을 제안합니다. 두 방식은 같은 R·F·M을 입력했으므로 분류가 겹친다는 사실 자체가 독립적인 타당성 검증은 아닙니다. 기간 분리 검증과 이후 무작위 실험으로 평가합니다.')

# Reproduction and provenance
new_page('APPENDIX A / REPRODUCTION', '코드 실행 안내와 출처')
para('다음 부록은 이번 집계에 실제 사용한 <b>analyze_rfm.py 전체 280줄</b>입니다. 원본 .py 파일도 PDF의 첨부 파일에 포함했습니다. PDF에서 복사하면 줄바꿈이 달라질 수 있으므로 실행에는 첨부 파일 또는 작업 폴더의 원본 코드를 사용합니다.')
table(['항목','설정'],[
    ['재현 환경',f'Python {platform.python_version()}, pandas {pd.__version__}, NumPy {np.__version__}'],
    ['원본 파일','settles.acl16.learning_traces.13m.csv.gz'],
    ['파일 배치','analyze_rfm.py와 원본 CSV.gz를 같은 폴더에 배치'],
    ['패키지 설치','python -m pip install pandas==3.0.1 numpy==2.3.5'],
    ['실행','python analyze_rfm.py'],
    ['재실행 캐시','sessions.pkl 및 quality.json이 있으면 원본 집계를 재사용']], [110,W-110])
para('데이터 파일을 변경했다면 기존 sessions.pkl과 quality.json을 다른 곳에 보관한 뒤 실행해 새 원본을 다시 집계해야 합니다. 첫 실행은 원본을 두 번 읽어 해시 후보의 실제 값까지 비교하며 완전 중복만 제거합니다.', 'small')
sub('주요 결과 파일')
para('results.json: 원래 경계값과 분석 결과<br/>user_rfm.csv: 사용자별 점수·세그먼트·군집<br/>segment_summary.csv: 그룹별 인원·비중·주간 지표<br/>forward_validation.csv: 이후 4일 재학습률<br/>cluster_summary.csv 및 segment_cluster_*.csv: 군집·교차표', 'small')
sub('출처와 품질 확인')
for label,url in [
    ('3팀 프로젝트 노션','https://app.notion.com/p/bfa0b7d59eee83a89db901096978c2a0'),
    ('공식 원본: Settles & Meeder 연구 데이터','https://doi.org/10.7910/DVN/N8XJME'),
    ('Duolingo 변수 설명','https://github.com/duolingo/halflife-regression/blob/master/README.md'),
    ('K-means 참고 문서','https://scikit-learn.org/stable/modules/generated/sklearn.cluster.KMeans.html'),
    ('ARI 참고 문서','https://scikit-learn.org/stable/modules/generated/sklearn.metrics.adjusted_rand_score.html')]:
    para(f'<link href="{escape(url)}" color="#007B83">{escape(label)}</link>', 'small')
para('원본 12,854,226행 - 완전 중복 81행 = 12,854,145행. 고유 사용자 115,222명. 원본 MD5는 공식 메타데이터와 일치했습니다. 세그먼트 인원·어휘 노출 합계, 125개 점수 조합의 전체 분류, 소규모 K-means 예제 및 ARI 레이블 치환 불변성을 확인했습니다.', 'small')
note('가입일·결제·메시지 반응이 없는 역사 데이터입니다. 장기 이탈, 매출 기여, 마케팅 액션의 인과 효과는 이 결과로 확정하지 않습니다. 세부 결과와 코드의 재현성이 이번 문서의 범위입니다.')

# Full code, preserving every original line and using Korean fallback in strings.
CODE_SIZE, CODE_LEADING = 8.5, 11.7
CODE_TEXT_WIDTH = W - 45
lines = SOURCE.splitlines()
default_color = '#273646'
char_colors = [[default_color] * len(line) for line in lines]
try:
    for tok in tokenize.generate_tokens(io.StringIO(SOURCE).readline):
        color = default_color
        if tok.type == token.STRING: color = '#17765A'
        elif tok.type == tokenize.COMMENT: color = '#788895'
        elif tok.type == token.NUMBER: color = '#835395'
        elif tok.type == token.NAME and keyword.iskeyword(tok.string): color = '#2351A1'
        if color != default_color:
            for row in range(tok.start[0], tok.end[0]+1):
                if not 1 <= row <= len(lines): continue
                lo = tok.start[1] if row == tok.start[0] else 0
                hi = tok.end[1] if row == tok.end[0] else len(lines[row-1])
                char_colors[row-1][lo:hi] = [color] * max(0,hi-lo)
except tokenize.TokenError:
    pass

def char_font(ch):
    return 'Consolas' if ord(ch) < 128 else 'Malgun'

wrapped = []
for i,line in enumerate(lines):
    if not line:
        wrapped.append((i+1,True,[]))
        continue
    parts = [(ch,char_font(ch),char_colors[i][j]) for j,ch in enumerate(line)]
    first = True
    while parts:
        prefix = [] if first else [(' ','Consolas',default_color)]*4
        length = sum(pdfmetrics.stringWidth(ch,font,CODE_SIZE) for ch,font,_ in prefix)
        end = 0
        for ch,font,_ in parts:
            width = pdfmetrics.stringWidth(ch,font,CODE_SIZE)
            if length+width > CODE_TEXT_WIDTH:
                break
            length += width
            end += 1
        if end < len(parts):
            breaks = [j+1 for j,(ch,_,_) in enumerate(parts[:end])
                      if ch in ' ,;)]}' and j+1 > end//2]
            if breaks:
                end = breaks[-1]
        assert end > 0
        wrapped.append((i+1,first,prefix+parts[:end]))
        parts = parts[end:]
        first = False

class CodeSheet(Flowable):
    def __init__(self, rows):
        Flowable.__init__(self)
        self.rows, self.width = rows, W
        self.height = len(rows)*CODE_LEADING+17
    def draw(self):
        c = self.canv
        c.setFillColor(LIGHT)
        c.roundRect(0,0,W,self.height,5,fill=1,stroke=0)
        c.setStrokeColor(LINE)
        c.line(31,7,31,self.height-7)
        for i,(number,first,parts) in enumerate(self.rows):
            y = self.height-14-i*CODE_LEADING
            c.setFont('Consolas',6.8)
            c.setFillColor(MUTED)
            c.drawRightString(25,y,str(number) if first else '.')
            x = 38
            text_line = c.beginText(38,y)
            for (font,color), run in itertools.groupby(parts, key=lambda q: (q[1],q[2])):
                run_text = ''.join(ch for ch,_,_ in run)
                text_line.setFont(font,CODE_SIZE)
                text_line.setFillColor(colors.HexColor(color))
                text_line.textOut(run_text)
                x += pdfmetrics.stringWidth(run_text,font,CODE_SIZE)
            c.drawText(text_line)
            assert x <= W-6, (number,x,W)

max_rows = 52
code_chunks, chunk = [], []
for _, group in itertools.groupby(wrapped, key=lambda row: row[0]):
    source_line_rows = list(group)
    if chunk and len(chunk)+len(source_line_rows) > max_rows:
        code_chunks.append(chunk)
        chunk = []
    chunk.extend(source_line_rows)
if chunk:
    code_chunks.append(chunk)
for i,rows in enumerate(code_chunks):
    new_page(f'APPENDIX B / SOURCE CODE {i+1:02d}', '전체 파이썬 코드' if i == 0 else '전체 파이썬 코드 · 계속')
    lo,hi = rows[0][0], rows[-1][0]
    para(f'analyze_rfm.py | 원본 {lo}~{hi}행 | 줄 번호가 없는 점 표시는 긴 줄의 이어지는 부분입니다.', 'small')
    story.append(CodeSheet(rows))

doc = SimpleDocTemplate(str(INTERMEDIATE), pagesize=A4,
    leftMargin=MARGIN,rightMargin=MARGIN,topMargin=64,bottomMargin=50,
    title='듀오링고 RFM 분석과 파이썬 코드',author='3팀 프로젝트 분석',
    subject='RFM scoring, seven segments, marketing actions and K-means comparison')
doc.build(story,onFirstPage=footer,onLaterPages=footer)
reader = PdfReader(str(INTERMEDIATE))
writer = PdfWriter()
writer.clone_document_from_reader(reader)
writer.add_attachment('analyze_rfm.py',SOURCE.encode('utf-8'))
writer.add_metadata({'/Title':'듀오링고 RFM 분석과 파이썬 코드', '/Author':'3팀 프로젝트 분석',
    '/Subject':'5가지 분석 항목 및 전체 파이썬 코드', '/Keywords':'Duolingo,RFM,K-means,Python'})
with FINAL.open('wb') as f:
    writer.write(f)
check = PdfReader(str(FINAL))
actual_pages = len(check.pages)
expected_pages = 8+len(code_chunks)
assert actual_pages == expected_pages, (actual_pages,expected_pages)
assert check.attachments['analyze_rfm.py'][0] == SOURCE.encode('utf-8')
text_all = '\n'.join(page.extract_text() for page in check.pages)
for required in ['115,222','23,353','23,912','70.31%','0.4492','2013-03-13','def quintile','if __name__']:
    assert required in text_all, required
assert len({number for number,first,parts in wrapped if first}) == len(lines)
manifest = {'pdf':str(FINAL),'pages':actual_pages,'code_pages':len(code_chunks),
    'source_lines':len(lines),'wrapped_rows':len(wrapped),'embedded_source_matches':True,
    'page_text_lengths':[len(page.extract_text()) for page in check.pages]}
(TMP/'pdf_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
