import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
import {Workbook, SpreadsheetFile} from '@oai/artifact-tool';

const root=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(root,'statistics_results.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('요약');
const dates=wb.worksheets.add('복귀일 비교');
const tests=wb.worksheets.add('전체 검정');
const font='Malgun Gothic', navy='#334B68', ink='#24364B';
const short={return_4d:'4일 내 재학습',repeat_4d:'2일 이상 학습',D1:'D+1 학습',D2:'D+2 학습',D3:'D+3 학습',within2:'2일 내 추가 학습'};
function base(sheet,last,rows){
  sheet.showGridLines=false;
  const r=sheet.getRange(`A1:${last}${rows}`);
  r.format.font={name:font,size:10,color:ink};r.format.rowHeight=24;r.format.verticalAlignment='center';
  r.format.wrapText=false;
  sheet.getRange(`A1:A${rows}`).format.columnWidth=3;
  sheet.getRange(`B1:${last}${rows}`).format.columnWidth=14;
}
function text(sheet,cell,value){sheet.getRange(cell).values=[[value]];}
function header(sheet,row,labels){
  const r=sheet.getRangeByIndexes(row-1,1,1,labels.length);r.values=[labels];
  r.format.fill=navy;r.format.font={name:font,size:10,color:'#FFFFFF',bold:true};
  r.format.horizontalAlignment='center';r.format.rowHeight=30;
}
function title(sheet,value){text(sheet,'B2',value);sheet.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};}
base(summary,'I',48);base(dates,'K',124);base(tests,'P',162);
summary.tabColor=navy;
summary.getRange('B1:D48').format.columnWidth=22;
summary.getRange('H1:I48').format.columnWidth=15;
title(summary,'코호트 비교와 통계 검증');
text(summary,'B3','기준 2013.03.01–07 / 추적 03.08–11 UTC / 82,467명 / 분석 2026.10.13');
text(summary,'B4','관측자료의 탐색적 비교. 신뢰구간은 개별 95%, 유의성은 150개 비교의 Holm 보정 p로 판단.');
text(summary,'B5','집계 출처: v3 user_retention_cohort.csv. 통계는 statistics_results.json의 계산 스냅샷.');
for(const [metric,start] of [['return_4d',7],['repeat_4d',19]]){
  text(summary,`B${start-1}`,metric==='return_4d'?'4일 안에 한 번 이상 재학습':'4일 중 서로 다른 날짜에 2일 이상 학습');
  summary.getRange(`B${start-1}`).format.font.bold=true;
  header(summary,start,['세그먼트','기준 인원','학습 인원','학습률','95% 하한','95% 상한']);
  const records=data.rates.filter(r=>r.scope==='baseline'&&r.metric===metric);
  records.forEach((r,i)=>{
    const row=start+1+i;
    summary.getRange(`B${row}:G${row}`).values=[[r.segment,r.n,r.successes,null,r.ci95_low,r.ci95_high]];
    summary.getRange(`E${row}`).formulas=[[`=D${row}/C${row}`]];
  });
  summary.getRange(`C${start+1}:D${start+7}`).setNumberFormat('#,##0');
  summary.getRange(`E${start+1}:G${start+7}`).setNumberFormat('0.0%');
  summary.getRange(`B${start+1}:G${start+1}`).format.fill='#EDF2F7';
}
text(summary,'B29','습관 형성형과 최근 단발형의 격차는 3/8·3/9 복귀자에서도 확인됨. 3/10 D+1은 유의하지 않음.');
text(summary,'B30','습관 형성형과 멈춤-꾸준형의 전체 반복학습률 차이는 보정 후 유의하지 않음.');
text(summary,'B32','전체 기준집단의 주요 반복학습률 비교 (차이 = A − B, 단위 %p)');
header(summary,33,['집단 A','집단 B','차이 (%p)','95% 하한','95% 상한','보정 p','판정']);
const important=data.comparisons.filter(r=>r.scope==='baseline'&&r.metric==='repeat_4d'&&[
 ['습관 형성형','최근 단발형'],['습관 형성형','멈춤-꾸준형'],['멈춤-꾸준형','멈춤-몰입형']
].some(([a,b])=>a===r.group_a&&b===r.group_b));
const testRow=new Map(data.comparisons.map((r,i)=>[r,8+i]));
important.forEach((r,i)=>{
 const row=34+i,tr=testRow.get(r);
 summary.getRange(`B${row}:H${row}`).values=[[r.group_a,r.group_b,null,null,null,null,null]];
 summary.getRange(`D${row}:H${row}`).formulas=[[
  `='전체 검정'!J${tr}`,`='전체 검정'!K${tr}`,`='전체 검정'!L${tr}`,`='전체 검정'!M${tr}`,`='전체 검정'!N${tr}`]];
});
summary.getRange('D34:F36').setNumberFormat('0.00');
for(const [row,note] of [[39,'비율: Wilson 95% 구간. 차이: Newcombe 95% 구간. 구간은 다중 비교 보정 전 값.'],
 [40,'검정: 양측 두 비율 z 검정. 30개 전체집단 + 120개 같은 복귀일 비교를 한 묶음으로 Holm 보정.'],
 [41,'개별 신뢰구간이 0을 제외해도 Holm 보정 후 유의하지 않을 수 있음. 비유의는 동등성 입증이 아님.'],
 [42,'같은 복귀일 비교의 분모는 해당 날짜 복귀자. 원래 세그먼트 전체에 대한 결론으로 확대하지 않음.'],
 [43,'동일 복귀일은 관측 기회를 맞추지만 최근성·활동량 차이를 통제하지 않음. 인과·개입 효과는 미검증.'],
 [44,'D7/D30·장기 이탈·다음 주 NSM은 4일 추적으로 확인 불가. 3/11 복귀자의 이후 칸은 미관측.'],
 [45,'통계 결과를 갱신하려면 analyze_cohort_statistics.py와 이 엑셀 생성 스크립트를 다시 실행.']])text(summary,`B${row}`,note);

