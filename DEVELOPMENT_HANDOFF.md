# 2026-10-22 CLOVA Voice handoff (#85)

- Updated develop from ad36bc7 to team 41057af; work on 85-persona-clova-voice.
- Frontend counterpart: Team-SaGoMugChi/sagomugchi-frontend#89.
- Added POST /tts with four speakers: nara, njinho, nminyoung, ndonghyun.
- Server-only settings: CLOVA_VOICE_CLIENT_ID and CLOVA_VOICE_CLIENT_SECRET.
  Local configuration currently missing; no real vendor synthesis was attempted.
- Validation: all 534 tests passed, 6 dependency deprecation warnings.
  Nine new tests cover voices, invalid input, missing settings and provider errors.
- No text/audio persistence, no changes to baseline extraction or counsel contracts.
- Remaining: configure Voice credentials and deploy, then verify four voices on
  Android/iOS and collect a six-sentence baseline to assess usable voice/face samples.
- Draft PR publication and develop merge status will be recorded separately.
