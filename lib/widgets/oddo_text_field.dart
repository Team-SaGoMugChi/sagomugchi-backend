import 'package:flutter/material.dart';

import '../theme/app_colors.dart';
import '../theme/app_radius.dart';
import '../theme/app_typography.dart';

/// Standard form input: white fill, light border, leading icon, hint, and an
/// optional password eye-toggle or trailing widget (counter / calendar).
/// Used across auth and later form screens.
class OddoTextField extends StatefulWidget {
  const OddoTextField({
    super.key,
    this.hint,
    this.prefixIcon,
    this.obscure = false,
    this.keyboardType,
    this.controller,
    this.suffix,
    this.readOnly = false,
    this.onTap,
    this.errorText,
  });

  final String? hint;
  final IconData? prefixIcon;

  /// Validation message shown under the field (null = no error).
  final String? errorText;

  /// Password field: shows an eye toggle and hides input.
  final bool obscure;
  final TextInputType? keyboardType;
  final TextEditingController? controller;

  /// Custom trailing widget (counter text, calendar icon, …). Ignored when
  /// [obscure] is true (the eye toggle takes the suffix slot).
  final Widget? suffix;
  final bool readOnly;
  final VoidCallback? onTap;

  @override
  State<OddoTextField> createState() => _OddoTextFieldState();
}

class _OddoTextFieldState extends State<OddoTextField> {
  late bool _obscured = widget.obscure;

  @override
  Widget build(BuildContext context) {
    Widget? suffixIcon;
    if (widget.obscure) {
      suffixIcon = IconButton(
        icon: Icon(
          _obscured ? Icons.visibility_off_outlined : Icons.visibility_outlined,
          color: AppColors.textTertiary,
          size: 20,
        ),
        onPressed: () => setState(() => _obscured = !_obscured),
      );
    } else if (widget.suffix != null) {
      suffixIcon = Padding(
        padding: const EdgeInsets.only(right: 12),
        child: widget.suffix,
      );
    }

    return TextField(
      controller: widget.controller,
      obscureText: _obscured,
      keyboardType: widget.keyboardType,
      readOnly: widget.readOnly,
      onTap: widget.onTap,
      style: AppTypography.body.copyWith(color: AppColors.textStrong),
      decoration: InputDecoration(
        hintText: widget.hint,
        errorText: widget.errorText,
        filled: true,
        fillColor: AppColors.surface,
        prefixIcon: widget.prefixIcon != null
            ? Icon(widget.prefixIcon, color: AppColors.textTertiary, size: 20)
            : null,
        suffixIcon: suffixIcon,
        suffixIconConstraints: const BoxConstraints(minWidth: 0, minHeight: 0),
        contentPadding:
            const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        enabledBorder: const OutlineInputBorder(
          borderRadius: AppRadius.button,
          borderSide: BorderSide(color: AppColors.border),
        ),
        focusedBorder: const OutlineInputBorder(
          borderRadius: AppRadius.button,
          borderSide: BorderSide(color: AppColors.primary, width: 1.5),
        ),
      ),
    );
  }
}
