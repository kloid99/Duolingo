# OneDrive 재실행 안내

2026-10-13. 워크스페이스는 `C:\Users\USER\OneDrive\마케팅`, v3은 그 아래 `cohort_v2`다. 역사적 원천과 기존 분석 결과는 보존한다. 기본 실행은 최신 최종 패키지의 검증이며 전체 원본 재분석은 수행하지 않는다.

## 1. 기본 검증

PowerShell에서 아래를 실행한다. 실행 스크립트는 자신의 경로를 기준으로 파일을 찾으므로 D: 경로가 필요하지 않다.

```powershell
Set-Location -LiteralPath 'C:\Users\USER\OneDrive\마케팅'
& '.\cohort_v2\final_delivery\run_final_delivery.ps1'
```

기본 Verify는 **기존 manifest를 먼저 비교하고 최종 패키지를 수정하지 않는다.** 최신 설정/주 결과 입력 해시, 저장 엑셀, 보고서 표의 라벨·값·단위·기간·분모, 기존 산출물·보완 분석 해시를 검사한다. 이어 독립 표본 계산, 측정 경계 38개, 부정 입력 15개를 검증한다. manifest·validation JSON은 덮어쓰지 않으며 별도 감사 기록은 v3/corrections/audits에 저장한다. 실제 배정·발송·외부 서비스 연결은 수행하지 않는다.

런타임 경로를 지정할 수도 있다.

```powershell
& '.\cohort_v2\final_delivery\run_final_delivery.ps1' `
  -PythonPath 'C:\Users\USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' `
  -NodePath 'C:\Users\USER\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
```

## 2. 최종 패키지 재생성

현재 입력과 원천을 이용해 최종 보고서·계획·엑셀을 다시 생성할 때만 RebuildFinal을 지정한다. 기존 기초 분석이나 세그먼트를 재계산하지 않는다.

```powershell
& '.\cohort_v2\final_delivery\run_final_delivery.ps1' -RebuildFinal
```

순서: 역사적 A1 이벤트 캐시/해시 확인 → 보완 민감도 분석(검증한 원본 언어·104명 캐시 재사용) → 계획/수치 목록 → 보고서/그림 → 엑셀 → 수치/측정/의미 검증 → 저장 파일 검증 → **Build에서만 새 manifest 생성**. 원본이 기존 해시와 다르면 중단한다. 바뀐 원천으로 분석하려면 별도 버전·출력 폴더를 먼저 정하고 이전 결과를 덮어쓰지 않는다. 설정을 바꾼 뒤 재생성하지 않으면 Verify가 실패하는 것이 정상이다.

## 3. 필요한 의존성

- Python: 위 bundled runtime. NumPy·pandas는 이 런타임에서 읽는다. 최종 계획·측정 검증은 표준 라이브러리와 NumPy를 사용한다.
- 그림: 현재 bundled Python에 matplotlib가 없어서 기존 `cohort_v1\tmp\python_deps`의 matplotlib를 추가 사용했다. build_final_report.py는 이 경로를 읽으며 bundled NumPy를 먼저 가져온다. Windows Malgun Gothic 폰트와 v3/tmp/mplconfig를 사용한다.
- 이전 회귀 검증: 일부 SciPy 모듈은 `cohort_v2\tmp\python_deps`에서 읽는다. 기존 회귀 스크립트의 수치 계산 함수가 이 의존성을 호출할 수 있다.
- 엑셀: bundled Node와 `@oai/artifact-tool`. 현재 `statistics\node_modules` junction을 통해 bundled node_modules를 참조한다. 최종 builder도 이 연결을 사용한다.

다른 PC로 옮겼다면 데이터와 스크립트만으로 의존성이 모두 포함되는 것은 아니다. 런타임·위 라이브러리 경로를 복구하고 preflight를 통과시킨다. 의존성 디렉터리를 임의 변경하거나 새 패키지를 자동 설치하지 않는다. OneDrive 원천 파일은 오프라인에서도 읽을 수 있도록 내려받은 상태여야 한다.

