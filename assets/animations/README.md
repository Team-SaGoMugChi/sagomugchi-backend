# 탄카츄 "말하기" Rive 애니메이션 — 작업 스펙

> **상태 (2026-08-13): 코드 쪽 연동 준비만 끝난 상태, 실제 `.riv` 파일 없음.**
> `lib/widgets/talking_mascot_guide.dart`가 아래 경로의 파일을 찾아서 있으면
> 자동으로 사용하고, 없으면(지금 상태) 기존 절차적 입 모양 애니메이션으로
> 조용히 폴백한다. 즉 이 파일을 넣기만 하면 별도 코드 수정 없이 바로 적용됨.

## 왜 필요한가

튜토리얼 통화 연습(화면 11) 등에서 탄카츄가 TTS로 안내할 때 "진짜 말하는
느낌"을 내고 싶은데, 지금은 정지 이미지 위에 코드로 그린 타원 하나를
벌렸다 오므렸다 하는 임시 연출이다(듀오링고 캐릭터 수준에 한참 못 미침).
립싱크 영상(Phase 8 T2V)까지는 아직 멀었지만, 그 전 단계로 **실제로 리깅된
2D 애니메이션**을 얹으면 훨씬 자연스러워진다.

## 넣어야 할 파일

`assets/animations/tankachu_talk.riv`

(다른 이름을 쓰게 되면 `talking_mascot_guide.dart`의 `_riveAssetPath` 상수도
같이 바꿔야 함.)

## Rive 파일 요구 사항 (코드가 기대하는 계약)

- **Artboard**: 이름 아무거나 상관없음(첫 번째 아티보드를 씀). 기준 아트는
  `assets/images/character/waving.png`(정면, 입이 안 가려진 유일한 실사용
  포즈) — 캔버스 1024×1024, 캐릭터가 캔버스의 약 86% 차지, 코/입은 대략
  (51%, 50%) 지점.
- **State Machine**: 이름 `"Talk"`.
- **Boolean input**: 이름 `"speaking"` — true면 입을 움직이는 상태(말하는
  중), false면 다물고 가만히(듣는 중/대기).
- 그 외 트리거(눈 깜빡임 등)는 자유롭게 추가해도 되지만, 지금 코드는
  `speaking` 하나만 읽는다. 더 추가하고 싶으면 담당자와 상의 후
  `talking_mascot_guide.dart`에서 같이 연결.
- 몸통/귀는 거의 고정, 턱·입 위주로만 움직이는 걸 권장(몸 전체를 흔드는
  버전은 이미 "떨림"으로 보인다는 피드백을 받은 적 있음).

## 참고

- Rive 에디터: https://rive.app (무료 플랜으로 충분)
- Flutter 런타임 문서: https://rive.app/docs/runtimes/flutter/flutter
- 캐릭터 원본 참고: `_docs/character_sheet.png` (16포즈 시트),
  `TANKACHU_POSES.md`
