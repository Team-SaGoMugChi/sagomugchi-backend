# Assets

Image/icon assets are dropped here and registered in `pubspec.yaml`.

- `images/character/` — 탄카츄 mascot poses. Filenames match `MascotPose`
  enum values in `lib/core/constants/app_assets.dart`
  (e.g. `waving.png`, `thinking.png`, `heart.png`). Until added,
  `MascotImage` shows a styled placeholder, so missing files are harmless.
- `images/` — `oddo_logo.png` and other illustrations.
- `icons/` — custom line/solid icons not covered by Material Icons.

Source mockups live in `_screens/` and `_docs/` at the repo root — those are
reference-only and are NOT bundled into the app.