Codex sandbox 안에서 기존 의존성 읽기가 대기한 사례가 있다. 이번 최종 보고서 그림은 승인된 호스트 실행에서 생성했다. 동일 현상이 생기면 중복 실행을 계속 만들지 말고 진행 중인 프로세스를 확인한 뒤 호스트 PowerShell에서 같은 명령을 실행한다.

## 4. 기존 분석을 재실행할 때의 순서

다음은 현재 v3 기준 단계별 실행 파일이다. 원천·조건이 바뀌지 않으면 모두 다시 돌릴 필요가 없다. stage별 기존 출력 폴더는 날짜가 고정돼 있으며 변경 데이터의 버전 관리 없이 재사용하면 안 된다.

| 분석 | Python 집계·분석 | 독립 검증 | Node 엑셀 생성 | 저장 파일 검증 |
|---|---|---|---|---|
| 기초 코호트 | analyze_retention.py | 분석 내부 checks | build_retention_workbook.mjs | results_retention.json과 manifest_retention.json |
| 세그먼트 통계 | analyze_cohort_statistics.py | 분석 내부 checks | statistics/build_statistics_workbook.mjs | 같은 폴더 verify_statistics_workbook.py |
| 비활동 | analyze_inactivity_sensitivity.py | 분석 내부 checks | sensitivity/build_sensitivity_workbook.mjs | 같은 폴더 verify_sensitivity_workbook.py |
| 세션 간격 | analyze_regularity.py | regularity/verify_regularity.py | 같은 폴더 build_regularity_workbook.mjs | 같은 폴더 verify_regularity_workbook.py |
| 전체 정답률 | analyze_accuracy_change.py | verify_accuracy_analysis.py | accuracy_change/build_accuracy_workbook.mjs | 같은 폴더 verify_accuracy_workbook.py |
| 같은 단어 | analyze_word_performance.py | verify_word_performance.py | word_performance/build_word_workbook.mjs | 같은 폴더 verify_word_workbook.py |
| 행동 흐름 | analyze_behavior_flow.py | behavior_flow/verify_behavior_flow.py | 같은 폴더 build_behavior_workbook.mjs | 같은 폴더 verify_behavior_workbook.py |

Python 파일은 v3 경로, Node 파일은 표에 적힌 해당 폴더를 기준으로 호출한다. 세그먼트 재구성은 run_segment_revision.py와 segmentation 코드가 별도 단계이며 최종 패키지 검증에서 실행하지 않는다. 기초 코호트 그래프는 plot_retention.py다.

## 5. 검증 범위

표본 수 계산은 정규근사 식·독립 정수 탐색·100,000회 이항 모의 검증을 사용했다. 모의 결과는 실제 실험 효과가 아니다. 엑셀은 Artifact Tool의 입력 변경 재계산과 저장 XML의 값·수식 캐시를 대조했고 실제 Excel 앱에서의 실행 검증은 수행하지 않았다.

기존 개별 분석의 manifest 해시는 당시 산출물을 검증한다. 역사적 D: 경로나 미완료 문구를 현재 작업 상태로 읽지 않는다. 최신 수치·읽는 순서·완료 상태는 최종 보고서와 최종 산출물 인덱스를 기준으로 확인한다.

추가 코드: report_semantics.py(8개 구조 표·기간/분모 계약), verify_semantic_integrity.py(메모리 안 라벨/단위/기간/분모/설정/입력/manifest 변조 반례), corrections/analyze_robustness.py(주 모형 5개 재현·추가 8개 민감도·CV 형태 진단). 기존 원본 분석 폴더는 읽기만 한다. prior_final_delivery_manifest.json과 prior_documents는 수정 전 검토 기록으로 보존했다.

실험 준비 확인은 validate_experiment_config.py이며 --require-ready를 주면 8개 외부 검증 gate와 실제 유입량·개시일 미확인 시 종료 코드 2로 실패한다. 이 상태는 코드 오류가 아니라 실제 서비스 연결·사업 승인 대기를 뜻한다. 주 지표는 D3+48시간, 보조 D1~D7 NSM은 D8+48시간 후 각각 확정한다. 현재 자료로 후속 7일 실제 결과는 생성하지 않는다.
