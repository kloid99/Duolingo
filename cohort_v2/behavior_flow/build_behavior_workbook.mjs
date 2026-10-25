import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(fileURLToPath(import.meta.url));
const req=createRequire(path.resolve(root,'../statistics/package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(path.join(root,'behavior_flow_results.json'),'utf8'));
const wb=Workbook.create(),a=wb.worksheets.add('행동 흐름'),b=wb.worksheets.add('대상과 시점');
const font='Malgun Gothic',navy='#334B68';
const put=(s,c,v)=>s.getRange(c).values=[[v]];
function head(s,r,labels){let v=s.getRangeByIndexes(r-1,1,1,labels.length);v.values=[labels];v.format.fill=navy;v.format.font={name:font,size:10,bold:true,color:'#FFFFFF'};v.format.horizontalAlignment='center';v.format.rowHeight=28;}
function serial(date){return (Date.parse(date+'T00:00:00Z')-Date.UTC(1899,11,30))/86400000;}
for(const s of [a,b]){
 s.showGridLines=false;s.getRange('A1:J39').format.font={name:font,size:10,color:'#24364B'};
 s.getRange('A1:J39').format.rowHeight=25;s.getRange('A1:J39').format.verticalAlignment='center';
 s.getRange('A1:A39').format.columnWidth=3;s.getRange('B1:B39').format.columnWidth=28;
 s.getRange('C1:I39').format.columnWidth=18;s.getRange('J1:J39').format.columnWidth=3;
 s.getRange('B2:I2').format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
 s.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};
}
a.tabColor=navy;put(a,'B2','첫 학습 뒤 다음 학습이 이어지는 지점');
put(a,'B3','기준 2013.03.01~07 UTC / 추적 03.08~11 UTC / 분석 2026.10.13');
put(a,'B4','고정 기준집단을 유지한다. 학습일 수는 서로 다른 UTC 날짜 수이며 세션 수와 다르다.');
head(a,6,['기준집단','전체 사용자','학습 없음','1일 학습','2일 이상 학습','재학습률','반복학습률']);
d.flow.forEach((r,i)=>{
 const row=i+7;a.getRange(`B${row}:H${row}`).values=[[r.segment,r.baseline_users,r.no_learning_users,r.one_learning_day_users,r.two_plus_learning_days_users,null,null]];
 a.getRange(`G${row}`).formulas=[[`=SUM(E${row}:F${row})/C${row}`]];a.getRange(`H${row}`).formulas=[[`=F${row}/C${row}`]];
});
a.getRange('C7:F13').setNumberFormat('#,##0');a.getRange('G7:H13').setNumberFormat('0.0%');a.getRange('B9:H9').format.fill='#EDF2F7';
put(a,'B15','아래는 3/8·9 첫 학습자만 포함. D1·D2를 모두 관측해 추가 학습 기회를 맞춘다.');
head(a,17,['첫 학습자 집단','관측 대상','D1·D2 없음','D1만 학습','D2만 학습','양일 학습','추가 학습률']);
d.aligned.forEach((r,i)=>{
 const row=i+18;a.getRange(`B${row}:H${row}`).values=[[r.segment,r.eligible_returners,r.pattern_00_users,r.pattern_10_users,r.pattern_01_users,r.pattern_11_users,null]];
 a.getRange(`H${row}`).formulas=[[`=IF(C${row}=0,"",SUM(E${row}:G${row})/C${row})`]];
});
a.getRange('C18:G24').setNumberFormat('#,##0');a.getRange('H18:H24').setNumberFormat('0.0%');a.getRange('B20:H20').format.fill='#EDF2F7';
put(a,'B26','첫 후속 학습에는 전날 학습자도 포함된다. 아래 표와 재개 대상 A1을 구분한다.');
head(a,28,['습관 형성형 첫 학습일','첫 학습자','D1 학습','D2 학습','D1 또는 D2','추가 학습률','2개 날짜 관측']);
d.first_learning.filter(r=>r.segment==='습관 형성형').forEach((r,i)=>{
 const row=i+29;a.getRange(`B${row}:H${row}`).values=[[serial(r.first_learning_date),r.users,r.d1_users,r.d2_users,r.within2_users,null,r.within2_observed?'완전 관측':'미완전 관측']];
 if(r.within2_observed)a.getRange(`G${row}`).formulas=[[`=IF(C${row}=0,"",F${row}/C${row})`]];
});
a.getRange('B29:B32').setNumberFormat('yyyy-mm-dd');a.getRange('C29:F32').setNumberFormat('#,##0');a.getRange('G29:G32').setNumberFormat('0.0%');
put(a,'B34','3/10·11 첫 학습자는 두 날짜 결과가 미관측이다. 해당 추가 학습 인원·비율은 빈칸으로 둔다.');
put(a,'B36','원천: v3 고정 사용자 코호트·사용자별 일별 활동·첫 후속 학습 코호트. 기준 시점 3/8 00:00 UTC.');

b.tabColor='#7890A8';b.getRange('B1:B39').format.columnWidth=23;b.getRange('C1:C39').format.columnWidth=28;b.getRange('D1:D39').format.columnWidth=16;
b.getRange('E1:I39').format.columnWidth=17;
put(b,'B2','주후보 A1: 재개 직후 다음 학습 연결');
put(b,'B3','A1은 습관 형성형의 첫 후속 학습이며 직전 완전 UTC 날짜 1개 이상 학습 기록이 없는 사람.');
put(b,'B4','A 결과: 첫 학습 다음 D1·D2의 학습. B 결과: 2일 비활동 확인 시점의 당일·다음날 학습.');
put(b,'B5','A는 첫 기록 이벤트 직후, B는 UTC 00:00. 한 후보 유형 안에서는 사용자당 최초 1회만 선정.');
head(b,7,['후보','대상 범위','자격 날짜','해당 사용자','완전 관측','미완전 관측','결과 학습자','학습률']);
d.candidates.forEach((r,i)=>{
 const row=i+8;const label=r.candidate==='B'?'B 비활동 복귀':r.scope==='직전 비활동 1일 이상'?'A1 주후보':r.scope==='직전 비활동 0일'?'A0 연속 학습':'A 전체 참고';
 b.getRange(`B${row}:I${row}`).values=[[label,r.scope==='전체 해당 대상'?'전체 해당 대상':r.scope,r.eligibility_date_utc==='합계'?'합계':serial(r.eligibility_date_utc),r.eligible_users,r.fully_observed_users,null,r.learning_users,null]];
 b.getRange(`G${row}`).formulas=[[`=E${row}-F${row}`]];b.getRange(`I${row}`).formulas=[[`=IF(F${row}=0,"",H${row}/F${row})`]];
 if(r.scope==='직전 비활동 1일 이상')b.getRange(`B${row}:I${row}`).format.fill='#EDF2F7';
});
b.getRange('D8:D19').setNumberFormat('yyyy-mm-dd');b.getRange('E8:H19').setNumberFormat('#,##0');b.getRange('I8:I19').setNumberFormat('0.0%');
put(b,'B21','A1: 4,809명 중 2,880명만 D1·D2 완전 관측. 추가 학습 1,312명, 45.6%.');
put(b,'B22','A 전체 47.6%와 A1 45.6%는 서로 다른 대상이다. 24.4% 전체 반복학습률도 별도 지표다.');
put(b,'B23','B는 두 완전 UTC 날짜가 끝난 직후 선정한다. 자격 당일 학습 여부를 선정 조건에 넣지 않는다.');
put(b,'B24','A/B 중복 4,705명. 실제 병행 시 공통 배정·노출 이력에 따른 제외 규칙이 필요하다.');
put(b,'B26','학습률은 관측된 행동이며 개입 효과가 아니다. A와 B는 대상·시작 시점이 달라 효과 순위를 비교하지 않는다.');
put(b,'B27','후보 목록에는 기준 주간 정보와 개입 전 활동만 포함. 이후 결과는 별도 파일에 저장한다.');
put(b,'B28','현재 A의 자격 시점은 날짜까지 재구성했다. 실제 운영에는 첫 학습 이벤트 timestamp가 필요하다.');
put(b,'B29','실제 학습 완료·화면 노출 로그가 없어 레슨 종료 시점이나 알림 발송 시간을 확정하지 않는다.');
put(b,'B31','원천: 기준 주간 고정 세그먼트와 자격 시점 전 사용자별 일별 활동. 이후 종료 상태는 선정에 사용하지 않는다.');
// Recalculation check with a changed count, then restore the input before final verification.
const original=a.getRange('F9').values[0][0];a.getRange('F9').values=[[original+1]];
if(Math.abs(a.getRange('H9').values[0][0]-(original+1)/d.flow[2].baseline_users)>1e-12)throw Error('ratio recalculation failed');
a.getRange('F9').values=[[original]];
wb.recalculate();
const checks=await wb.inspect({kind:'table',range:'대상과 시점!B8:I19',include:'values,formulas',tableMaxRows:12,tableMaxCols:8,maxChars:5000});
await fs.writeFile(path.join(root,'workbook_inspection.ndjson'),checks.ndjson);
const errors=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:50},summary:'Final error scan'});
await fs.writeFile(path.join(root,'workbook_error_scan.json'),errors.ndjson);console.log(errors.ndjson);
for(const [s,last,name] of [[a,37,'flow'],[b,33,'candidates']]){
 const img=await wb.render({sheetName:s.name,range:`A1:J${last}`,scale:1.3,format:'png'});
 await fs.writeFile(path.join(root,`preview_${name}.png`),new Uint8Array(await img.arrayBuffer()));
}
const file=await SpreadsheetFile.exportXlsx(wb);await file.save(path.join(root,'행동흐름과_개입대상.xlsx'));
console.log('exported 2 sheets; count-change recalculation verified');
