# Oddo (오또) — 팀 개발 온보딩 / 에이전트 전체 컨텍스트

> **이 문서는 무엇인가**
> Oddo 프로젝트를 처음 받는 사람과 그 사람의 **AI 코딩 에이전트**가, 프로젝트를 처음부터 만든
> 사람과 **동일한 전체 맥락**을 가지고 개발을 시작하도록 만든 단일 온보딩 문서입니다.
>
> - **Claude Code 사용자**: 이 파일은 프로젝트 루트의 `CLAUDE.md`라서 에이전트가 **자동으로 읽습니다.** 별도로 붙여넣을 필요 없음.
> - **다른 에이전트 사용자**: 이 파일 **전체를 첫 프롬프트(시스템/첫 메시지)로 붙여넣고** 시작하세요.
> - 사람도 그냥 위에서부터 읽으면 프로젝트 전체가 파악됩니다.

---

## 0. 시작하기 전에 — 반드시 먼저 읽을 것

작업 시작 전, 아래를 **이 순서대로** 읽어 맥락을 잡으세요. (이 폴더들은 **읽기 전용 자료**입니다 — §9 참고)

1. 이 `CLAUDE.md` 전체
2. `_docs/01_전체_페이지_흐름.md` → `_docs/02_관련_화면_설명_및_이동_흐름.md` → `_docs/03_핵심_플로우_요약.md` → `_docs/04_공통_디자인_톤.md` → `_docs/05_Oddo_전체_사용_흐름.md`
3. `_docs/flowchart.png`, `_docs/character_sheet.png` (마스코트 16포즈 시트), 필요시 `_docs/thesis.pdf` (방법론)
4. `TANKACHU_POSES.md` (화면별 마스코트 포즈 / 에셋 교체 지점 핸드오프 목록)
5. `_screens/` (디자인 시안 50장, 번호 = 화면 번호) — **참조만**

---

## 1. 프로젝트 개요

**Oddo(오또)** 는 Flutter로 만드는 **AI 감정 일기** 모바일 앱입니다. 마스코트는 **탄카츄(Tankachu)** — 갈색 쿼카 느낌 캐릭터(`_docs/character_sheet.png`에 16포즈).

핵심 플로우는 두 가지입니다.

1. **신규 사용자 온보딩**
   스플래시 → 로그인/회원가입(소셜) → 홈 → "Baseline 측정 필요" 팝업 → 권한 안내 → 튜토리얼 1~5 → 얼굴/음성 baseline 측정 → 심리테스트(Big5/MBTI/성향) → 챗봇 페르소나 설정 → 온보딩 완료 → 홈
2. **일일 감정 기록 루프**
   홈(달력) → Step1 말하기(영상통화형, STT) → Step2 확인하기(+추가질문 채팅) → Step3 영상 제작 → Step4 상담(영상통화) → 감정 리포트/행동 가이드 → 홈(작성일 상태)

방법론(논문 기반): 음성(피치/속도/에너지), 표정(FACS AU/랜드마크), STT, Text-to-Video, SFT 상담 봇, baseline을 비교 기준으로 사용 — 자세한 건 `_docs/03`, `_docs/thesis.pdf`.

> **구현 기술 확정 현황**(2026-07-29 팀원 A 피드백 반영): STT=**Naver CLOVA Speech 확정**, 텍스트 감정=AI Hub 감성대화 말뭉치+**ALBERT 계열**(최종 모델·담당 팀 재확인 중, KoBERT 아님), 상담봇=**SFT 파인튜닝**(담당 다경), T2V=Veo 후보. 발표용 정확도는 과장 금지 — 멀티모달 73~83%/인간 72% 기준. **확정/미확정·미해결 팀 결정은 `ROADMAP.md`가 단일 기준**.

---

## 2. 현재 상태 (★ 매우 중요 — 어디까지 됐는지, 2026-07-18 기준)

**Phase-1(프로토타입)을 지나 실서비스 전환(Phase 0~3) 완료 상태**입니다. 상세 진행 현황·다음 단계는 **`ROADMAP.md`가 단일 기준**.

