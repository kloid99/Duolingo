import fs from 'node:fs/promises';
import path from 'node:path';
import {fileURLToPath,pathToFileURL} from 'node:url';
import {createRequire} from 'node:module';
const root=path.dirname(fileURLToPath(import.meta.url));
const req=createRequire(path.resolve(root,'../statistics/package.json'));
const {Workbook,SpreadsheetFile}=await import(pathToFileURL(req.resolve('@oai/artifact-tool')).href);
const d=JSON.parse(await fs.readFile(path.join(root,'word_performance_results.json'),'utf8'));
const wb=Workbook.create(),a=wb.worksheets.add('같은 단어 개선과 재학습'),b=wb.worksheets.add('단어 간격과 정답률'),c=wb.worksheets.add('대상과 정의');
const font='Malgun Gothic',navy='#334B68';
function put(s,cell,v){s.getRange(cell).values=[[v]];}
function head(s,row,labels){const r=s.getRangeByIndexes(row-1,1,1,labels.length);r.values=[labels];r.format.fill=navy;r.format.font={name:font,size:10,color:'#FFFFFF',bold:true};r.format.horizontalAlignment='center';r.format.rowHeight=30;}
for(const s of [a,b,c]){
 s.showGridLines=false;s.getRange('A1:J41').format.font={name:font,size:10,color:'#24364B'};
 s.getRange('A1:J41').format.rowHeight=26;s.getRange('A1:J41').format.verticalAlignment='center';
 s.getRange('A1:A41').format.columnWidth=3;s.getRange('B1:B41').format.columnWidth=44;
 s.getRange('C1:I41').format.columnWidth=17;s.getRange('J1:J41').format.columnWidth=3;
 s.getRange('B2:I2').format.borders={bottom:{style:'thin',color:'#CCD6E0'}};
 s.getRange('B2').format.font={name:font,size:15,bold:true,color:navy};
}
a.tabColor=navy;put(a,'B2','같은 단어 성과 개선과 이후 재학습');
put(a,'B3','기준 2013.03.01~07 UTC / 결과 03.08~11 UTC / 분석 2026.10.13');
put(a,'B4','개선율: 같은 단어 첫·마지막 날짜 정답률 차이를 마지막 날짜 노출 수로 가중. 대상 단어 5개 이상.');
put(a,'B5','OR은 개선율 +10%p당. 초기 수준·활동량·최근성·관측 기회 등을 보정한 탐색적 연관성.');
put(a,'B6','반복학습 = 추적 4일 중 2일 이상, 재학습 = 1일 이상. 개별 95% 구간, 주요 효과 6개 Holm 보정.');
head(a,8,['보정 모형','사용자','결과 해당 인원','오즈비 OR','95% 하한','95% 상한','Holm p']);
const labels=['습관 형성형 · 5단어 · 반복학습','전체 · 5단어 · 반복학습','습관 형성형 · 10단어 · 반복학습','습관 형성형 · 5단어 · 재학습'];
d.models.slice(0,4).forEach((r,i)=>a.getRange(`B${9+i}:H${9+i}`).values=[[labels[i],r.n,r.events,r.estimate,r.ci_low,r.ci_high,r.p_holm===0?'<1e-300':r.p_holm]]);
a.getRange('C9:D12').setNumberFormat('#,##0');a.getRange('E9:G12').setNumberFormat('0.000');a.getRange('H9:H12').setNumberFormat('0.00E+00');a.getRange('B9:H9').format.fill='#EDF2F7';
put(a,'B14','같은 단어를 맞춰 콘텐츠 구성을 제한했지만 동기·난도·선택 편향까지 제거한 인과 분석은 아님.');
put(a,'B15','최초 시각의 과거 이력이 불명확하면 개선율은 보존하고 사용자 보정 모형에서 제외.');
head(a,18,['습관 형성형 · 개선 사분위','사용자','반복학습 인원','반복학습률','초기 평균','마지막 평균','단어 수 중앙값']);
d.quartiles.forEach((r,i)=>{
 const row=19+i;a.getRange(`B${row}:H${row}`).values=[[r.gain_quartile,r.n,r.repeated,null,r.initial_mean,r.final_mean,r.words_median]];
 a.getRange(`E${row}`).formulas=[[`=D${row}/C${row}`]];
});
a.getRange('C19:D22').setNumberFormat('#,##0');a.getRange('E19:G22').setNumberFormat('0.0%');a.getRange('H19:H22').setNumberFormat('#,##0');
put(a,'B24','사분위 표는 미보정 관측률. 초기 수준과 노출 구성이 다르므로 회귀 결과와 구분.');
put(a,'B26','초기 과거 정답률: 단어별 기준 주간 최초 관측 직전 history 비율을 첫 날짜 노출 수로 가중.');
put(a,'B27','보정: 초기 정답률·제곱, 초기 과거 정답률, 활동일·최근성, 노출·세션·단어 수, 최초 날짜·관측 간격.');
put(a,'B28','기존 3/1~3 대 3/5~7 전체 정답률 변화와 다른 지표. 서로 다른 표본의 OR로 우열을 판단하지 않음.');
put(a,'B30','원천: 원본 학습 추적 CSV, v3 사용자 코호트, docs/03_지표_정의서.md. 결과 JSON에 해시 기록.');
put(a,'B31','모형은 Python 결과 스냅샷. 재실행: analyze_word_performance.py → 검증 → 이 엑셀 생성 코드.');

