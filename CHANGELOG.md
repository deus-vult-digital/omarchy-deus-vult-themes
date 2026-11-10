# Changelog

All notable changes to the Deus Vult themes. Versions follow [semver](https://semver.org/).

## [1.0.0] - 2026-11-10

The first public release, at github.com/deus-vult-digital/omarchy-deus-vult-themes,
with each theme in its own repo beside it.

### Added
- Four themes, one per deusvult.digital phosphor, each in its own repo:
  Green Screen (P1 green, `deus-vult-green-screen`), Amber Monochrome (P3
  amber), Paper White (P4 white) and Blue Phosphor (P11 blue). Each has
  `colors.toml`, `btop.theme`, `icons.theme` (the nearest Yaru tint), three
  backgrounds with Omarchy 4.5 intros and a live background, `unlock.png`,
  `preview.png`, `preview-unlock.png`, a banner and its README.
- `phosphors.toml`: every phosphor's ramp and field, and the ANSI colours all
  four share (so errors and diffs stay legible).
- `tools/build.py` builds the themes from it; `tools/publish.sh` pushes each
  to its repo (`-p` to its public mirror too). `templates/README.md` is the
  themes' README. `tools/make-backgrounds.py`, `tools/make-preview-unlock.sh`
  and `tools/stage-preview.sh` make the art and previews.
- The README lists the four themes with their previews and install commands.