- ✅ 화면 53개 + 라우트 52개 전부 구현 (go_router, 스모크 테스트가 전 라우트 빌드 검증)
- ✅ **실제 인증**: Firebase Auth 이메일·Google·Kakao(OIDC) 로그인/가입/자동 로그인/탈퇴, 라우터 가드 동작 (`AppConfig.dev.useDummyData=false` — dev도 실데이터)
- ✅ **실제 데이터**: 일기/리포트/상담록이 Firestore(`FIRESTORE_SCHEMA.md`)에 날짜별 저장·조회, 작성일 집합·온보딩·페르소나 **영구 저장** (재시작 유지)
- ✅ **디바이스**: 카메라/마이크 실권한 요청, 통화형 화면 카메라 프리뷰, 마이크 녹음(파일 로컬 보관 — Phase 4에서 AI 서버 업로드)
- ✅ 보라 테마(#7C5CF6) + 탄카츄 실제 포즈 아트 17종 실장
- ✅ 설정/알림/마이페이지 실화면, 도움말·약관 등 죽은 버튼 없음
- ✅ 검증 통과 유지: `flutter analyze` clean / `flutter test` 53개 / debug APK 빌드

**아직 안 된 것 (= Phase 4~8, `ROADMAP.md` 참고):**

- **AI 콘텐츠 생성** — STT, 요약/키워드/점수, 상담봇 대화, 리포트 문구, baseline 분석은 아직 **샘플 콘텐츠로 저장**됨 (구조·저장은 실제). Phase 4(FastAPI 서버)~5에서 실생성으로 교체
- 심리테스트 실제 문항/채점 (Phase 6 — 문항 자료 팀 논의 중)
- 숏폼 실제 영상(T2V, 립싱크+한국어 대사 요구), 일러스트 7곳, 앱 아이콘, 정식 약관 (Phase 8)

> 한 줄 요약: **"로그인부터 기록·저장까지 진짜로 돌아간다. AI가 채울 '내용물'만 샘플이다."**

---

## 3. 기술 스택 & 실행

- **Flutter 3.41.9 / Dart 3.11.5** (정확한 버전은 `flutter --version`으로 확인)
- 주요 의존성(`pubspec.yaml`이 기준): `flutter_riverpod`, `go_router`, `firebase_core/auth/cloud_firestore`, `google_sign_in`, `kakao_flutter_sdk_user`, `camera`, `record`, `permission_handler`, `speech_to_text`, `dio`, `shared_preferences`, `video_player`, `url_launcher`, `package_info_plus` 등
- 진입점: `lib/main.dart` → `bootstrap(AppConfig.dev)` — **dev도 실제 Firebase 사용** (`useDummyData=false`; 더미는 테스트 전용). prod는 `main_prod.dart` + `--dart-define=ODDO_API_BASE_URL`
- 백엔드: Firebase 프로젝트 `oddo-emotion-diary` (Auth + Firestore, 보안 규칙은 레포의 `firestore.rules`)
- ⚠️ 팀원이 자기 기기에서 **구글/카카오 로그인 테스트**하려면 본인 디버그 키 지문 등록 필요(팀장에게 SHA-1·키 해시 전달 — PR #5/#6 본문에 추출 명령). 이메일 로그인은 등록 없이 동작

```bash
flutter pub get        # pull 후 최초 1회
flutter run            # 시뮬레이터/기기에서 실행
flutter analyze        # 정적 분석
flutter test           # 위젯/라우트 스모크 테스트
```

---

## 4. 폴더 구조 (feature-first)

```
lib/
  main.dart                  # dev flavor 진입점 → bootstrap(AppConfig.dev)
  app/
    app.dart                 # bootstrap(): ProviderScope + MaterialApp.router
    router/
      app_routes.dart        # ★ AppRoute(이름) + AppPath(경로) 중앙 상수
      app_router.dart        # ★ goRouterProvider — 모든 GoRoute 정의
      route_guard.dart       # redirect 가드 자리(현재 null 반환 — 로그인 상태 체크 자리)
  core/
    config/                  # AppConfig(dev/staging/prod), appConfigProvider, useDummyData 스위치
    constants/               # app_assets.dart(MascotPose enum, 에셋 경로), app_durations.dart
    error/                   # AppException, Failure
    network/                 # api_client.dart (비어 있음 — 실 API 자리)
    utils/                   # date_formatter.dart 등
  data/
    dummy/                   # ★ 모든 더미 데이터. *Dummy / DummySeed 클래스
  features/<기능>/
    presentation/screens/    # 화면 위젯
    presentation/widgets/    # 그 기능 전용 위젯
    application/             # 그 기능의 Riverpod provider/notifier
    data/{datasources,models,repositories}/   # (auth, diary에만 스캐폴드 존재)
  theme/                     # ★ 디자인 토큰: app_colors/spacing/radius/typography + app_theme
  widgets/                   # ★ 앱 전역 공통 위젯 (+ index.dart 배럴)
```

기능 폴더: `auth, baseline, calendar, diary, home, notifications, onboarding, persona, psych_test, records, settings, tutorial`.

---

## 5. 아키텍처 규칙 (★ 반드시 준수 — 코드 일관성의 핵심)

신규 코드는 **주변 코드와 똑같은 스타일/관례**로 작성하세요. 구체 규칙:

### 5.1 라우팅
- 경로/이름은 **`lib/app/router/app_routes.dart`의 `AppPath`/`AppRoute` 상수만** 사용. 문자열 하드코딩 금지.
- 화면 정의는 **`app_router.dart`** 한 곳에 모음.
- 이동은 항상 **`context.goNamed(...)` / `context.pushNamed(...)` / `context.pushReplacementNamed(...)`** (이름 기반). `context.go('/path')` 같은 경로 직접 사용 금지.
- 새 화면 추가 절차: ① `AppRoute`·`AppPath`에 상수 추가 → ② `app_router.dart`에 `GoRoute` 추가 → ③ `test/route_smoke_test.dart`가 자동으로 그 경로를 빌드 검증하도록 경로 목록에 맞춰 둠.

### 5.2 상태관리 (Riverpod 3.x)
- `Notifier` / `NotifierProvider` 사용. 화면은 필요 시 `ConsumerWidget` / `ConsumerStatefulWidget`.
- 기능별 provider는 `features/<기능>/application/`에 둠.
- 여러 화면이 공유하는 상태는 provider로 (생성자 인자로 넘기지 말 것 — go_router가 같은 경로의 State를 재사용해서 인자가 한 번만 읽히는 버그가 남). §6 참고.

### 5.3 디자인 토큰 (`lib/theme/`)
- 색/여백/모서리/타이포는 **반드시 토큰 사용**. 매직 넘버·하드코딩 색 금지.
  - `AppColors` — **메인 컬러 `#7C5CF6`**(primary, 보라 — 2026-07 파랑에서 전환), `primarySoft #F0EBFE`, `authBackground`, `callBackground`(다크) 등
  - `AppSpacing`(+ `Gap.h8/h12/...` 헬퍼), `AppRadius`, `AppTypography`
- 공통 배경 크롬은 `AppBackground`(연한 하늘색 + 구름) 위젯.

### 5.4 데이터 레이어 / 더미
- 더미 데이터는 **`lib/data/dummy/`** 에만 추가 (`home_dummy`, `calendar_dummy`, `records_dummy`, `diary_flow_dummy`, `dummy_seed` 등).
- 실서비스 전환 시드는 이미 깔려 있음: **Repository ← DataSource ← Dummy** 패턴 + `AppConfig.useDummyData` 스위치. **단, 현재 auth·diary에만 스캐폴드가 있고 화면에서 소비하지 않음.** 실전환은 §12 참고.

### 5.5 공통 위젯
- 두 화면 이상에서 반복되는 UI는 **`lib/widgets/`로 추출**하고 `widgets/index.dart` 배럴에 등록.
- 기존 공통 위젯을 먼저 찾아 재사용: `PrimaryButton`/`SecondaryButton`/`BottomActionBar`, `OddoCard`, `OddoChip`, `OddoTextField`, `AppBackground`, `CardSectionHeader`, `InfoCallout`, `StepProgressBar`/`StepIndicator`, `MascotImage`, `DiaryBottomNav`, `video_call_widgets`(CallStatusRow/CallChip/CallUserPreview/CallControlButton), `ChatBubble`, `PlaceholderScreen` 등.

---

## 6. 핵심 런타임 상태 provider 3개 (★ 꼭 이해할 것)

| provider | 위치 | 역할 |
|---|---|---|
| `viewingDateProvider` | `features/records/application/viewing_date_provider.dart` | **현재 포커스된 일기 날짜**(date-only). 홈 주간바 선택, 기록 화면들이 공유. 일기 작성 시작 모달에서 작성 대상 날짜로 set되어 작성 플로우 전체가 그 날짜를 타겟함. 기본값=오늘. |
| `onboardingCompleteProvider` | `features/onboarding/application/onboarding_controller.dart` | 온보딩 완료 여부(bool). 홈 진입 팝업이 baseline-필요 vs 일기-시작 모달로 분기되는 근거. `markComplete()`. |
| `recordedDaysProvider` | `features/records/application/recorded_days_provider.dart` | **작성된 날짜 집합**(`Set<DateTime>`, date-only). **로그인 세션 기준 Firestore(diaries 문서 id)에서 로드 — 재시작해도 유지.** 일기 완료 시 `markRecorded()`로 즉시 반영. 더미 모드(테스트)에서만 `CalendarDummy` 시드. |

흐름 예: 안 쓴 날 선택 → `showDiaryStartModal(context, ref, date:)`가 `viewingDate=그날`로 set → 작성 플로우 → `report_guide_screen`의 "기록 완료하기"가 `recordedDaysProvider.markRecorded(viewingDate)` 후 `goNamed(homeWritten)` → 홈·달력에 그날이 "작성됨"으로 표시.

> UI가 이제 정적 `CalendarDummy.recordedDays/isRecorded`를 **직접 읽지 않습니다**(provider 시드로만 사용). 작성-상태가 필요하면 `recordedDaysProvider`를 watch 하세요.

---

## 7. 네비게이션 / 화면 컨텍스트

- 하단 탭 **[일기][리포트][상담]은 "작성일(written-day) 컨텍스트"에서만** 보이는 서브 내비입니다. 전역 앱 셸이 아님 — 온보딩/작성 플로우는 탭 없는 단독 화면.
- 기록 컨텍스트는 `StatefulShellRoute.indexedStack`(`records_shell.dart`)로 구성: 브랜치 0=일기상세, 1=감정리포트, 2=상담기록.
- **일기 탭(0)을 누르면 일기 상세가 아니라 홈(`homeWritten`)으로 갑니다.** 일기 상세는 홈의 **"작성한 일기 읽기"** 버튼으로만 진입.
- 홈 화면(`HomeScreen`)은 `home`과 `homeWritten` 두 경로가 공유하며, 작성/미작성 상태에 따라 카드가 바뀜.

---

## 8. 마스코트 / 에셋 규칙

- **실제 포즈 아트 17종 실장 완료** (16 기본 포즈 + 홈 전용 `peeking`) — `assets/images/character/<pose>.png`, `MascotImage(pose:)`가 자동 매핑 (없는 포즈는 플레이스홀더 폴백).
- 새 마스코트 자리가 필요하면 `MascotPose` enum의 기존 포즈를 재사용. 새 포즈 추가 시 같은 규격(투명 PNG, 캐릭터가 캔버스 86% 차지)으로 `assets/images/character/`에 추가.
- 남은 미실장 이미지는 **마스코트 외 일러스트/썸네일 7곳** — 목록은 `TANKACHU_POSES.md` §3.
- 코드의 `// TODO …교체 예정` 주석은 장면 맞춤 아트로 다듬을 수 있는 지점 표시 (`grep -rn "교체 예정" lib`).

---

## 9. 절대 건드리지 말 것 (읽기 전용 자료)

- **`_docs/`** 와 **`_screens/`** 는 **참조 전용 자료 폴더**입니다. 절대 수정/삭제하지 마세요. (스펙·시안의 원본)
- 코드의 정답이 `_docs`/`_screens`와 충돌하면, 임의로 고치지 말고 사람에게 확인 요청.

---

## 10. 작업 검증 루프 (★ "끝났다"고 말하기 전 필수)

어떤 변경이든 **완료 선언 전에** 아래 3개를 반드시 통과시키세요.

```bash
dart fix --apply        # 자동 수정(const 등)
flutter analyze         # 반드시 "No issues found!"
flutter test            # 반드시 전부 통과 (스모크 + route_smoke_test)
```

- 새 화면/라우트를 추가했다면 `flutter test`의 `route_smoke_test`가 그 경로도 빌드 검증하는지 확인.
- 포맷이 깨지면 `dart format <파일>`.
- 큰 변경은 가능하면 `flutter build apk --debug`로 실제 컴파일까지 확인.

---

## 11. 협업 규칙 (분업 시 충돌 최소화)

- **브랜치**: `main` 직접 푸시 금지. 기능별 `feature/<영역>-<요약>` 브랜치 → PR로 머지.
- **분업 단위는 `features/<기능>/` 폴더 단위**로 나누면 충돌이 가장 적습니다. (예: A=auth, B=diary, C=psych_test …)
- **충돌 핫스팟 (수정 전 팀과 조율, 작게 자주 머지):**
  - `lib/app/router/app_routes.dart`, `lib/app/router/app_router.dart` (모두가 라우트 추가)
  - `lib/widgets/index.dart`, `lib/theme/*` (공통 위젯/토큰)
  - `lib/data/dummy/*` (공유 더미)
- **새 의존성 추가는 팀 합의 후.** `pubspec.yaml`/`pubspec.lock` 변경은 별도 작은 PR로.
- 커밋/PR 메시지는 무엇을·왜를 명확히. 본인이 만들지 않은 파일을 지우거나 갈아엎기 전엔 먼저 확인.

---

## 12. 남은 작업 백로그 (Phase-2, 분업 대상)

> **★ Phase-2의 확정된 기술 방향과 단계별 전체 계획은 루트의 `ROADMAP.md`를 보세요.**
> (Firebase+FastAPI 하이브리드 / 외부 LLM API / 이메일 로그인 우선 / T2V·에셋·색상은 마지막)
> 아래 목록은 그 계획의 요약 백로그입니다.

**A. 데이터 연결 (실서비스 1순위)**
- [ ] **날짜별 콘텐츠 연결** — 일기상세/감정리포트/상담기록이 현재 단일 샘플 더미. `viewingDate` 기준으로 날짜별 내용이 다르게 표시되도록.
- [ ] **Repository ← DataSource ← Dummy 실연결** — 화면이 `*Dummy`/`DummySeed`를 직접 읽는 부분을 provider 경유로. (auth·diary는 스캐폴드만 있고 미사용 / `AppConfig.useDummyData` 스위치 존재)
- [ ] **영구 저장(persistence)** — `recordedDaysProvider`, 온보딩 완료, 로그인 유지, 페르소나 선택 등 재시작 후 유지.

**B. 실제 로직/인프라**
- [ ] 입력 검증, 실제 로그인/회원가입 호출(현재는 화면 전환만), OS 권한 요청.
- [ ] STT / Text-to-Video / SFT 상담봇 / baseline 측정 API, `core/network/api_client.dart` 구현, 예외→`Failure` 매핑.
- [ ] 라우터 가드 — 스플래시 로그인 상태 체크(`route_guard.dart` `appRedirect`가 현재 `null` 반환).
- [ ] flavor — prod 진입점(`main_prod.dart`) 추가(현재 `main.dart`=dev만).

**C. 마감 다듬기**
- [ ] 마스코트/이미지 실제 에셋 교체(`grep -rn "교체 예정" lib`).
- [ ] `CalendarDummy.latestRecordedDay`는 현재 미사용 — 정리 가능.

---

## 13. 에이전트 작업 매너 (요약)

- 변경은 작고 명확하게, **주변 코드 스타일을 모방**. 토큰/공통위젯/라우트 상수 규칙(§5)을 어기지 말 것.
- 추측하지 말고 코드/`_docs`를 먼저 읽기. 스펙 충돌·되돌리기 어려운 작업은 사람에게 확인.
- 완료 전 **§10 검증 루프** 필수. 통과 못 하면 "끝났다"고 하지 말 것.
- `_docs/`·`_screens/`는 절대 수정 금지(§9).