put(b,'B2','같은 사용자·단어의 복습 간격과 정답률');
put(b,'B3','delta ≥ 60초인 기록만 사용. 서로 다른 첫·마지막 복습 날짜의 정답률과 간격 변화를 짝 비교.');
put(b,'B4','노출 가중 기하평균 간격의 마지막/첫 날짜 비율이 2배일 때 정답률 차이의 변화(%p).');
put(b,'B5','초기 수준·초기 간격·누적 노출 변화·날짜를 보정. 사용자 군집 표준오차로 반복 기록 종속성 반영.');
head(b,7,['가중 방식','사용자','단어 쌍','계수 %p','95% 하한','95% 상한','Holm p']);
d.models.slice(4).forEach((r,i)=>b.getRange(`B${8+i}:H${8+i}`).values=[[r.weighted?'마지막 복습 날짜 노출 가중':'단어 쌍 동일 가중',r.users,r.n,r.estimate,r.ci_low,r.ci_high,r.p_holm===0?'<1e-300':r.p_holm]]);
b.getRange('C8:D9').setNumberFormat('#,##0');b.getRange('E8:G9').setNumberFormat('0.000');b.getRange('H8:H9').setNumberFormat('0.00E+00');
put(b,'B11','동일 사용자·단어의 변화 관계다. 최적 복습 간격, 장기 기억 또는 간격 조절의 인과 효과가 아님.');
put(b,'B12','직접 간격 모형의 표본은 첫 시각 이력이 명확한 복습 단어 쌍 5개 이상 사용자.');
head(b,15,['기술 통계 · 복습 간격','기록 수','사용자','노출 수','정답 수','정답률']);
d.gap_bins.forEach((r,i)=>{
 const row=16+i;b.getRange(`B${row}:G${row}`).values=[[r.gap_bin,r.records,r.users,r.attempts,r.correct,null]];
 b.getRange(`G${row}`).formulas=[[`=F${row}/E${row}`]];
});
b.getRange('C16:F20').setNumberFormat('#,##0');b.getRange('G16:G20').setNumberFormat('0.0%');
put(b,'B22','구간별 사용자·단어 구성이 다르고 사용자가 여러 구간에 나타남. 사용자 수를 합산하지 않음.');
put(b,'B23','위 구간표는 기준 주간 전체 복습 기록. 짝 비교 모형의 제한된 표본과 분모가 다름.');
put(b,'B25','현재 정답률과의 관계를 학습 성과 개선·미래 반복학습으로 연결한 인과 경로로 해석하지 않음.');
put(b,'B26','단어별 delta와 사용자별 timestamp 간격 CV를 혼용하지 않음.');

