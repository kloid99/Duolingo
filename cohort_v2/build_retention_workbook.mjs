import fs from 'node:fs/promises';
import {createRequire} from 'node:module';
import {pathToFileURL,fileURLToPath} from 'node:url';
import path from 'node:path';
const runtime='C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/node';
const req=createRequire(path.join(runtime,'package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool',{paths:[runtime]})).href);
const root=path.dirname(fileURLToPath(import.meta.url));
const r=JSON.parse(await fs.readFile(path.join(root,'results_retention.json'),'utf8'));
const revision=JSON.parse(await fs.readFile(path.join(root,'segmentation','revision_validation.json'),'utf8'));
const wb=Workbook.create();
const summary=wb.worksheets.add('세그먼트 요약');
const daily=wb.worksheets.add('시점별 추적');
const cohorts=wb.worksheets.add('복귀일 코호트');
const definitions=wb.worksheets.add('분석 기준과 액션');
const color='#334B68',font='Malgun Gothic';
const all=r.first_return_cohorts_overall;
// Derived cohort records are emitted as JSON by the analysis script, not CSV parsing.
const detailed=JSON.parse(await fs.readFile(path.join(root,'workbook_inputs.json'),'utf8'));
const excelDate=s=>new Date(s+'T00:00:00Z');
function setup(s,last='N',rows=90){
 s.showGridLines=false;s.getRange(`B2:${last}${rows}`).format.font={name:font,size:10,color:'#24364B'};
 s.getRange(`B2:${last}${rows}`).format.rowHeight=25;
 s.getRange(`B2:${last}${rows}`).format.verticalAlignment='center';
 s.getRange(`A1:A${rows}`).format.columnWidth=3;
 s.getRange(`B2:B${rows}`).format.columnWidth=25;
 s.getRange(`C2:${last}${rows}`).format.columnWidth=15;
}
function title(s,text,last){
 s.getRange('B2').values=[[text]];s.getRange('B2').format.font={name:font,size:14,bold:true};
 s.getRange(`B3:${last}3`).format.borders={bottom:{style:'thin',color:'#A8B5C4'}};
}
function table(s,row,headers,data){
 const h=s.getRangeByIndexes(row-1,1,1,headers.length);h.values=[headers];
 h.format.fill=color;h.format.font={name:font,size:10,color:'#FFFFFF',bold:true};
 h.format.wrapText=true;h.format.horizontalAlignment='center';h.format.rowHeight=43;
 s.getRangeByIndexes(row,1,data.length,headers.length).values=data.map(v=>v.map(x=>typeof x==='string'&&x.startsWith('=')?null:x));
 for(let i=0;i<data.length;i++)for(let j=0;j<headers.length;j++){
  const x=data[i][j];if(typeof x==='string'&&x.startsWith('='))s.getCell(row+i,1+j).formulas=[[x]];
 }
}
function formats(s,r0,r1,countCols,rateCols){
 for(const c of countCols)s.getRange(`${c}${r0}:${c}${r1}`).setNumberFormat('#,##0');
 for(const c of rateCols)s.getRange(`${c}${r0}:${c}${r1}`).setNumberFormat('0.0%');
}
for(const s of [summary,daily,cohorts])setup(s);
setup(definitions,'F',70);summary.tabColor=color;
title(summary,'반복 학습과 비활동 신호 — 수정된 6개 세그먼트','K');
summary.getRange('B4').values=[['기준 2013.03.01~07 | 추적 03.08~11 | UTC | 모든 기준 사용자 포함']];
const rows=r.segment_summary.map((x,i)=>{
 const n=i+7;return [x.segment,x.cohort_users,x.returned_users,`=D${n}/C${n}`,
  x.repeat_users,`=F${n}/C${n}`,x.inactive_3day_users_at_end,`=H${n}/C${n}`,
  Math.round(x.mean_active_days*x.cohort_users),`=J${n}/C${n}`];
});
table(summary,6,['세그먼트','대상 인원','1회 이상\n재학습 인원','4일 내\n재학습률','2일 이상\n학습 인원','2일 이상\n학습률','3일 비활동\n인원(3/11)','3일 비활동\n비율(3/11)','활동일 수\n합계','평균\n활동일 수'],rows);
formats(summary,7,12,['C','D','F','H','J'],['E','G','I']);summary.getRange('K7:K12').setNumberFormat('0.00"일"');
summary.getRange('B13').values=[['전체']];for(const c of ['C','D','F','H','J'])summary.getRange(`${c}13`).formulas=[[`=SUM(${c}7:${c}12)`]];
summary.getRange('E13').formulas=[['=D13/C13']];summary.getRange('G13').formulas=[['=F13/C13']];summary.getRange('I13').formulas=[['=H13/C13']];summary.getRange('K13').formulas=[['=J13/C13']];
formats(summary,13,13,['C','D','F','H','J'],['E','G','I']);summary.getRange('K13').setNumberFormat('0.00"일"');summary.getRange('B13:K13').format.fill='#E9EEF4';summary.getRange('B13:K13').format.font.bold=true;
summary.getRange('B16').values=[['복귀 뒤 추가 학습 — 관측 기간이 확보된 복귀자만 분모에 포함']];summary.getRange('B16').format.font.bold=true;
const conditional=r.segment_summary.map((x,i)=>{const n=i+19;return [x.segment,x.nextday_eligible_returners,x.nextday_repeat_users,`=D${n}/C${n}`,x.two_day_eligible_returners,x.two_day_repeat_users,`=G${n}/F${n}`];});
table(summary,18,['세그먼트','D+1 관측\n복귀자 수','다음날\n학습자 수','다음날\n재학습률','D+2까지 관측\n복귀자 수','2일 내 추가\n학습자 수','2일 내 추가\n학습률'],conditional);
formats(summary,19,24,['C','D','F','G'],['E','H']);
summary.getRange('B26').values=[['다음날 비교: 첫 복귀 3/8~10. 2일 내 추가 학습: 첫 복귀 3/8~9만 포함.']];
summary.getRange('B27').values=[['이 표는 복귀자 중 반복 학습 지표이며, 위 표의 전체 사용자 기준 비율과 분모가 다릅니다.']];
summary.getRange('B30').values=[['추적 종료 시 관측된 학습 양상 — 서로 겹치지 않는 4개 상태']];summary.getRange('B30').format.font.bold=true;
table(summary,32,['세그먼트','대상 인원','관측기간\n미복귀','1회 복귀 후\n3일 비활동','1회 재학습\n추적 종료','2일 이상\n재학습'],r.segment_summary.map(x=>[x.segment,x.cohort_users,x.no_return_users,x.one_return_then_inactive_users,x.one_return_users_other,x.repeat_users]));
formats(summary,33,38,['C','D','E','F','G'],[]);
summary.getRange('B41').values=[['미활동은 관측된 학습 기록 부재입니다. 3일 기준으로 장기 이탈을 확정하지 않습니다.']];
summary.getRange('B42').values=[['단기 반복 학습의 관측 결과이며, 7일 중 4일 학습 NSM이나 마케팅 개입 효과와 구분합니다.']];

