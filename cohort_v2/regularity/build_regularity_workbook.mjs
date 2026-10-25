import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(fileURLToPath(import.meta.url));
const req=createRequire(path.resolve(root,'../statistics/package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(path.join(root,'regularity_results.json'),'utf8'));
const wb=Workbook.create(),s=wb.worksheets.add('규칙성과 반복학습'),c=wb.worksheets.add('대상과 분석 기준');
const font='Malgun Gothic',navy='#334B68';
function put(sh,cell,v){sh.getRange(cell).values=[[v]];}
function head(sh,row,labels){const r=sh.getRangeByIndexes(row-1,1,1,labels.length);r.values=[labels];r.format.fill=navy;r.format.font={name:font,size:10,color:'#FFFFFF',bold:true};r.format.horizontalAlignment='center';r.format.rowHeight=30;}
for(const sh of [s,c]){
 sh.showGridLines=false;sh.getRange('A1:I42').format.font={name:font,size:10,color:'#24364B'};
 sh.getRange('A1:I42').format.rowHeight=26;sh.getRange('A1:I42').format.verticalAlignment='center';
 sh.getRange('A1:A42').format.columnWidth=3;sh.getRange('B1:B42').format.columnWidth=48;
 sh.getRange('C1:H42').format.columnWidth=17;sh.getRange('I1:I42').format.columnWidth=3;
 sh.getRange('B2:H2').format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
 sh.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};
}
s.tabColor=navy;
put(s,'B2','복습 규칙성과 이후 반복학습');
put(s,'B3','습관 형성형 / 기준 2013.03.01~07 UTC / 결과 03.08~11 / 분석 2026.10.13');
put(s,'B4','활동량 등을 보정하면 간격 변동이 클수록 반복학습 오즈가 낮음. 개입 효과를 뜻하지 않음.');
put(s,'B5','결과: 4일 중 2일 이상 학습. OR: log(1+CV)가 해당 표본에서 1표준편차 증가할 때의 오즈비.');
put(s,'B6','CV = 세션 간격 표준편차 / 평균. 낮을수록 간격 변동이 작음. 95% 구간은 다중 비교 보정 전.');
head(s,8,['분석 모형','사용자','반복학습 인원','오즈비 OR','95% 하한','95% 상한','Holm p']);
const labels=['고유 시각 4회 이상 · 미보정','고유 시각 4회 이상 · 보정','고유 시각 6회 이상 · 보정','30분 세션 4회 이상 · 보정','동일 4,100명 · 고유 시각 보정'];
d.models.forEach((r,i)=>s.getRange(`B${9+i}:H${9+i}`).values=[[labels[i],r.n,r.events,r.odds_ratio,r.ci_low,r.ci_high,r.p_holm??null]]);
s.getRange('C9:D13').setNumberFormat('#,##0');s.getRange('E9:G13').setNumberFormat('0.000');s.getRange('H9:H13').setNumberFormat('0.00E+00');s.getRange('B10:H10').format.fill='#EDF2F7';
put(s,'B15','미보정 행의 Holm p는 적용 대상 아님. 보정 모형 4개의 검정만 Holm 보정.');
put(s,'B16','보정: 활동일 수·최근성 범주, log(1+문항 수), log(1+세션 수), 첫 관측 학습 시각.');
put(s,'B17','세션 정의에 따라 추정 크기가 달라짐. OR 0.705는 반복학습 확률이 29.5% 낮다는 뜻이 아님.');
head(s,19,['미보정 CV 사분위','사용자','반복학습 인원','반복학습률','문항 수 중앙값','세션 수 중앙값']);
d.quartiles.forEach((r,i)=>{
 const row=20+i;s.getRange(`B${row}:G${row}`).values=[[r.cv_group,r.users,r.repeat_users,null,r.words_median,r.sessions_median]];
 s.getRange(`E${row}`).formulas=[[`=D${row}/C${row}`]];
});
s.getRange('C20:D23').setNumberFormat('#,##0');s.getRange('E20:E23').setNumberFormat('0.0%');s.getRange('F20:G23').setNumberFormat('#,##0');
put(s,'B25','단순 사분위 비교는 단조롭지 않음. 변동이 큰 집단의 세션 수와 학습량도 큼.');
head(s,27,['비슷한 활동 조건의 보조 비교','낮은 변동 비율','높은 변동 비율','차이 %p','포함 사용자','층 수']);
const r=d.within_strata;
s.getRange('B28:G28').values=[['층 내부 중앙값 기준 · 동일 층 가중치',r.low_rate,r.high_rate,null,r.users,r.strata]];
s.getRange('E28').formulas=[['=(D28-C28)*100']];s.getRange('C28:D28').setNumberFormat('0.00%');s.getRange('E28').setNumberFormat('0.00');s.getRange('F28:G28').setNumberFormat('#,##0');
put(s,'B30','활동일·최근성·세션 수를 맞추고 문항 수 3분위로 층화. 양 집단 각각 10명 이상인 층만 포함.');
put(s,'B31','층별 전체 인원 비중으로 가중. 첫 관측 시각까지 보정한 비교는 아니며 기술 통계로 해석.');
put(s,'B33','주 분석은 14,583명 중 10,633명(72.9%). 기록 부족 3,950명에게 결과를 일반화하지 않음.');
put(s,'B34','후속 과제: 초반·후반 정답률 변화와 재학습 관계 분석, 이후 무작위 개입 실험 설계.');

put(c,'B2','규칙성 산출 대상과 분석 기준');
put(c,'B3','분석 포함 기준: 해당 정의의 세션 4회 이상, 기준 주간 활동일 2일 이상.');
put(c,'B4','세그먼트별 산출 가능 범위는 아래와 같음. 회귀 분석은 습관 형성형에 한정.');
head(c,6,['세션 정의','세그먼트','기준 인원','분석 가능','제외 인원','포함 비율']);
c.getRange('B1:B42').format.columnWidth=29;c.getRange('C1:C42').format.columnWidth=25;c.getRange('D1:H42').format.columnWidth=20;
d.coverage.forEach((r,i)=>{
 const row=7+i;c.getRange(`B${row}:G${row}`).values=[[r.definition==='timestamp'?'고유 타임스탬프':'30분 초과 간격으로 분리',r.segment,r.users,r.eligible_users,null,null]];
 c.getRange(`F${row}:G${row}`).formulas=[[`=D${row}-E${row}`,`=E${row}/D${row}`]];
});
c.getRange('D7:F18').setNumberFormat('#,##0');c.getRange('G7:G18').setNumberFormat('0.0%');
const notes=[
 '기본 세션: 사용자별 고유 timestamp. 30분 정의: 직전 기록과 30분 초과 간격이면 새 세션.',
 '실제 세션 ID가 없으므로 추정치. 단어별 delta는 사용하지 않음. 언어별 기록은 사용자 단위로 통합.',
 '원천: learning_traces.13m.csv 및 v3/user_retention_cohort.csv. SHA-256은 regularity_results.json에 기록.',
 '로지스틱 회귀·HC1 표준오차·양측 Wald 검정. 보정 모형 4개 규칙성 계수에 Holm 보정.',
 '관측된 연관성. 7일 안의 간격만 포함하며 장기 유지·알림 효과·예측 성능은 미검증.',
 '간격 수에 따라 가능한 CV 범위가 달라, 모든 사용자에게 공통 CV를 부여한 보정 확률은 제시하지 않음.',
 '30분 정의는 4,100명(습관 형성형의 28.1%)만 포함. 같은 4,100명에 기본 정의도 적용해 함께 비교.',
 '사용자별 지표: user_regularity.csv. 층별 분자·분모: within_strata_comparison.csv.',
 '회귀 수치는 Python 분석의 스냅샷. 엑셀 수치 수정으로 재적합되지 않음.',
 '재실행: v3/analyze_regularity.py → 이 폴더의 verify_regularity.py → build_regularity_workbook.mjs.',
 '검증: 82,467명 기존 집계 대조, 150명 간격 재계산, 5개 모형 독립 BFGS 교차검증.',
 '기록 부족을 규칙성 0으로 처리하지 않음. 사분위·최소 세션 수는 검증된 운영 임계값이 아님.'
];notes.forEach((v,i)=>put(c,`B${21+i}`,v));
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},summary:'Formula errors'});
await fs.writeFile(path.join(root,'workbook_error_scan.json'),errors.ndjson);console.log(errors.ndjson);
for(const [sh,n] of [[s,'results'],[c,'coverage']]){
 const image=await wb.render({sheetName:sh.name,range:'A1:I35',scale:1.5,format:'png'});
 await fs.writeFile(path.join(root,`preview_${n}.png`),new Uint8Array(await image.arrayBuffer()));
}
const book=await SpreadsheetFile.exportXlsx(wb);await book.save(path.join(root,'복습_규칙성과_반복학습.xlsx'));
console.log('exported 2 sheets');
