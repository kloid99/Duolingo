import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(fileURLToPath(import.meta.url));
const req=createRequire(path.resolve(root,'../statistics/package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(path.join(root,'sample_size_results.json'),'utf8'));
const wb=Workbook.create(),s=wb.worksheets.add('표본 수와 모집 기간');
const font='Malgun Gothic',navy='#334B68';
function put(cell,v){s.getRange(cell).values=[[v]];}
function formula(cell,v){s.getRange(cell).formulas=[[v]];}
function head(row,labels){const r=s.getRangeByIndexes(row-1,1,1,labels.length);r.values=[labels];r.format.fill=navy;r.format.font={name:font,size:10,bold:true,color:'#FFFFFF'};r.format.horizontalAlignment='center';r.format.rowHeight=28;}
s.showGridLines=false;s.tabColor=navy;s.getRange('A1:J47').format.font={name:font,size:10,color:'#24364B'};
s.getRange('A1:J47').format.rowHeight=25;s.getRange('A1:J47').format.verticalAlignment='center';
s.getRange('A1:A47').format.columnWidth=3;s.getRange('B1:B47').format.columnWidth=31;
s.getRange('C1:D47').format.columnWidth=18;s.getRange('E1:E47').format.columnWidth=3;
s.getRange('F1:F47').format.columnWidth=28;s.getRange('G1:I47').format.columnWidth=18;s.getRange('J1:J47').format.columnWidth=3;
s.getRange('B2:I2').format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
s.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};
put('B2','A1 실험의 표본 수와 모집 기간');put('B3','양측 α=0.05, 1:1 배정. +3%p는 계획용 가정이며 실제 효과가 아니다. 작성 2026.10.13');
put('B4','총 필요 표본');formula('C4','=IF(C14<>"정상","",2*G4)');put('F4','군별 필요 표본');formula('G4','=IF(C14<>"정상","",CEILING(G12,2))');
s.getRange('C4').format.font={name:font,size:14,bold:true,color:navy};s.getRange('G4').format.font={name:font,size:14,bold:true,color:navy};
s.getRange('C4').setNumberFormat('#,##0');s.getRange('G4').setNumberFormat('#,##0');
const inputs=[['기준률',d.historical_baseline],['탐지 개선 폭',d.config.planning_mde_absolute],['양측 유의수준',d.config.alpha_two_sided],['목표 검정력',d.config.target_power],['실제 신규 자격 인원/일',null],['최소 모집 날짜 수',d.config.minimum_enrollment_utc_days],['수집 지연 대기 날짜 수',d.config.data_lateness_allowance_days],['최대 모집 날짜 수',d.config.maximum_enrollment_utc_days]];
inputs.forEach(([label,value],i)=>{put(`B${6+i}`,label);put(`C${6+i}`,value);});
s.getRange('C6:C13').format.fill='#FFF2CC';s.getRange('C6:C9').setNumberFormat('0.0%');s.getRange('C10:C13').setNumberFormat('#,##0');
s.getRange('C6:C9').dataValidation={rule:{type:'decimal',operator:'between',formula1:0.0001,formula2:0.9999}};
s.getRange('C10:C11').dataValidation={rule:{type:'whole',operator:'greaterThan',formula1:0}};
s.getRange('C12').dataValidation={rule:{type:'whole',operator:'greaterThanOrEqual',formula1:0}};
s.getRange('C13').dataValidation={rule:{type:'whole',operator:'greaterThan',formula1:0}};
put('B14','입력 관계 검증');formula('C14','=IF(COUNT(C6:C9,C11:C13)<>7,"입력 관계 오류",IF(AND(C6>0,C7>0,C6+C7<1,C8>0,C8<1,C9>0.5,C9<1,C11>=1,C13>=C11,C12>=0,MOD(C11,1)=0,MOD(C12,1)=0,MOD(C13,1)=0),"정상","입력 관계 오류"))');
for(const [cell,label,v] of [['G6','안내군 가정 비율','C6+C7'],['G7','두 군 평균 비율','AVERAGE(C6,G6)'],['G8','양측 임계 z','NORM.S.INV(1-C8/2)'],['G9','검정력 z','NORM.S.INV(C9)'],['G10','통합 분산 SD 계수','SQRT(2*G7*(1-G7))'],['G11','군별 분산 SD 계수','SQRT(C6*(1-C6)+G6*(1-G6))'],['G12','군별 표본 반올림 전','((G8*G10+G9*G11)/C7)^2']]){put(`F${cell.slice(1)}`,label);formula(cell,`=IF(C14<>"정상","",${v})`);}
s.getRange('G6:G7').setNumberFormat('0.0%');s.getRange('G8:G11').setNumberFormat('0.000');s.getRange('G12').setNumberFormat('#,##0.0');
put('B15','목표까지 필요한 모집일');formula('C15','=IF(C14<>"정상","",IF(ISBLANK(C10),"",IF(NOT(ISNUMBER(C10)),"양수 입력",IF(C10<=0,"양수 입력",MAX(C11,ROUNDUP(C4/C10,0))))))');
put('B16','표본 충족 여부');formula('C16','=IF(C14<>"정상","입력 관계 오류",IF(ISBLANK(C10),"유입량 미입력",IF(NOT(ISNUMBER(C10)),"양수 입력",IF(C10<=0,"양수 입력",IF(C15>C13,"상한 내 표본 부족","기간 내 충족 가정")))))');
put('B17','상한 적용 모집일');formula('C17','=IF(C14<>"정상","",IF(NOT(ISNUMBER(C10)),"",IF(C10<=0,"",MIN(C15,C13))))');
put('B18','주 결과 확인까지 일수');formula('C18','=IF(C17="","",SUM(C17,2,C12))');
put('B19','보조 NSM 확인까지 일수');formula('C19','=IF(C17="","",SUM(C17,7,C12))');
s.getRange('C15:C18').setNumberFormat('#,##0');
put('F15','노란 입력 칸을 바꾸면 표본과 기간이 다시 계산된다.');
put('F16','기준률+개선 폭<100%, 검정력>50%를 유지한다.');
put('F17','미입력·0 유입량은 확정 기간으로 계산하지 않는다.');
put('F18','기간 상한 초과는 계획 검정력을 충족한다는 뜻이 아니다.');
head(21,['개선 폭','검정력','안내군 가정율','두 군 평균','통합 SD','군별 SD','군별 표본','총 표본']);
s.getRange('E21:E27').format.columnWidth=18;
d.scenarios.forEach((r,i)=>{
 const row=22+i;s.getRange(`B${row}:I${row}`).values=[[r.mde,r.target_power,null,null,null,null,null,null]];
 formula(`D${row}`,`=$C$6+B${row}`);formula(`E${row}`,`=AVERAGE($C$6,D${row})`);
 formula(`F${row}`,`=SQRT(2*E${row}*(1-E${row}))`);formula(`G${row}`,`=SQRT($C$6*(1-$C$6)+D${row}*(1-D${row}))`);
 formula(`H${row}`,`=CEILING((($G$8*F${row}+NORM.S.INV(C${row})*G${row})/B${row})^2,2)`);formula(`I${row}`,`=2*H${row}`);
});
s.getRange('B22:E27').setNumberFormat('0.0%');s.getRange('F22:G27').setNumberFormat('0.000');s.getRange('H22:I27').setNumberFormat('#,##0');s.getRange('B23:I23').format.fill='#EDF2F7';
head(30,['신규 자격/일 가정','필요 모집일','상한 내 가능','상한 적용일','결과 확인일','기간 성격']);
d.timing_scenarios.forEach((r,i)=>{
 const row=31+i;put(`B${row}`,r.assumed_daily_new_eligible);
 formula(`C${row}`,`=MAX($C$11,ROUNDUP($C$4/B${row},0))`);
 formula(`D${row}`,`=IF(C${row}<=$C$13,"가능 가정","표본 미달")`);
 formula(`E${row}`,`=MIN(C${row},$C$13)`);formula(`F${row}`,`=SUM(E${row},2,$C$12)`);put(`G${row}`,'가정, 실제 일정 아님');
});
s.getRange('B31:C33').setNumberFormat('#,##0');s.getRange('E31:F33').setNumberFormat('#,##0');
s.getRange('D31:D33').format.horizontalAlignment='center';s.getRange('G31:G33').format.horizontalAlignment='center';
put('B35','기준률 45.6%: 3/8·9 재개, 비활동 1~2일의 조건부 기록 비율. 실제 대상에서 재산출 필수.');
put('B36','방법: 통합 영가설 분산·군별 대립가설 분산 정규근사. 전체 무작위 블록 4명에 맞춘 올림.');
put('B37','자료: https://www.statsmodels.org/stable/generated/statsmodels.stats.proportion.power_proportions_2indep.html');
put('B38','모집 최소 14일·최대 28일·수집 지연 대기 2일은 작성 가정. 실제 신규 자격 규모·개시일은 미확인.');
put('B39','역사적 4,809명은 새 실험의 대조·안내 데이터가 아니다. 실제 모집단 규모와 기록 연결이 필요하다.');
put('B40','유입량 가정은 주후보 A1의 새 고유 사용자 수다. 전체 방문자나 기존 대상 누적 수를 쓰지 않는다.');
// Check input changes against independent JSON outputs; restore every value before export.
const check=(cell,expected)=>{const value=s.getRange(cell).values[0][0];if(typeof expected==='number'?Math.abs(value-expected)>1e-8:value!==expected)throw Error(`${cell}: ${value} != ${expected}`);};
check('C4',d.default.n_total);check('G4',d.default.n_per_arm);
put('C7',0.02);check('C4',d.scenarios[0].n_total);put('C7',d.config.planning_mde_absolute);
put('C10',500);check('C15',18);check('C18',22);put('C10',100);check('C15',87);check('C17',28);check('C18',32);check('C16','상한 내 표본 부족');
put('C10',0);check('C16','양수 입력');put('C10',null);check('C16','유입량 미입력');
const blank=(cell)=>{const v=s.getRange(cell).values[0][0];if(v!==null&&v!=='')throw Error(`${cell}: invalid input produced ${v}`);};
put('C13',7);check('C14','입력 관계 오류');check('C16','입력 관계 오류');blank('C4');blank('C18');put('C13',d.config.maximum_enrollment_utc_days);
put('C7',0.6);check('C14','입력 관계 오류');blank('G12');put('C7',d.config.planning_mde_absolute);
put('C9',0.5);check('C14','입력 관계 오류');blank('G9');put('C9',d.config.target_power);
put('C12',-1);check('C14','입력 관계 오류');put('C12',d.config.data_lateness_allowance_days);
check('C14','정상');put('C10',500);check('C19',27);put('C10','unknown');check('C16','양수 입력');blank('C18');put('C10',null);
// Guard every scenario formula as well as the main calculator.
for(let row=22;row<=27;row++)for(const col of ['D','E','F','G','H','I']){const cell=`${col}${row}`;const f=s.getRange(cell).formulas[0][0];formula(cell,`=IF(OR($C$14<>"정상",$C$6+B${row}>=1),"",${f.slice(1)})`);}
for(let row=31;row<=33;row++)for(const col of ['C','D','E','F']){const cell=`${col}${row}`;const f=s.getRange(cell).formulas[0][0];formula(cell,`=IF($C$14<>"정상","",${f.slice(1)})`);}
put('C13',7);blank('I22');blank('F31');put('C13',d.config.maximum_enrollment_utc_days);check('C4',d.default.n_total);
wb.recalculate();
const inspection=await wb.inspect({kind:'table',range:'표본 수와 모집 기간!B21:I27',include:'values,formulas',tableMaxRows:7,tableMaxCols:8,maxChars:5000});await fs.writeFile(path.join(root,'workbook_inspection.ndjson'),inspection.ndjson);
const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:50},summary:'Final formula error scan'});await fs.writeFile(path.join(root,'workbook_error_scan.json'),err.ndjson);console.log(err.ndjson);
const img=await wb.render({sheetName:s.name,range:'A1:J42',scale:1.4,format:'png'});await fs.writeFile(path.join(root,'preview_sample_size.png'),new Uint8Array(await img.arrayBuffer()));
const output=await SpreadsheetFile.exportXlsx(wb);await output.save(path.join(root,'A1_실험표본수와_기간산정.xlsx'));
console.log('Workbook exported; MDE/inflow/blank/zero/cap recalculation verified.');
