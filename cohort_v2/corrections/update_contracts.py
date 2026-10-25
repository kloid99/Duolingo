from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent;DEL=ROOT.parent/'final_delivery'
p=DEL/'experiment_config.json';c=json.loads(p.read_text(encoding='utf-8'))
c.update(status='designed_launch_blocked_pending_validation',historical_baseline_scope='2013-03-08/09 최초 재개·직전 비활동 1~2일의 완전 관측 표본 한정',inactivity_gap_strata=[1,2,'3+'],secondary_day_offsets=list(range(1,8)),secondary_minimum_active_days=4,secondary_metric='D1~D7 중 4일 이상 유효 서비스 학습 날짜 / 모든 배정자. [D1 00:00,D8 00:00), D8+지연 대기 후 판정',guardrail_investigation_absolute=0.01,guardrail_status='작성 가정·사업 승인 미확인',launch_gates={k:None for k in ['service_event_contract_verified','coverage_and_identity_verified','target_baseline_recalibrated','business_mde_approved','guardrail_thresholds_approved','actual_pool_and_inflow_verified','card_usability_and_date_choices_verified','assignment_and_exposure_integration_verified']})
p.write_text(json.dumps(c,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
supplement='''

## 2026-10-13 검토 보완: 적용 범위와 실행 차단 조건

공개 파일의 비활동은 **유효 단어 lesson/practice 기록이 없는 완전 UTC 날짜**다. 앱 미사용·모든 학습 부재·영구 이탈을 뜻하지 않는다. 원본의 최초 단어 노출 포함 여부와 모든 세션 coverage는 검증되지 않았다. 현재 주간 NSM 9,834명도 관측 기록 기준 지표다.

A1 자격은 비활동 1일 이상을 유지한다. 45.6%는 3/8·9 재개 및 비활동 1~2일의 조건부 비율이다. 전체 후보 4,809명 중 1,929명(40.1%)은 완전 D1·D2가 없다. 날짜별 비율은 3/8 549/1,307=42.0%, 3/9 763/1,573=48.5%; 3/10·11은 미확인이다. 비활동 3일 이상 결과를 0으로 채우거나 짧은 비활동으로 자격을 사후 축소하지 않는다.

실제 서비스의 고정 주간 대상에서 **카드 없는 사전 관측 기간**을 먼저 확보한다. 모집 예정 14~28일의 날짜별 신규 고유 자격 수·비활동 1일/2일/3일 이상·지원 앱 구성·자격 모수와 D1·D2 기준률을 측정한다. 각 층의 n/K/coverage/미확인 수를 보고하고, 예정 모집 구성으로 전체 기준률을 다시 산출한다. 모든 결과는 D3+지연 대기 후 확정한다. 표본 부족·coverage 미확인 층이 있으면 모집 기간/범위를 사전에 재설계하고 계획을 다시 생성한다. 43.7~47.4% 구간에 따른 총 표본 8,640~8,716명은 기존 표본의 통계적 민감도이며 모집단 이동 오차를 해결하지 않는다.

설정의 launch_gates가 모두 true이고 실제 유입량·개시일이 있어야 실행 검토가 가능하다. 사업적 MDE +3%p, 가드레일 조사 +1%p, 모집 14~28일은 승인 전 작성 가정이다. 현재 gate는 null로 두며 자동 실행·효과·안전성 확인으로 간주하지 않는다. `validate_experiment_config.py --require-ready`는 미확인 입력이 남으면 실패한다.

## 후속 7일 NSM과 날짜 선택

보조 NSM은 모든 배정자를 분모로 D1~D7의 유효 서비스 학습 날짜가 4일 이상인지 측정한다. 구간은 [D1 00:00,D8 00:00), 판정은 D8+48시간 이후다. 수집 미확인은 None으로 유지하고 군별 K/N~(K+M)/N을 보고한다. D0는 제외하며 같은 날짜의 여러 사건은 1일이다. 주 지표의 유의성만으로 NSM 개선을 선언하지 않는다. 마지막 배정 이후 보조 결과에는 7일 추적+2일 대기가 필요하다.

UI에서는 D1·D2 UTC 구간과 교집합이 있는 사용자 현지 날짜만 제공한다. 각 날짜의 허용 시각 구간을 서버에서 계산해 보존하며, 현지 날짜 일부가 측정 구간 밖일 수 있음을 날짜 표시/선택 가능 시간으로 안내한다. 미래의 임의 날짜는 선택할 수 없다. 사용자의 timezone을 저장하고 DST도 시간대 데이터로 변환한다. 제목/본문은 기존 쉬운 문구를 유지한다. UI와 주 측정 기간의 일치는 출시 전 사용성·경계 테스트 gate다.
'''
for name in ['A1_실험명세서.md','운영_연결과_미확인입력.md']:
    p=DEL/name;p.write_text(p.read_text(encoding='utf-8')+supplement,encoding='utf-8')
p=DEL/'A1_실험명세서.md';t=p.read_text(encoding='utf-8').replace('7일 중 4일 이상 학습은 추가 기간을 확보했을 때만 탐색적 중기 결과로 기록한다.','후속 D1~D7의 4일 이상 학습을 탐색적 보조 NSM으로 수집하며, 구간·판정은 아래 보완 계약을 따른다.');p.write_text(t,encoding='utf-8')
p=DEL/'측정과_로그_명세.md';t=p.read_text(encoding='utf-8').replace('date_utc, complete, checked_at_utc, incident_id','date_utc, version, complete, checked_at_utc, incident_id').replace('UTC 날짜당 1개 최종 판정.','UTC 날짜+양의 정수 version 고유. 버전 증가 시 확인 시각 단조 증가.').replace('데이터 동결 시각이 D3 00:00 이전','데이터 동결 시각이 D3 00:00+48시간 이전').replace('기간 종료·coverage 완전','지연 대기 종료·동결 당시 coverage 완전')
t+='''

## 강화된 학습 사건·coverage 계약

서비스 learning_recorded는 최초/재노출 단어와 무관하게 완료된 유효 학습 세션을 서버가 확인한 사건이다. session_id, event_id, user_id, session_type, occurred_at_utc, received_at_utc, schema_version을 보존한다. 중복 전송은 event_id로 제거하고 테스트/자동화/무효 세션은 valid=false 및 사유를 기록한다. 단순 앱 열기나 카드 선택은 학습 사건이 아니다. 단어 로그와 세션 계약은 같다고 가정하지 않는다.

실제 서비스 기준 주간에서 전체 학습 세션의 사용자-UTC날짜 집합과 공개 자료 방식의 단어 기록 집합을 비교해 일치/세션만/단어만의 수와 이유를 기록한다. 최초 학습·지원 앱·언어별 누락을 검사하고, 이 검증과 수집 완전성 점검이 통과되기 전 서비스 NSM으로 적용하지 않는다. 실제 비교 수치는 현재 없다.

coverage는 해당 UTC 날짜가 끝난 후 checked_at_utc를 기록한다. 동일 날짜 버전 중 동결 시각 이하 최신 버전만 사용한다. 미래 버전은 사용하지 않는다. 이전 true를 최신 false가 번복하면 미확인이다. 시각·버전 누락, 중복 버전, 역행 확인 시각은 입력 오류로 중단한다. 최소 48시간 대기와 coverage 둘 다 충족해야 0/1을 확정한다. 동결 이후 도착 사건은 그 동결 결과에서 제외한다. coverage의 완전성 판정이 나중에 잘못으로 확인되면 새 버전과 새 동결 분석을 남기고 과거 결과를 덮어쓰지 않는다.

measurement_reference.evaluate의 data_lateness_allowance_days는 기본 2일이며 실행 설정과 같아야 한다. D1·D2 주 결과와 D1~D7 4일 이상 보조 NSM을 모두 반환한다. 보조 NSM에도 모든 배정자·동일 coverage 버전·지연 대기를 적용한다. 주 결과는 D3+2일, 보조 결과는 D8+2일 전까지 각각 미확인이다.
''';p.write_text(t,encoding='utf-8')
(ROOT/'관측지표_현행정의.md').write_text('''# 관측 기록 지표의 현행 해석

2026-10-13. 기존 정의 문서와 주 분석은 역사적 스냅샷으로 보존한다. 현재 최종 해석에는 이 보완을 함께 적용한다.

| 지표 | 현재 자료에서의 정의 | 적용 범위 |
|---|---|---|
| 활동 날짜 | 해당 공개 파일의 유효 학습 단어 기록이 1행 이상인 UTC 날짜 | 전체 서비스 세션 coverage 미검증 |
| 비활동 날짜 | 유효 기록이 없는 완전 UTC 날짜 | 앱 미사용·모든 학습 부재·영구 이탈 주장 불가 |
| 기준 NSM | 2013-03-01~07 중 기록 활동 날짜≥4인 9,834명 | 관측 기록 기준, 실제 서비스 NSM으로 확정 불가 |
| 반복학습 | 2013-03-08~11 중 기록 활동 날짜≥2 | 후속 7일 NSM 대체 불가 |
| A1 D1·D2 | 첫 재개 다음 두 UTC 날짜의 기록≥1 | 완전 관측은 3/8·9, 비활동 1~2일 표본만 |

최초 단어 노출 행이 없다는 관측은 모든 사용자 세션이 누락됐다는 증거가 아니다. 다만 전체 세션을 모두 포괄한다는 증거도 없다. 신규 서비스에서는 완료된 학습 세션 계약과 사용자-날짜 일치/누락 검사 후 지표를 다시 계산한다.
''',encoding='utf-8')
print('Config and current contracts updated; historical definitions preserved.')