title(daily,'시점별 재학습·반복 학습·비활동','N');
daily.getRange('B4').values=[['모든 비율은 각 세그먼트의 고정 인원 기준. 2일·3일 비활동 기준을 함께 확인.']];
table(daily,6,['세그먼트','날짜','대상 인원','당일\n학습 인원','당일\n학습률','누적 1회\n학습 인원','누적\n재학습률','누적 2일\n학습 인원','누적 반복\n학습률','3일 비활동\n인원','3일 비활동\n비율','2일 비활동\n인원','2일 비활동\n비율'],detailed.daily.map((x,i)=>{
 const n=i+7;return [x.segment,excelDate(x.date),x.cohort_users,x.active_users,`=E${n}/D${n}`,
 x.cumulative_returned_users,`=G${n}/D${n}`,x.cumulative_repeat_users,`=I${n}/D${n}`,
 x.inactive_3day_users,`=K${n}/D${n}`,x.inactive_2day_users,`=M${n}/D${n}`];
}));
daily.getRange('C7:C30').setNumberFormat('m/d');formats(daily,7,30,['D','E','G','I','K','M'],['F','H','J','L','N']);
daily.getRange('B33').values=[['3일 비활동 신호의 유입과 재학습 — 전일 신호 인원 + 신규 신호 − 재학습']];daily.getRange('B33').format.font.bold=true;
table(daily,35,['세그먼트','날짜','대상 인원','전일 종료\n비활동 인원','신규\n비활동 인원','비활동 후\n재학습 인원','당일 종료\n비활동 인원','비활동\n비율','전일 비활동자\n재학습률'],detailed.daily.map((x,i)=>{
 const n=i+36;return [x.segment,excelDate(x.date),x.cohort_users,x.start_3day_inactive_users,x.new_3day_inactive_users,
 x.relearned_after_3day_inactivity_users,`=E${n}+F${n}-G${n}`,`=H${n}/D${n}`,`=IF(E${n}=0,"",G${n}/E${n})`];
}));
daily.getRange('C36:C59').setNumberFormat('m/d');formats(daily,36,59,['D','E','F','G','H'],['I','J']);
daily.getRange('B62').values=[['전체 사용자 추적 — 누적 재학습과 현재 비활동은 서로 겹칠 수 있음']];daily.getRange('B62').format.font.bold=true;
table(daily,64,['날짜','대상 인원','누적 재학습\n인원','누적\n재학습률','누적 반복\n학습 인원','누적 반복\n학습률','3일 비활동\n인원','3일 비활동\n비율'],r.overall_daily.map((x,i)=>{
 const n=i+65;return [excelDate(x.date),x.cohort_users,x.cumulative_returned_users,`=D${n}/C${n}`,x.cumulative_repeat_users,`=F${n}/C${n}`,x.inactive_3day_users,`=H${n}/C${n}`];
}));
daily.getRange('B65:B68').setNumberFormat('m/d');formats(daily,65,68,['C','D','F','H'],['E','G','I']);
daily.getRange('B71').values=[['신규 비활동 인원은 그날 처음 3일 기준에 도달한 인원이며, 영구 이탈 인원이 아닙니다.']];