dates.getRange('B1:B124').format.columnWidth=14;
dates.getRange('C1:D124').format.columnWidth=23;
title(dates,'같은 복귀일의 세그먼트 비교');
text(dates,'B3','D0 = 추적기간 중 첫 재학습일. 분모 = 해당 날짜에 처음 복귀한 사용자.');
text(dates,'B4','2일 내 추가 학습 = D+1 또는 D+2 학습. D+1~D+3은 각 날짜 당일 학습률.');
text(dates,'B5','미관측은 빈칸으로 유지. 구간은 개별 Wilson 95% 신뢰구간.');
text(dates,'B6','입력: v3 사용자별 활동을 재집계하고 first_return_cohorts.csv와 전수 대조.');
header(dates,7,['첫 복귀일','지표','세그먼트','복귀 인원','학습 인원','학습률','95% 하한','95% 상한','관측 상태']);
const dateOrder=['2013-03-08','2013-03-09','2013-03-10','2013-03-11'];
const metricOrder=['D1','D2','D3','within2'];
const dr=data.rates.filter(r=>r.scope==='same_return_date').sort((a,b)=>dateOrder.indexOf(a.first_return_date)-dateOrder.indexOf(b.first_return_date)||metricOrder.indexOf(a.metric)-metricOrder.indexOf(b.metric));
dr.forEach((r,i)=>{
 const row=8+i;
 dates.getRange(`B${row}:J${row}`).values=[[new Date(r.first_return_date+'T00:00:00Z'),short[r.metric],r.segment,r.n,r.successes,null,r.ci95_low,r.ci95_high,r.observable?'관측':'미관측']];
 if(r.observable)dates.getRange(`G${row}`).formulas=[[`=F${row}/E${row}`]];
 else dates.getRange(`F${row}:J${row}`).format.fill='#F1F3F5';
 if(r.segment==='전체')dates.getRange(`B${row}:E${row}`).format.fill='#EDF2F7';
});
dates.getRange('B8:B119').setNumberFormat('yyyy-mm-dd');dates.getRange('E8:F119').setNumberFormat('#,##0');dates.getRange('G8:I119').setNumberFormat('0.0%');
dates.freezePanes.freezeRows(7);

