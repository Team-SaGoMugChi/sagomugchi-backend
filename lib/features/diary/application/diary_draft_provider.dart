import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/models/fusion_result.dart';

/// The in-progress diary run, carried across the write-flow steps until the
/// final "기록 완료하기" save.
///
/// - [transcript]: Step 2 (확인하기)에서 사용자가 수정한 대화 원문.
/// - [recordingPath]: Step 1 (말하기)에서 녹음된 음성 파일 경로 —
///   Phase 4에서 AI 서버 업로드/분석에 사용.
/// - [faceImagePath]: Step 1 종료 시점에 캡처한 정지 이미지 — baseline과
///   같은 방식으로 표정 분석에 사용.
/// - [fusionResult]: 그 둘 + baseline을 서버(`/diary/step2/analyze`)에 보내서
///   받은 감정 키워드/점수/Δ. 아직 없으면(분석 전/실패) null — Step2 확인
///   화면은 이 경우 더미 콘텐츠로 폴백한다.
///
/// TODO(Phase 5): grow into a full draft (summary/counsel log) once the AI
/// pipeline produces real values for those too.
class DiaryDraftState {
  const DiaryDraftState({
    this.transcript,
    this.recordingPath,
    this.faceImagePath,
    this.fusionResult,
  });

  final String? transcript;
  final String? recordingPath;
  final String? faceImagePath;
  final FusionResult? fusionResult;

  DiaryDraftState copyWith({
    String? transcript,
    String? recordingPath,
    String? faceImagePath,
    FusionResult? fusionResult,
  }) => DiaryDraftState(
    transcript: transcript ?? this.transcript,
    recordingPath: recordingPath ?? this.recordingPath,
    faceImagePath: faceImagePath ?? this.faceImagePath,
    fusionResult: fusionResult ?? this.fusionResult,
  );
}

class DiaryDraft extends Notifier<DiaryDraftState> {
  @override
  DiaryDraftState build() => const DiaryDraftState();

  void setTranscript(String transcript) =>
      state = state.copyWith(transcript: transcript);

  void setRecordingPath(String path) =>
      state = state.copyWith(recordingPath: path);

  void setFaceImagePath(String path) =>
      state = state.copyWith(faceImagePath: path);

  void setFusionResult(FusionResult result) =>
      state = state.copyWith(fusionResult: result);

  void clear() => state = const DiaryDraftState();
}

final diaryDraftProvider = NotifierProvider<DiaryDraft, DiaryDraftState>(
  DiaryDraft.new,
);
