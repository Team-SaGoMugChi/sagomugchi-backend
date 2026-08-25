import 'package:flutter/material.dart';

import '../../theme/app_colors.dart';

/// One OS permission explained on the permission-rationale screen (09).
class PermissionInfo {
  const PermissionInfo(this.icon, this.title, this.description);
  final IconData icon;
  final String title;
  final String description;
}

/// One environment checklist row on the baseline ready screen (18).
class CheckItem {
  const CheckItem(this.icon, this.title, this.description);
  final IconData icon;
  final String title;
  final String description;
}

/// One measurement item on the baseline intro screen (17).
class MeasureItem {
  const MeasureItem(this.icon, this.title, this.description, this.duration);
  final IconData icon;
  final String title;
  final String description;
  final String duration;
}

/// Live progress row on the measuring screen (19).
class MeasureProgress {
  const MeasureProgress(this.label, this.value);
  final String label;
  final double value; // 0..1
}

/// A summary metric tile on the completion screen (21).
class BaselineMetric {
  const BaselineMetric(this.icon, this.label, this.value, this.color);
  final IconData icon;
  final String label;
  final String value;
  final Color color;
}

/// Static dummy content for the permission + baseline flow. Mirrors the
/// mockups and `_docs/02`. Replace with real data/state later.
abstract final class BaselineDummy {
  BaselineDummy._();

  // 09 — permission rationale.
  static const List<PermissionInfo> permissions = [
    PermissionInfo(
      Icons.camera_alt_outlined,
      '카메라',
      '얼굴 표정 측정과 영상 통화를 위해 필요해요.',
    ),
    PermissionInfo(
      Icons.mic_none_rounded,
      '마이크',
      '목소리를 기록하고 감정을 분석하기 위해 필요해요.',
    ),
    PermissionInfo(
      Icons.graphic_eq_rounded,
      '음성 인식',
      '말한 내용을 텍스트로 변환하기 위해 필요해요.',
    ),
    PermissionInfo(
      Icons.notifications_none_rounded,
      '알림',
      '기록 리마인드와 소식을 전달하기 위해 필요해요.',
    ),
    PermissionInfo(
      Icons.photo_library_outlined,
      '사진 저장',
      '완성된 숏폼 영상을 저장하기 위해 필요해요.',
    ),
  ];

  // 17 — measurement items.
  static const List<MeasureItem> measureItems = [
    MeasureItem(
      Icons.sentiment_satisfied_alt_rounded,
      '얼굴 표정 측정',
      '다양한 표정을 자연스럽게 지어볼 거예요.',
      '약 2분',
    ),
    MeasureItem(
      Icons.mic_none_rounded,
      '음성 측정',
      '몇 가지 주제에 대해 자유롭게 이야기해볼 거예요.',
      '약 3분',
    ),
  ];

  static const List<String> introTips = [
    '편안한 장소에서 진행하면 좋아요.',
    '천천히, 자연스럽게 이야기해주세요.',
    '측정 중 너무 움직이지 않도록 해주세요.',
  ];

  // 18 — environment checklist (all good for the prototype).
  static const List<CheckItem> checklist = [
    CheckItem(Icons.center_focus_strong_rounded, '얼굴 위치', '얼굴이 화면 중앙에 있어요'),
    CheckItem(Icons.light_mode_rounded, '조명 상태', '주변이 너무 어둡지 않아요'),
    CheckItem(Icons.mic_none_rounded, '마이크 상태', '마이크가 정상적으로 연결됐어요'),
    CheckItem(Icons.volume_off_rounded, '주변 소음', '주변 소음이 크지 않아요'),
    CheckItem(Icons.verified_user_outlined, '카메라·마이크 권한', '권한이 모두 켜져 있어요'),
  ];

  // 19 — live measuring progress.
  static const List<MeasureProgress> measuringProgress = [
    MeasureProgress('얼굴 표정 측정', 0.60),
    MeasureProgress('음성 측정', 0.45),
  ];

  static const List<String> measuringTips = ['화면을 응시하며 자연스럽게 행동해주세요.'];

