import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../../app/router/app_routes.dart';
import '../../../../data/dummy/auth_dummy.dart';
import '../../../../data/dummy/terms_dummy.dart';
import '../../../../theme/app_colors.dart';
import '../../../../theme/app_typography.dart';

/// "전체 동의" header + per-item consent rows (필수/선택 + 보기). Self-managed
/// selection; toggling 전체 동의 flips every row. [onRequiredChanged] reports
/// whether every 필수 item is checked, so the signup button can gate on it.
class TermsAgreementSection extends StatefulWidget {
  const TermsAgreementSection({
    super.key,
    this.terms = AuthDummy.terms,
    this.onRequiredChanged,
  });

  final List<TermItem> terms;
  final ValueChanged<bool>? onRequiredChanged;

  @override
  State<TermsAgreementSection> createState() => _TermsAgreementSectionState();
}

class _TermsAgreementSectionState extends State<TermsAgreementSection> {
  late final List<bool> _checked = List<bool>.filled(widget.terms.length, false);

  bool get _allChecked => _checked.every((c) => c);

  bool get _requiredChecked => [
        for (var i = 0; i < widget.terms.length; i++)
          if (widget.terms[i].required) _checked[i],
      ].every((c) => c);

  void _notify() => widget.onRequiredChanged?.call(_requiredChecked);

  void _toggleAll() {
    final next = !_allChecked;
    setState(() {
      for (var i = 0; i < _checked.length; i++) {
        _checked[i] = next;
      }
    });
    _notify();
  }

  void _toggleOne(int i) {
    setState(() => _checked[i] = !_checked[i]);
    _notify();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: _toggleAll,
          child: Padding(
            padding: const EdgeInsets.symmetric(vertical: 4),
            child: Row(
              children: [
                _SquareCheck(checked: _allChecked),
                const SizedBox(width: 10),
                Text(
                  '전체 동의입니다.',
                  style: AppTypography.body.copyWith(fontWeight: FontWeight.w700),
                ),
              ],
            ),
          ),
        ),
        const Padding(
          padding: EdgeInsets.symmetric(vertical: 8),
          child: Divider(color: AppColors.divider),
        ),
        for (var i = 0; i < widget.terms.length; i++)
          _TermRow(
            item: widget.terms[i],
            checked: _checked[i],
            onToggle: () => _toggleOne(i),
            onView: () => context.pushNamed(
              AppRoute.termsDetail,
              extra: TermsDummy.byTitle(widget.terms[i].title),
            ),
          ),
      ],
    );
  }
}

class _TermRow extends StatelessWidget {
  const _TermRow({
    required this.item,
    required this.checked,
    required this.onToggle,
    required this.onView,
  });

  final TermItem item;
  final bool checked;
  final VoidCallback onToggle;
  final VoidCallback onView;

  @override
  Widget build(BuildContext context) {
    final tag = item.required ? '(필수)' : '(선택)';
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 6),
      child: Row(
        children: [
          GestureDetector(
            onTap: onToggle,
            child: Icon(
              checked ? Icons.check_circle_rounded : Icons.check_circle_outline,
              size: 22,
              color: checked ? AppColors.primary : AppColors.inactive,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text.rich(
              TextSpan(
                style: AppTypography.bodySecondary
                    .copyWith(color: AppColors.textSecondary),
                children: [
                  TextSpan(text: '${item.title} '),
                  TextSpan(
                    text: tag,
                    style: TextStyle(
                      color: item.required
                          ? AppColors.primary
                          : AppColors.textTertiary,
                    ),
                  ),
                ],
              ),
            ),
          ),
          GestureDetector(
            onTap: onView,
            child: const Row(
              children: [
                Text('보기', style: AppTypography.caption),
                Icon(Icons.chevron_right_rounded,
                    size: 16, color: AppColors.textTertiary),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

/// Rounded square checkbox used for the 전체 동의 row.
class _SquareCheck extends StatelessWidget {
  const _SquareCheck({required this.checked});

  final bool checked;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 24,
      height: 24,
      decoration: BoxDecoration(
        color: checked ? AppColors.primary : AppColors.surface,
        borderRadius: BorderRadius.circular(8),
        border: Border.all(
          color: checked ? AppColors.primary : AppColors.border,
        ),
      ),
      child: Icon(
        Icons.check_rounded,
        size: 16,
        color: checked ? AppColors.textOnPrimary : AppColors.inactive,
      ),
    );
  }
}
