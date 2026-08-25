# Oddo (오또) 🐻

Flutter로 만드는 **AI 감정 일기** 앱 — 음성으로 하루를 기록하면 AI가 감정을 분석하고, 마스코트 탄카츄와의 상담·감정 리포트·숏폼 영상으로 돌려줍니다.

## 팀원 온보딩 (여기부터!)

1. **[CLAUDE.md](CLAUDE.md)** — 프로젝트 전체 맥락·아키텍처 규칙·작업 방법. **Claude Code 에이전트는 자동으로 읽습니다** (다른 AI 에이전트를 쓰면 이 파일 전체를 첫 프롬프트로 붙여넣기)
2. **[ROADMAP.md](ROADMAP.md)** — 진행 현황과 남은 Phase·준비물
3. **[FIRESTORE_SCHEMA.md](FIRESTORE_SCHEMA.md)** — 데이터 구조 단일 기준

## 실행

```bash
flutter pub get
flutter run        # 에뮬레이터/기기
```

## 작업 규칙 (요약 — 상세는 CLAUDE.md §10·§11)

- `main` 직접 푸시 금지 → `feature/<영역>-<요약>` 브랜치 + PR
- 완료 선언 전: `dart fix --apply` → `flutter analyze` → `flutter test` 전부 통과
- `_docs/`, `_screens/`는 읽기 전용 (수정 금지)

