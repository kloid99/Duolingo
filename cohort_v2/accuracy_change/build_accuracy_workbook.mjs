import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(fileURLToPath(import.meta.url));
const req=createRequire(path.resolve(root,'../statistics/package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(path.join(root,'accuracy_results.json'),'utf8'));
const wb=Workbook.create(),s=wb.worksheets.add('정답률 변화와 재학습'),c=wb.worksheets.add('대상과 세그먼트');
const font='Malgun Gothic',navy='#334B68';
function put(sh,cell,v){sh.getRange(cell).values=[[v]];}
function head(sh,row,labels){const r=sh.getRangeByIndexes(row-1,1,1,labels.length);r.values=[labels];r.format.fill=navy;r.format.font={name:font,size:10,color:'#FFFFFF',bold:true};r.format.horizontalAlignment='center';r.format.rowHeight=31;}
for(const sh of [s,c]){
 sh.showGridLines=false;sh.getRange('A1:I48').format.font={name:font,size:10,color:'#24364B'};
 sh.getRange('A1:I48').format.rowHeight=26;sh.getRange('A1:I48').format.verticalAlignment='center';
 sh.getRange('A1:A48').format.columnWidth=3;sh.getRange('B1:B48').format.columnWidth=48;
 sh.getRange('C1:H48').format.columnWidth=18;sh.getRange('I1:I48').format.columnWidth=3;
 sh.getRange('B2:H2').format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
 sh.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};
}
s.tabColor=navy;put(s,'B2','정답률 변화와 이후 재학습');
put(s,'B3','초반 2013.03.01~03 / 후반 03.05~07 / 추적 03.08~11 UTC / 분석 2026.10.13');
put(s,'B4','현재 표본에서는 정답률 상승이 반복학습 증가와 연결된다는 뚜렷한 근거를 확인하지 못함.');
put(s,'B5','양쪽 기간 각각 20문항 이상. 변화 = 후반 정답률 − 초반 정답률. 3/4는 변화 계산에서 제외.');
put(s,'B6','주 분석: 습관 형성형 4,653명(31.9%). 반복학습 = 추적 4일 중 2일 이상 학습.');
head(s,8,['모형 / 대비','사용자','결과 해당 인원','오즈비 OR','95% 하한','95% 상한','Holm p']);
const labels=['습관 형성형 · 반복학습 · 미보정','습관 형성형 · 반복학습 · 보정','전체 가능자 · 반복학습 · 보정','습관 형성형 · 1일 이상 재학습','양쪽 50문항 · 반복학습 · 보정','하락 vs 유지 · 반복학습 · 보정','상승 vs 유지 · 반복학습 · 보정'];
d.models.forEach((r,i)=>s.getRange(`B${9+i}:H${9+i}`).values=[[labels[i],r.n,r.events,r.odds_ratio,r.ci_low,r.ci_high,r.p_holm??null]]);
s.getRange('C9:D15').setNumberFormat('#,##0');s.getRange('E9:H15').setNumberFormat('0.000');s.getRange('B10:H10').format.fill='#EDF2F7';
put(s,'B17','연속 모형 OR은 정답률 변화 +10%p당. 마지막 두 행은 ±5%p 유지 집단 대비 오즈비.');
put(s,'B18','보정 효과 6개에 Holm 적용. 미보정 행은 적용 대상 아님. CI는 개별 95% 구간.');
put(s,'B19','초기 정답률·제곱항, 활동일·최근성, 양쪽 문항 수, 세션 수, 첫 관측 날짜를 보정.');
head(s,21,['습관 형성형 · 미보정 집단','사용자','1일 이상 재학습','재학습률','2일 이상 학습','반복학습률']);
d.groups.filter(r=>r.segment==='습관 형성형').forEach((r,i)=>{
 const row=22+i;s.getRange(`B${row}:G${row}`).values=[[r.change_group,r.n,r.returned,null,r.repeated,null]];
 s.getRange(`E${row}`).formulas=[[`=D${row}/C${row}`]];s.getRange(`G${row}`).formulas=[[`=F${row}/C${row}`]];
});
s.getRange('C22:D24').setNumberFormat('#,##0');s.getRange('F22:F24').setNumberFormat('#,##0');s.getRange('E22:E24').setNumberFormat('0.0%');s.getRange('G22:G24').setNumberFormat('0.0%');
const notes=[
 '상승 집단의 초기 평균 정답률 83.8%, 하락 집단 94.0%. 시작점 차이와 평균으로의 회귀를 고려해야 함.',
 '재학습 모형의 개별 CI는 1을 넘지만 Holm p=0.156. 다중 비교 보정 후 유의하지 않음.',
 '비유의는 효과 0 또는 집단 동등성의 입증이 아님. 정답률 변화만으로 대상을 선별할 근거는 부족함.',
 '초반·후반의 단어·난도가 다를 수 있어 실제 학습 능력의 개선·악화로 단정하지 않음.',
 '기록이 없는 정답률·변화는 결측. 양쪽 기록이 있는 사용자만 포함해 선택 편향이 있음.',
 '범주형 비교는 미보정 결과 확인 후 추가한 탐색적 보조 분석. 사전 등록된 검증이 아님.',
 '다음 단계: 습관 형성형의 다음 학습 연결 실험안. 정답률 변화는 대상 필터로 추가하지 않음.',
 '출처: 원본 session_seen/session_correct 및 v3 사용자 코호트. 해시는 accuracy_results.json에 기록.',
 '회귀는 Python 결과 스냅샷. 입력 변경 시 analyze_accuracy_change.py를 다시 실행.'
];notes.forEach((v,i)=>put(s,`B${27+i}`,v));

c.getRange('B1:B48').format.columnWidth=26;c.getRange('C1:C48').format.columnWidth=24;c.getRange('D1:H48').format.columnWidth=20;
put(c,'B2','비교 가능 대상과 세그먼트별 결과');
put(c,'B3','한쪽 기록 없음과 문항 수 부족을 별도 집계. 두 기간을 모두 관측한 사용자에 대한 결과.');
put(c,'B4','최근 단발형은 비교 가능 대상 0명. 비율 빈칸을 0%로 해석하지 않음.');
head(c,6,['세그먼트','기준 인원','분석 가능','한쪽 기록 없음','20문항 미만','포함 비율','양쪽 50문항']);
const order=['전체','꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형'];
const cv=[...d.coverage].sort((a,b)=>order.indexOf(a.segment)-order.indexOf(b.segment));
cv.forEach((r,i)=>{
 const row=7+i;c.getRange(`B${row}:H${row}`).values=[[r.segment,r.baseline_users,r.eligible_users,r.missing_window_users,r.low_volume_users,null,r.eligible_50_users]];
 c.getRange(`G${row}`).formulas=[[`=D${row}/C${row}`]];
});
c.getRange('C7:F13').setNumberFormat('#,##0');c.getRange('G7:G13').setNumberFormat('0.0%');c.getRange('H7:H13').setNumberFormat('#,##0');
put(c,'B15','정답률은 기간별 정답 수 합 / 문항 수 합. 각 사용자 정답률을 계산한 후 결과와 연결.');
put(c,'B16','집단별 수치 아래는 미보정 관측률. 세그먼트나 집단 사이의 인과 효과 비교가 아님.');
head(c,18,['세그먼트','변화 집단','사용자','재학습 인원','재학습률','반복학습 인원','반복학습률']);
const gs=[...d.groups].sort((a,b)=>order.indexOf(a.segment)-order.indexOf(b.segment));
gs.forEach((r,i)=>{
 const row=19+i;c.getRange(`B${row}:H${row}`).values=[[r.segment,r.change_group,r.n,r.returned,null,r.repeated,null]];
 if(r.n){c.getRange(`F${row}`).formulas=[[`=E${row}/D${row}`]];c.getRange(`H${row}`).formulas=[[`=G${row}/D${row}`]];}
 if(r.segment==='전체')c.getRange(`B${row}:H${row}`).format.fill='#EDF2F7';
});
c.getRange('D19:E39').setNumberFormat('#,##0');c.getRange('G19:G39').setNumberFormat('#,##0');c.getRange('F19:F39').setNumberFormat('0.0%');c.getRange('H19:H39').setNumberFormat('0.0%');
put(c,'B41','변화 경계: 정확히 ±5%p는 유지에 포함. 정수 교차곱으로 판정해 반올림 오류를 방지.');
put(c,'B42','사용자별 분자·분모·제외 사유는 user_accuracy_change.csv, 일별 원천 집계는 baseline_daily_accuracy.csv.');
put(c,'B43','원천 전체 행 해시 중복 81개 제거. 82,467명 문항·정답·세션·활동일 수 기존 집계와 일치.');
wb.recalculate();
const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},summary:'Formula errors'});
await fs.writeFile(path.join(root,'workbook_error_scan.json'),err.ndjson);console.log(err.ndjson);
for(const [sheetName,range,name] of [[s.name,'A1:I37','summary'],[c.name,'A1:I25','coverage'],[c.name,'A26:I44','segments']]){
 const image=await wb.render({sheetName,range,scale:1.5,format:'png'});await fs.writeFile(path.join(root,`preview_${name}.png`),new Uint8Array(await image.arrayBuffer()));
}
const book=await SpreadsheetFile.exportXlsx(wb);await book.save(path.join(root,'정답률_변화와_재학습.xlsx'));
console.log('exported 2 sheets');