title(cohorts,'첫 복귀일을 D0로 맞춘 재학습 코호트','N');
cohorts.getRange('B4').values=[['D0는 3/8~11 중 첫 재학습일. 가입일과 구분하며, 미관측 구간은 빈칸.']];
const ch=['세그먼트','첫 복귀일','복귀 집단\n인원','D0 인원','D0 비율','D+1 인원','D+1 비율','D+2 인원','D+2 비율','D+3 인원','D+3 비율','2일 내 추가\n학습 인원','2일 내 추가\n학습률'];
function cr(x,n){const out=[x.segment,excelDate(x.first_return_date),x.return_cohort_users];
 for(let k=0;k<4;k++)out.push(x[`D${k}_active_users`]??null,x[`D${k}_observable`]&&x.return_cohort_users>0?`=${['E','G','I','K'][k]}${n}/D${n}`:null);
 out.push(x.within_2days_repeat_users??null,x.within_2days_observable&&x.return_cohort_users>0?`=M${n}/D${n}`:null);return out;}
table(cohorts,6,ch,all.map((x,i)=>cr(x,i+7)));
table(cohorts,14,ch,detailed.cohorts.filter(x=>x.segment!=='전체').map((x,i)=>cr(x,i+15)));
for(const [a,b] of [[7,10],[15,38]]){
 cohorts.getRange(`C${a}:C${b}`).setNumberFormat('m/d');formats(cohorts,a,b,['D','E','G','I','K','M'],['F','H','J','L','N']);
 for(const col of ['F','H','J','L'])cohorts.getRange(`${col}${a}:${col}${b}`).conditionalFormats.add('colorScale',{colors:['#F2F6FA','#C7D9E8','#87B1D0'],thresholds:[0,.5,1]});
}
cohorts.getRange('B41').values=[['빈칸은 미관측입니다. 예: 3/10 복귀자의 D+2는 추적 종료 뒤라 계산하지 않습니다.']];
cohorts.getRange('B42').values=[['복귀자만 포함하므로 전체 기준집단의 이탈 규모는 세그먼트 요약과 함께 봅니다.']];
cohorts.getRange('B43').values=[['복귀일별 인원은 모든 세그먼트에서 합치면 전체 재학습자 29,240명입니다.']];

