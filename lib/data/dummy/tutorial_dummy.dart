import 'package:flutter/material.dart';

/// Generic icon + title (+ optional description) row used across the tutorial
/// screens (example questions, flow steps, completion list).
class TutorialItem {
  const TutorialItem(this.icon, this.title, [this.description]);
  final IconData icon;
  final String title;
  final String? description;
}

/// Static dummy content for the 5-step tutorial flow. Mirrors the mockups and
/// `_docs/02`. Replace with real, localized content later.
abstract final class TutorialDummy {
  TutorialDummy._();

  // 12 — self-introduction example questions.
  static const List<TutorialItem> selfIntroQuestions = [
    TutorialItem(Icons.person_outline_rounded, '나에 대해 이야기해요',
        '이름, 좋아하는 것, 오늘의 관심사 등'),
    TutorialItem(Icons.wb_sunny_outlined, '오늘 하루는 어땠나요?',
        '좋았던 일, 힘들었던 일, 인상 깊었던 순간'),
    TutorialItem(Icons.mood_rounded, '지금 어떤 기분인가요?', '지금 느끼는 감정을 자유롭게 이야기해보세요'),
  ];

  // 13 — STT flow (음성 입력 → 음성 분석 → 텍스트 변환) + example sentence.
  static const List<TutorialItem> voiceFlow = [
    TutorialItem(Icons.mic_none_rounded, '음성 입력'),
    TutorialItem(Icons.graphic_eq_rounded, '음성 분석'),
    TutorialItem(Icons.text_fields_rounded, '텍스트 변환'),
  ];
  static const String exampleSentence = '오늘은 친구와 점심을 먹었는데, 오랜만이라 정말 즐거웠어요 😊';

  // 14 — face-capture steps + checklist.
  static const List<TutorialItem> faceSteps = [
    TutorialItem(Icons.center_focus_strong_rounded, '얼굴 중앙 정렬'),
    TutorialItem(Icons.sentiment_satisfied_alt_rounded, '자연스러운 표정'),
    TutorialItem(Icons.straighten_rounded, '편안한 거리'),
  ];
  static const List<String> faceChecklist = [
    '얼굴이 화면 중앙에 있어요',
    '주변 조명이 충분히 밝아요',
    '카메라가 선명하게 보고 있어요',
    '자연스러운 표정을 보여주세요',
  ];

  // 16 — completed-steps summary.
  static const List<TutorialItem> completionItems = [
    TutorialItem(Icons.star_rounded, 'Oddo 소개'),
    TutorialItem(Icons.videocam_rounded, '영상 통화 연습'),
    TutorialItem(Icons.mic_none_rounded, '음성 입력 연습'),
    TutorialItem(Icons.sentiment_satisfied_alt_rounded, '표정 입력 연습'),
    TutorialItem(Icons.checklist_rounded, '측정 방식 안내'),
  ];

  // Tips.
  static const List<String> introTips = [
    '카메라와 마이크가 켜져 있는지 확인해주세요.',
    '조용한 곳에서 진행하면 더 정확해요.',
    '편하게, 평소처럼 이야기하면 돼요.',
  ];
  static const List<String> callTips = [
    '편안한 장소에서 이야기해보세요.',
    '어떤 이야기든 좋아요. 있는 그대로 말해주세요.',
    '중간에 멈춰도 괜찮아요. 천천히 해도 돼요.',
  ];
  static const List<String> faceTips = [
    '약간 미소를 지으면 분석에 도움이 돼요.',
    '카메라를 정면으로 바라봐주세요.',
  ];
}