  // 19 — 탄카츄가 측정 중 음성으로 읽어주는 안내 대사. 감정 기복이 적은 평소
  // 상태를 자연스럽게 끌어내려고 일부러 담백한 주제로 구성했다(baseline은
  // "오늘 하루"가 아니라 평소 기준치를 잡는 용도). 튜토리얼 통화 연습(짧은
  // 데모)에서만 쓰는 짧은 버전 — 실제 측정 시간(5~7분)을 채우는 목록은
  // [baselineConversationPrompts] 참고.
  static const List<String> guideScript = [
    '안녕하세요, 오늘 평소 표정과 목소리를 기준으로 남겨둘게요.',
    '편하게 화면을 보면서, 요즘 하루를 어떻게 보내고 있는지 얘기해주세요.',
    '좋아하는 음식이나 최근에 본 것도 좋아요. 자연스럽게 말씀해주시면 돼요.',
  ];

  // 19 — 실제 baseline 측정용 확장 대화 목록. baseline_measuring_screen이
  // 사용자가 답하는 만큼(무음이 이어질 때까지) 기다렸다가 다음 질문으로
  // 넘어가는 방식으로 이 목록을 순서대로 진행하고, 총 소요 시간이 목표
  // 구간(5~7분)에 닿으면 멈춘다 — 그래서 목록이 다 안 끝나도 되고, 다 끝나면
  // 자연스러운 마무리 인사로 마친다. 전부 감정 기복이 적은 담백한 일상 주제.
  static const List<String> baselineConversationPrompts = [
    '안녕하세요, 오늘 평소 표정과 목소리를 기준으로 남겨둘게요.',
    '편하게 화면을 보면서, 요즘 하루를 어떻게 보내고 있는지 얘기해주세요.',
    '오늘 하루는 몇 시쯤 시작하셨어요? 아침엔 보통 뭘 하시나요?',
    '요즘 자주 먹는 음식이나 좋아하는 메뉴가 있으면 편하게 얘기해주세요.',
    '평소 이동할 땐 뭘 타고 다니세요? 그 시간에 보통 뭘 하며 보내시는지도 궁금해요.',
    '요즘 즐겨 듣는 음악이나 자주 보는 영상이 있다면 소개해주세요.',
    '주말엔 보통 어떻게 시간을 보내는 편이세요?',
    '최근에 읽은 책이나 본 영화, 드라마가 있다면 간단히 얘기해주세요.',
    '좋아하는 계절이나 날씨가 있으신가요? 이유도 편하게 말씀해주세요.',
    '평소 잠은 몇 시쯤 주무시고, 몇 시쯤 일어나시는 편이에요?',
    '집이나 방에서 가장 편하게 느끼는 공간은 어디예요?',
    '요즘 새로 시작했거나 꾸준히 하고 있는 취미가 있다면 들려주세요.',
    '좋아요, 거의 다 됐어요. 마지막으로 오늘 컨디션은 평소랑 비교하면 어떤 편인가요?',
  ];

  // 20 — analysis-in-progress items.
  static const List<String> analysisItems = [
    '얼굴 표정 기준',
    '음성 에너지 기준',
    '말하기 속도 기준',
  ];

  // 21 — completion summary lines (doc 21).
  static const List<String> completionSummary = [
    '얼굴 기준 데이터 저장 완료',
    '음성 기준 데이터 저장 완료',
    '감정 분석 준비 완료',
  ];

  // 21 — emotion-baseline summary metrics (mockup).
  static const List<BaselineMetric> metrics = [
    BaselineMetric(
      Icons.sentiment_satisfied_alt_rounded,
      '평균 감정',
      '6.2 / 10',
      AppColors.primary,
    ),
    BaselineMetric(
      Icons.graphic_eq_rounded,
      '음성 안정도',
      '72%',
      AppColors.success,
    ),
    BaselineMetric(
      Icons.insights_rounded,
      '표정 변화 다양성',
      '64%',
      AppColors.primary,
    ),
    BaselineMetric(
      Icons.schedule_rounded,
      '평균 측정 시간',
      '1분 48초',
      AppColors.warning,
    ),
  ];
}