title(definitions,'분석 기준과 이탈방지 실험 제안','F');
definitions.getRange('C2:F65').format.columnWidth=26;
const defs=[
 ['집단 정의','수정 코드의 6개 세그먼트; 3/1~7 정보로 확정'],
 ['집단 유지','3/8~11의 결과로 세그먼트를 재배정하지 않음'],
 ['단기 반복 학습','서로 다른 날짜에 2일 이상 학습; 연속 학습 조건 없음'],
 ['복귀일 코호트','이후 기간의 첫 재학습일이 같은 사용자; D0는 복귀일'],
 ['미관측 처리','3/11 이후의 경과일은 빈칸; 미활동 0%와 구분'],
 ['3일 비활동 신호','마지막 학습일 이후 3개 이상 연속 달력 날짜에 기록 없음'],
 ['신호 시작점','기준일 이전 마지막 활동도 사용; 이미 쉬던 사용자 포함'],
 ['2일 기준 비교','분석표에 함께 제공; 임계값의 민감도를 확인'],
 ['조건부 분모','D+1: 첫 복귀 3/8~10; 2일 내 반복: 첫 복귀 3/8~9'],
 ['매출 해석','학습량은 어휘 노출 횟수이며 매출·고유 문제 수가 아님'],
 ['관측 한계','4일 추적으로 장기 이탈·D7 리텐션·개입 효과를 확정하지 않음'],
 ['NSM 연결','후속 실험의 목표는 7일 중 4일 이상 학습 비율'],
 ['M 점수 변경','rank(method="first") 제거; 동일 학습량은 동일 M 점수'],
 ['M 경계','1, 24, 53, 108, 239, 최대값; 경계값은 아래 구간 포함'],
 ['입력 코드','사용자가 제공한 수정 코드; 실행용 원본 경로만 변경'],
];
table(definitions,6,['항목','내용'],defs);definitions.getRange('C7:C21').format.columnWidth=92;
definitions.getRange('B24').values=[['검증된 변경 사항']];definitions.getRange('B24').format.font.bold=true;
table(definitions,26,['항목','결과'],[
 ['대상 사용자 수',revision.baseline_users],['세그먼트 수',6],['명칭 변경 외 재배정 인원',revision.membership_changes_after_name_mapping],
 ['M 점수가 바뀐 인원',revision.M_score_changed_users],['M 경계값',revision.m_quantile_edges.join(', ')],
 ['K-means 선택 K',revision.selected_k],['RFM·군집 ARI',revision.ARI],['코호트 데이터 검증',`${Object.values(r.checks).filter(Boolean).length}/${Object.keys(r.checks).length} 항목 일치`],
]);
definitions.getRange('C27:C30').setNumberFormat('#,##0');
definitions.getRange('C32').setNumberFormat('0');
definitions.getRange('C33').setNumberFormat('0.0000');
definitions.getRange('B37').values=[['시점 3/11의 실험 후보 풀 — 역사 데이터에서 산출한 대상 규모']];definitions.getRange('B37').format.font.bold=true;
table(definitions,39,['대상 풀','인원'],r.review_pools.map(x=>[x.review_pool,x.users]));
definitions.getRange('B40:B43').format.columnWidth=37;definitions.getRange('C40:C43').setNumberFormat('#,##0"명"');
definitions.getRange('B46').values=[['습관 형성형: 복귀 직후 다음 학습 일정·주간 진행률 안내를 실험하고 반복 학습을 평가.']];
definitions.getRange('B47').values=[['멈춤-꾸준형·몰입형: 기존 학습 내용으로 짧게 재진입한 뒤 다음 학습까지 연결하는 실험.']];
definitions.getRange('B48').values=[['저활동형: 대규모 풀의 낮은 자연 재학습률을 고려해 저비용 복귀 동선을 검토.']];
definitions.getRange('B49').values=[['실험 성과: 전체 배정 사용자 기준 재학습·반복 학습·7일 중 4일 학습률; 개입 효과는 미검증.']];
definitions.getRange('B52').values=[['출처: 사용자 제공 세그먼트 코드, 원본 learning_traces.13m.csv, 기존 사용자·날짜 활동표.']];
definitions.getRange('B53').values=[['전체 원본을 수정 코드로 재실행하고, 기존 집계값 및 원본 SHA256과 대조했습니다.']];

wb.recalculate();
const overall=summary.getRange('C13:K13').values[0];
if(Number(overall[0])!==82467||Number(overall[1])!==29240||Number(overall[3])!==13466||Math.abs(Number(overall[4])-13466/82467)>1e-12)throw Error('Workbook totals mismatch');
for(let i=0;i<r.segment_summary.length;i++){
 const row=summary.getRange(`C${i+7}:K${i+7}`).values[0],x=r.segment_summary[i];
 if(Number(row[0])!==x.cohort_users||Math.abs(Number(row[4])-x.repeat_4day_rate)>1e-12||Math.abs(Number(row[6])-x.inactive_3day_rate_at_end)>1e-12)throw Error('Workbook segment rates mismatch');
}
console.log((await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:20},maxChars:1000})).ndjson);
await fs.mkdir(path.join(root,'tmp'),{recursive:true});
for(const [s,range,name] of [[summary,'B2:K42','summary'],[daily,'B2:N30','daily'],[daily,'B33:J71','inactivity'],[cohorts,'B2:N43','cohorts'],[definitions,'B2:F53','definitions']]){
 const p=await wb.render({sheetName:s.name,range,scale:1.3,format:'png'});
 await fs.writeFile(path.join(root,'tmp',name+'.png'),new Uint8Array(await p.arrayBuffer()));
}
const output=await SpreadsheetFile.exportXlsx(wb);
await output.save(path.join(root,'코호트_이탈방지_분석_수정세그먼트_v3.xlsx'));
console.log(JSON.stringify({output:'코호트_이탈방지_분석_수정세그먼트_v3.xlsx',validated:true}));
