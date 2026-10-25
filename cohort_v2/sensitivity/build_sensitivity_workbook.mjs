import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(fileURLToPath(import.meta.url));
// Reuse the task's existing junction to bundled packages.
const req=createRequire(path.resolve(root,'../statistics/package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const data=JSON.parse(await fs.readFile(path.join(root,'sensitivity_results.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('종료일 비교');
const daily=wb.worksheets.add('날짜별 신호');
const following=wb.worksheets.add('다음날 재학습');
const font='Malgun Gothic',navy='#334B68';
function init(s,last,rows){
 s.showGridLines=false;
 s.getRange(`A1:${last}${rows}`).format.font={name:font,size:10,color:'#24364B'};
 s.getRange(`A1:${last}${rows}`).format.rowHeight=25;
 s.getRange(`A1:${last}${rows}`).format.verticalAlignment='center';
 s.getRange(`A1:A${rows}`).format.columnWidth=3;
 s.getRange(`B1:${last}${rows}`).format.columnWidth=15;
 s.getRange(`B2:${last}2`).format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
}
function put(s,c,v){s.getRange(c).values=[[v]];}
function title(s,v){put(s,'B2',v);s.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};}
function head(s,row,labels){const r=s.getRangeByIndexes(row-1,1,1,labels.length);r.values=[labels];r.format.fill=navy;r.format.font={name:font,size:10,color:'#FFFFFF',bold:true};r.format.horizontalAlignment='center';r.format.rowHeight=31;}
init(summary,'K',47);init(daily,'M',42);init(following,'J',66);
summary.tabColor=navy;
summary.getRange('B1:B47').format.columnWidth=25;
title(summary,'2일·3일 비활동 기준 민감도');
put(summary,'B3','2013.03.11 종료 시점 / 기준집단 82,467명 / 연속 UTC 달력 날짜 / 분석 2026.10.13');
put(summary,'B4','2일 기준으로 4,798명 추가 (+5.82%p). 종료일의 인원 순위와 비활동률 순위는 유지됨.');
put(summary,'B5','비활동은 기록 부재의 운영 신호이며 영구 이탈 판정이 아님. 3일 집단은 2일 집단의 부분집합.');
put(summary,'B6','입력: v3 사용자별 활동·마지막 학습일 재계산. 원천 파일 및 해시는 sensitivity_results.json에 기록.');
head(summary,8,['세그먼트','기준 인원','3일 이상','3일 비율','2일 이상','2일 비율','추가 인원','증가 %p','대상 증가율']);
data.final.forEach((r,i)=>{
 const row=9+i;
 summary.getRange(`B${row}:J${row}`).values=[[r.segment,r.cohort_users,r.inactive_3day_users,null,r.inactive_2day_users,null,null,null,null]];
 summary.getRange(`E${row}`).formulas=[[`=D${row}/C${row}`]];
 summary.getRange(`G${row}:J${row}`).formulas=[[`=F${row}/C${row}`,`=F${row}-D${row}`,`=(G${row}-E${row})*100`,`=H${row}/D${row}`]];
});
summary.getRange('C9:D15').setNumberFormat('#,##0');summary.getRange('F9:F15').setNumberFormat('#,##0');summary.getRange('H9:H15').setNumberFormat('#,##0');
for(const c of ['E','G','J'])summary.getRange(`${c}9:${c}15`).setNumberFormat('0.0%');summary.getRange('I9:I15').setNumberFormat('0.00');
summary.getRange('B9:J9').format.fill='#EDF2F7';
put(summary,'B18','인원과 비율의 순위를 각각 비교');
head(summary,19,['세그먼트','3일 인원 순위','2일 인원 순위','3일 비율 순위','2일 비율 순위']);
data.final.filter(r=>r.segment!=='전체').forEach((r,i)=>summary.getRange(`B${20+i}:F${20+i}`).values=[[
 r.segment,r.rank_3day_users,r.rank_2day_users,r.rank_3day_rate,r.rank_2day_rate]]);
summary.getRange('C20:F25').setNumberFormat('0');
put(summary,'B27','순위는 내림차순 규모·비율 기준. 캠페인 효과·투자수익·개입 우선순위를 직접 뜻하지 않음.');
put(summary,'B29','기존 액션 후보를 세 단계로 확인');
head(summary,30,['세그먼트','정확히 1일','정확히 2일','3일 이상','2일 이상 합계']);
data.operating_pools.slice(0,2).forEach((r,i)=>{
 const row=31+i;summary.getRange(`B${row}:F${row}`).values=[[r.segment,r.exact1_users,r.exact2_users,r.inactive3plus_users,null]];
 summary.getRange(`F${row}`).formulas=[[`=D${row}+E${row}`]];
});
summary.getRange('C31:F32').setNumberFormat('#,##0');
put(summary,'B34','멈춤-꾸준형·몰입형의 대상: 3일 이상 9,520명 → 2일 이상 10,287명 (+767명).');
put(summary,'B36','습관 형성형은 추가 인원이 가장 큼: 1,281명. 꾸준형은 기존 대상 대비 증가율이 가장 큼: 31.7%.');
put(summary,'B37','3/8·3/9는 기준에 따라 순위가 달라짐. 3/10·3/11은 순위가 같음. 날짜별 결과를 함께 확인.');
put(summary,'B39','제안: 정확히 2일은 조기 관찰, 3일 이상은 지속 비활동으로 함께 표시. 최적 개입 시점은 미검증.');
put(summary,'B40','습관 형성형의 기존 1~2일 후보 2,902명 중 1,281명은 2일 기준 선택 시 단계가 이동함.');
put(summary,'B41','날짜별 비활동 인원은 서로 겹침. 합산해 고유 이탈 인원으로 해석하지 않음.');
put(summary,'B42','개입 정보가 없어 다음날 재학습을 자연 복귀율·캠페인 반응률로 단정할 수 없음.');
put(summary,'B43','추론 검정 없이 임계값의 인원·비율·순위 민감도를 비교한 결과. 실제 CRM 파일은 수정하지 않음.');
put(summary,'B44','새 데이터로 갱신하려면 analyze_inactivity_sensitivity.py와 이 엑셀 생성 스크립트를 다시 실행.');

daily.getRange('B1:B42').format.columnWidth=16;daily.getRange('C1:C42').format.columnWidth=25;
daily.getRange('J1:M42').format.columnWidth=17;
title(daily,'날짜별 비활동 신호와 순위');
put(daily,'B3','3일 이상 집단 ⊆ 2일 이상 집단. 추가 인원 = 정확히 2일 비활동 사용자.');
put(daily,'B4','날짜별 순위는 6개 세그먼트 안에서 계산. 동점은 최소 순위. 전체 행에는 순위 없음.');
put(daily,'B5','3/7 종료부터 이미 비활동: 2일 기준 43,600명, 3일 기준 32,323명. 이후 수치는 신규 이탈률이 아님.');
put(daily,'B6','입력: daily_threshold_comparison.csv. 상태 흐름의 시작·신규·재학습 인원은 같은 CSV에 보존.');
head(daily,7,['날짜','세그먼트','3일 이상','2일 이상','추가 인원','3일 비율','2일 비율','증가 %p','3일 인원 순위','2일 인원 순위','3일 비율 순위','2일 비율 순위']);
const segOrder=['전체','꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형'];
const ds=[...data.daily].sort((a,b)=>a.date.localeCompare(b.date)||segOrder.indexOf(a.segment)-segOrder.indexOf(b.segment));
ds.forEach((r,i)=>{
 const row=8+i;
 daily.getRange(`B${row}:M${row}`).values=[[new Date(r.date+'T00:00:00Z'),r.segment,r.inactive_3day_users,r.inactive_2day_users,null,r.inactive_3day_rate,r.inactive_2day_rate,null,r.rank_3day_users,r.rank_2day_users,r.rank_3day_rate,r.rank_2day_rate]];
 daily.getRange(`F${row}`).formulas=[[`=E${row}-D${row}`]];daily.getRange(`I${row}`).formulas=[[`=(H${row}-G${row})*100`]];
 if(r.segment==='전체')daily.getRange(`B${row}:M${row}`).format.fill='#EDF2F7';
});
daily.getRange('B8:B35').setNumberFormat('yyyy-mm-dd');daily.getRange('D8:F35').setNumberFormat('#,##0');daily.getRange('G8:H35').setNumberFormat('0.0%');daily.getRange('I8:I35').setNumberFormat('0.00');daily.getRange('J8:M35').setNumberFormat('0');
daily.freezePanes.freezeRows(7);

following.getRange('B1:C66').format.columnWidth=16;following.getRange('D1:D66').format.columnWidth=25;following.getRange('E1:E66').format.columnWidth=18;
title(following,'비활동 신호 다음날의 재학습');
put(following,'B3','같은 날짜의 정확히 2일 집단과 3일 이상 집단을 비교. 각 집단은 서로 겹치지 않음.');
put(following,'B4','같은 사용자가 여러 날짜에 나타날 수 있어 날짜별로 제시. 합산해 독립 표본 검정하지 않음.');
put(following,'B5','3/11 신호의 다음날은 미관측. 빈칸을 0%로 해석하지 않음.');
put(following,'B6','입력: nextday_relearning_by_gap.csv. 학습률의 분모는 신호 기준일의 해당 집단 전체.');
head(following,7,['신호 기준일','다음 날짜','세그먼트','비활동 기간','대상 인원','재학습 인원','재학습률','관측 상태']);
const ns=[...data.nextday].sort((a,b)=>a.signal_date.localeCompare(b.signal_date)||segOrder.indexOf(a.segment)-segOrder.indexOf(b.segment)||a.gap_group.localeCompare(b.gap_group));
ns.forEach((r,i)=>{
 const row=8+i;
 following.getRange(`B${row}:I${row}`).values=[[new Date(r.signal_date+'T00:00:00Z'),new Date(r.next_date+'T00:00:00Z'),r.segment,r.gap_group,r.eligible_users,r.nextday_users,null,r.observation_status]];
 if(r.observable&&r.eligible_users)following.getRange(`H${row}`).formulas=[[`=G${row}/F${row}`]];
 if(!r.observable)following.getRange(`G${row}:I${row}`).format.fill='#F1F3F5';
 if(r.segment==='전체')following.getRange(`B${row}:F${row}`).format.fill='#EDF2F7';
});
following.getRange('B8:C63').setNumberFormat('yyyy-mm-dd');following.getRange('F8:G63').setNumberFormat('#,##0');following.getRange('H8:H63').setNumberFormat('0.0%');following.freezePanes.freezeRows(7);
wb.recalculate();
for(let i=0;i<data.final.length;i++)if(summary.getRange(`H${9+i}`).values[0][0]!==data.final[i].added_exact2_users)throw new Error('Added counts differ');
const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:30},summary:'Final formula error scan'});
console.log(err.ndjson);await fs.writeFile(path.join(root,'workbook_error_scan.json'),err.ndjson);
for(const [sheetName,range,name] of [['종료일 비교','A1:K45','summary'],['날짜별 신호','A1:M22','daily'],['다음날 재학습','A1:J23','nextday'],['다음날 재학습','A48:J63','unobserved']]){
 const image=await wb.render({sheetName,range,scale:1.4,format:'png'});await fs.writeFile(path.join(root,`preview_${name}.png`),new Uint8Array(await image.arrayBuffer()));
}
const xlsx=await SpreadsheetFile.exportXlsx(wb);await xlsx.save(path.join(root,'비활동_2일3일_민감도분석.xlsx'));
console.log(JSON.stringify({sheets:3,dailyRows:ds.length,nextdayRows:ns.length,export:'비활동_2일3일_민감도분석.xlsx'}));
