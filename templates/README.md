<h1 align="center"><img src="assets/banner.png" alt="Deus Vult $name" width="100%"></h1>

<p align="center">
  Omarchy 4.5 theme · by <a href="https://deusvult.digital">Deus Vult Digital</a>
</p>

<p align="center">
  <a href="#install">Install</a> ·
  <a href="#whats-in-it">What's in it</a> ·
  <a href="#palette">Palette</a> ·
  <a href="#the-other-phosphors">The other phosphors</a> ·
  <a href="#license">License</a>
</p>

<p align="center">
  <img src="preview.png" alt="The Deus Vult $name theme: three terminals showing fastfetch with a pixel Jerusalem cross, btop and the theme's colours, all in $code $colour phosphor" width="100%">
</p>

$code $colour phosphor on a dark CRT field: the glow of an old $colour
monochrome terminal, kept quiet enough to work in all day. Errors, warnings and diffs
keep their own colours (red, amber, green, blue), so the terminal still tells
you what's what. One of four Deus Vult phosphor themes, after the phosphors of
[deusvult.digital](https://deusvult.digital).

## Install

```sh
omarchy theme install $install
```

The installer clones the theme into `~/.config/omarchy/themes/$slug` and
switches to it. Afterwards it is in the theme menu (`Super + Ctrl + Shift + Space`)
like any other; `omarchy theme set $slug` switches back to it.

To leave it, set another theme (e.g. `omarchy theme set tokyo-night`). To
remove it: `omarchy theme remove $slug`.

## What's in it

- **Colours** (`colors.toml`): the terminal, editor, bar, launcher,
  notifications, lock screen and window borders all come from it through
  Omarchy's templates. Window borders run a bright-to-deep gradient of the
  phosphor.
- **Backgrounds**: three stills and one live background, picked from the
  background switcher (`Super + Ctrl + Space`):
  - `1-cross`: the pixel Jerusalem cross, glowing in the middle of the field;
  - `2-every-square-pixel`: the motto in ANSI Shadow block letters;
  - `3-boot`: a boot screen, BIOS lines and a fastfetch with the cross;
  - `4-live-cross`: the cross, alive. Its glow breathes and a refresh band
    rolls down the glass, an 8-second seamless loop (Omarchy plays it;
    it pauses under fullscreen windows).
- **Intros** (Omarchy 4.5): each still has one in `backgrounds/intros/`. The
  CRT powers on, a bright line opening into the picture, and draws the still
  pixel by pixel or line by line before settling on it. Omarchy plays it when
  you switch to the theme and at login. Turn intros off with
  `omarchy theme bg intro disable`.
- **Boot and login logo** (`unlock.png`): the cross and DEUS VULT for the
  disk-unlock screen. Switching themes leaves the boot screen alone; to use
  this one, run `omarchy plymouth set-by-theme $slug` (asks for sudo).
- **btop** (`btop.theme`): boxes and graphs in the phosphor; temperature and
  free-memory meters climb into amber and red.
- **Icons** (`icons.theme`): $icons, the Yaru tint closest to the phosphor.

<p align="center">
  <img src="preview-unlock.png" alt="The disk-unlock screen: the pixel cross and DEUS VULT above a password field" width="70%">
</p>

## Palette

| Role | Colour | Note |
| --- | --- | --- |
$palette

Text and every ANSI colour read at 7:1 or better on the background.

## The other phosphors

$others

## License

[MIT](LICENSE) © Deus Vult Digital. The theme is generated: its colours,
art and previews are made by scripts, nothing downloaded. They live in
[omarchy-deus-vult-themes](https://github.com/deus-vult-digital/omarchy-deus-vult-themes);
change the theme there, not here. The background lettering uses the ANSI
Shadow FIGlet font from the MIT-licensed
[figlet](https://github.com/patorjk/figlet.js) package.
