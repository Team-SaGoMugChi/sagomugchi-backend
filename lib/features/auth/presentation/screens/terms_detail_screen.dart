import 'package:flutter/material.dart';

import '../../../../data/dummy/terms_dummy.dart';
import '../../../../theme/app_spacing.dart';
import '../../../../theme/app_typography.dart';
import '../../../../widgets/app_background.dart';
import '../../../../widgets/oddo_app_bar.dart';
import '../../../../widgets/oddo_card.dart';

/// 약관 상세 뷰어 — 회원가입/추가정보의 약관 "보기"에서 진입.
/// (본문은 임시 표준 문구 — 정식 약관은 출시 전 교체, ROADMAP Phase 8)
class TermsDetailScreen extends StatelessWidget {
  const TermsDetailScreen({super.key, required this.doc});

  final TermsDoc doc;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: OddoAppBar(title: doc.title),
      body: AppBackground(
        child: SafeArea(
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.screenH),
            children: [
              OddoCard(
                child: Text(
                  doc.body.trim(),
                  style: AppTypography.body.copyWith(height: 1.7),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