c.getRange('B1:B41').format.columnWidth=26;c.getRange('C1:I41').format.columnWidth=19;
put(c,'B2','지표 산출 범위와 보정 분석 대상');
put(c,'B3','5단어 개선율 산출 가능자와 초기 과거 이력까지 명확한 보정 모형 대상자를 구분.');
head(c,6,['세그먼트','기준 인원','대상 단어 0개','1~4개','5개 이상','이력 제외','보정 대상','간격 모형 대상']);
const order=['전체','꾸준형','습관 형성형','최근 단발형','멈춤-꾸준형','멈춤-몰입형','멈춤-저활동형'];
const cv=[...d.coverage].sort((x,y)=>order.indexOf(x.segment)-order.indexOf(y.segment));
cv.forEach((r,i)=>{
 const row=7+i;c.getRange(`B${row}:I${row}`).values=[[r.segment,r.baseline_users,r.no_matched_words,r.one_to_four_words,r.eligible_users,r.ambiguous_history_users,null,r.review_eligible_users]];
 c.getRange(`H${row}`).formulas=[[`=F${row}-G${row}`]];
});
c.getRange('C7:I13').setNumberFormat('#,##0');c.getRange('B7:I7').format.fill='#EDF2F7';
const notes=[
 '개선율: 같은 사용자·학습 언어·lexeme_id의 서로 다른 날짜 정답률 차이. 단어별 마지막 날짜 노출 가중.',
 '최초 관측 날짜는 가입일이 아님. user_id+timestamp는 실제 레슨 ID가 아닌 추정 세션.',
 '노출 수는 session_seen 합이며 고유 문제 수와 다름. 기록 부족이나 미관측 개선율을 0으로 바꾸지 않음.',
 '원래 개선율에는 delta 필터를 넣지 않음. 직접 간격 분석만 delta ≥ 60초와 명확한 초기 이력을 요구.',
 `초기 이력 충돌: 개선 단어 쌍 ${d.extraction.ambiguous_matched_words}개, 복습 단어 쌍 ${d.extraction.ambiguous_review_pairs}개.`,
 '가설·모형·6개 검정군을 결과 계산 전에 기록. 추출 중 발견한 이력 모호성 처리만 명시적으로 추가.',
 '사용자 개선율은 user_word_improvement.csv, 단어 쌍은 matched_word_pairs.csv와 review_word_pairs.csv.',
 '같은 단어 기준은 콘텐츠 차이를 줄이지만 모든 난도·노출 선택·측정오차를 통제하지 못함.',
 '기준 주간은 7일, 후속 결과는 4일. 후속 NSM·D7·D30·개입 효과는 검증하지 않음.',
 '공통 지표·기존 분석과의 관계는 v3의 가설과_지표_정의_대조표.md에 기록.'
];notes.forEach((v,i)=>put(c,`B${16+i}`,v));
wb.recalculate();const err=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!',options:{useRegex:true,maxResults:20},summary:'Formula error scan'});
await fs.writeFile(path.join(root,'workbook_error_scan.json'),err.ndjson);console.log(err.ndjson);
for(const [s,last,name] of [[a,33,'improvement'],[b,28,'gap'],[c,27,'coverage']]){
 const img=await wb.render({sheetName:s.name,range:`A1:J${last}`,scale:1.4,format:'png'});await fs.writeFile(path.join(root,`preview_${name}.png`),new Uint8Array(await img.arrayBuffer()));
}
const book=await SpreadsheetFile.exportXlsx(wb);await book.save(path.join(root,'같은단어_성과개선과_복습간격.xlsx'));console.log('exported 3 sheets');