tests.getRange('B1:B162').format.columnWidth=14;
tests.getRange('C1:E162').format.columnWidth=22;
tests.getRange('F1:G162').format.columnWidth=12;
tests.getRange('M1:N162').format.columnWidth=16;
tests.getRange('O1:P162').format.columnWidth=16;
title(tests,'전체 조합의 차이와 다중 비교 보정');
text(tests,'B3','차이 = 집단 A − 집단 B. 기준집단 전체 30건 + 같은 복귀일 120건 = 150건.');
text(tests,'B4','95% 차이 구간은 보정 전 Newcombe 구간. 판정은 Holm 보정 p < 0.05 기준.');
text(tests,'B5','통계 계산 스냅샷. p가 매우 작으면 <1e-300으로 표시하며 log10(p)도 보존.');
text(tests,'B6','입력: statistics_results.json. 원본 사용자 활동과 기존 v3 요약표의 분자·분모 일치 확인.');
header(tests,7,['복귀일/범위','지표','집단 A','집단 B','A 인원','B 인원','A 비율','B 비율','차이 (%p)','95% 하한','95% 상한','Holm p','보정 후 판정','원래 p','log10(Holm p)']);
data.comparisons.forEach((r,i)=>{
 const row=8+i;
 tests.getRange(`B${row}:P${row}`).values=[[
 r.first_return_date?new Date(r.first_return_date+'T00:00:00Z'):'전체 기준집단',short[r.metric],r.group_a,r.group_b,r.n_a,r.n_b,r.rate_a,r.rate_b,null,r.ci95_diff_low_pp,r.ci95_diff_high_pp,
 r.p_holm===0?r.p_holm_label:r.p_holm,r.significant_holm_005?'유의':'유의하지 않음',r.p_raw===0?r.p_raw_label:r.p_raw,r.log10_p_holm]];
 tests.getRange(`J${row}`).formulas=[[`=(H${row}-I${row})*100`]];
});
tests.getRange('B8:B157').setNumberFormat('yyyy-mm-dd');tests.getRange('F8:G157').setNumberFormat('#,##0');tests.getRange('H8:I157').setNumberFormat('0.0%');tests.getRange('J8:L157').setNumberFormat('0.00');tests.getRange('M8:M157').setNumberFormat('0.000E+00');tests.getRange('O8:O157').setNumberFormat('0.000E+00');tests.getRange('P8:P157').setNumberFormat('0.00');
tests.getRange('N8:N157').conditionalFormats.add('containsText',{text:'유의하지 않음',format:{fill:'#F1F3F5',font:{color:'#526175'}}});
tests.freezePanes.freezeRows(7);
for(const sh of [summary,dates,tests]){
 const max=sh===summary?48:sh===dates?124:162;
 const last=sh===summary?'I':sh===dates?'K':'P';
 sh.getRange(`B2:${last}2`).format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
 sh.getRange(`E8:${last}${max}`).format.horizontalAlignment='right';
}
summary.getRange('G34:G36').setNumberFormat('0.000E+00');
wb.recalculate();
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Final error scan'});
await fs.writeFile(path.join(root,'workbook_error_scan.json'),errors.ndjson);
console.log(errors.ndjson);
const expectedRates=data.rates.filter(r=>r.scope==='baseline'&&r.metric==='return_4d');
for(let i=0;i<expectedRates.length;i++){
 const actual=summary.getRange(`E${8+i}`).values[0][0];
 if(Math.abs(actual-expectedRates[i].rate)>1e-12)throw new Error('Rate formula does not match Python');
}
const captures=[['요약','A1:I46','preview_summary.png'],['복귀일 비교','A1:K22','preview_dates.png'],['전체 검정','A1:P19','preview_tests.png'],['복귀일 비교','A89:K119','preview_unobserved.png']];
for(const [sheetName,range,file] of captures){
 const png=await wb.render({sheetName,range,scale:1.4,format:'png'});
 await fs.writeFile(path.join(root,file),new Uint8Array(await png.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);
await xlsx.save(path.join(root,'코호트_복귀일비교_통계검증.xlsx'));
console.log(JSON.stringify({sheets:3,comparisons:data.test_count,export:'코호트_복귀일비교_통계검증.xlsx'}));
