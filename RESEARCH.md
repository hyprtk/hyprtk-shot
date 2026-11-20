# hyprtk-shot — research

What the screenshot tools on Linux actually do on Wayland in late 2026, and
which parts of them this app copies on purpose.

## The protocol question comes first

A Wayland client cannot read the framebuffer. Everything is built on one of
three doors:

| Door | Who implements it | Consequence |
|---|---|---|
| `wlr-screencopy` | wlroots, Hyprland, Sway, river | one-shot capture of an output or a region, no prompt; the wlroots-native path |
| `ext-image-copy-capture` | newer compositors (partial) | the successor protocol; not something a 2026 app can rely on alone |
| `xdg-desktop-portal` (`Screenshot`/`ScreenCast`) | GNOME, KDE, and Hyprland via `xdg-desktop-portal-hyprland` | works everywhere but can show a permission dialog and returns a stream, not a still |

Hyprland implements `wlr-screencopy`, which is why every Hyprland screenshot
tool is a `grim` wrapper. Flameshot on Wayland goes through the portal and is
the one tool in this list that can block on a dialog. The suite already ships
`xdg-desktop-portal-hyprland` for screen sharing, but a screenshot should not
need it.

**Decision:** `grim` for pixels. No in-process screencopy widget, no portal.

## The tools

| Tool | Stack | Region | Window | Output | Annotate | Frozen screen | Scriptable |
|---|---|---|---|---|---|---|---|
| `grim` + `slurp` | C (wlroots) | yes | no | yes | no | no | yes, ideal for pipes |
| `grim` + `satty` | C + Rust/GTK | yes | no | yes | yes (strong) | yes (satty) | yes |
| `grim` + `swappy` | C | yes | no | yes | basic | yes (swappy) | yes |
| HyprQuickFrame | Quickshell/QML | yes | hover-pick | yes | basic + share | yes | limited |
| Hyprshot | shell + grim/slurp | yes | yes (geometry) | yes | no | no | yes |
| grimblast | shell | yes | yes | yes | no | no | yes |
| Flameshot | C++/Qt | yes | yes | yes | strong | yes | `--raw`, `--clipboard` |
| Spectacle | KDE/Qt | yes | yes | yes | yes (Plasma 6) | yes | `-r -b -n -o` |
| xfce4-screenshooter | GTK | yes | yes | yes | no | no | yes (`-f -r -w`) |
| GNOME Shell | JS | yes | yes | yes | basic | yes | DBus |
| Ksnip | Qt | editor-first | — | — | strong | n/a | CLI on files |
| Waytator | C/GTK | yes (via grim) | no | yes | yes | yes (editor) | yes |

### What each one gets right

- **xfce4-screenshooter** is the cleanest "small utility" shape: `-f`, `-r`,
  `-w`, `-d <seconds>`, `-o <app>`, and a dialog that also offers "open with".
  Its mode set is the one users expect, and its CLI is the model for ours.
- **Spectacle** proves that one window can be both launcher and editor, and its
  CLI (`-f`, `-m`, `-a`, `-r`, `-b` for background, `-o` for output) is what
  scripting wants. It also does full-screen capture from the compositor, which
  is free for KDE and impossible for us.
- **Flameshot** is the annotation benchmark: arrows, shapes, text, pen,
  highlighter, blur, pixelate, numbered counters, and a toolbar that appears on
  the selection. Its weakness here is Wayland capture, not its editor.
- **Satty** shows how good the frozen-screen model feels, and its tool set
  (pen/brush/highlighter/arrow/rect/ellipse/text/marker/blur/pixelate) is the
  list we implement.
- **HyprQuickFrame** is the suite's current screenshot path. It is a Quickshell
  overlay that also captures live, with KDE Connect sharing and an editor
  hand-off. Two problems for us: it needs `swappy`/`satty` for annotation, and
  the NVIDIA workaround (a grim+slurp fallback) is a second code path that
  behaves differently from the primary one. A frozen frame removes the reason
  for the fallback.
- **Hyprshot** is the popular script: `hyprshot -m window|region|output`,
  saves and copies, uses `slurp` for selection. Its window mode reads the same
  `hyprctl clients` geometry we do. It has no editor, which is the gap.

### What this app takes

1. **The mode set** from xfce4-screenshooter/Hyprshot: region, window, output,
   all outputs.
2. **The CLI contract** from Spectacle/xfce4-screenshooter: a mode word plus
   `--delay`, `--save`, `--copy`, and a quiet `--no-edit` path.
3. **The toolbar-and-freeze interaction** from Flameshot/Satty.
4. **The annotation list** from Satty (and therefore Flameshot).
5. **The window geometry source** from Hyprshot (`hyprctl clients -j`).

### What it deliberately does not take

- **Portal capture.** A permission dialog between the keypress and the shot is
  a worse product on a desktop that owns its compositor.
- **Live capture under the overlay.** The overlay would appear in the image.
- **An external annotation editor.** One palette, one keymap, one binary.
- **Upload.** A hardcoded service ages badly; a configurable command is v0.3.

## Measurements on this box

Hyprland 0.57.2, one 3840x1080 output at scale 1, grim 1.5.0, Python 3.14,
PySide6 6.12:

| Operation | Time |
|---|---|
| `grim -` (full output, PNG to stdout) | **~480 ms** min, ~486 ms median |
| `grim -o DP-1 -` | ~485 ms |
| `hyprctl clients -j` | ~4 ms |
| `hyprctl monitors -j` | ~4 ms |
| our QML window construction (offscreen boot) | ~120 ms |

The grim number is the important one: PNG-encoding 4.1 Mpx dominates, not the
IPC. That is why the overlay shows a *decoded* image and never re-captures
during a session, and why the keybinding path captures immediately with no
delay by default.

`hyprctl` being ~4 ms is why window mode does not need a picker to feel fast:
the geometry is available before the eye moves.

## Design consequences

| Finding | Consequence in the code |
|---|---|
| grim is ~0.5 s | capture once, decode, then operate on `QImage`; nothing re-grabs |
| `hyprctl clients` is cheap | window mode reads geometry at capture time, no cached list |
| Wayland clients cannot position windows | the overlay requests fullscreen; no custom multi-output canvas in v0.1 |
| `grim -g` takes logical coordinates | Hyprland's window `at`/`size` are used unchanged; `-o` handles scale itself |
| `grim` prints exactly what it captured | the freeze is the file the user is annotating: no preview mismatch |

## Sources

- Hyprland wiki, *Screenshots and recording* (grim/swappy/satty/wf-recorder/
  wl-screenrec examples, portal note).
- `grim -h` and `slurp -h` on this box (flags verified, not quoted).
- `hyprctl monitors -j` / `clients -j` output on this box (field names and
  units verified).
- HyprQuickFrame upstream README and the suite's vendored `SOURCE.md` +
  patch description.
- xfce4-screenshooter documentation (modes, `-d`, `-o`, `-m`).
- KDE Spectacle app page and man page (capture modes, annotation, CLI flags).
- Flameshot feature page and the Flameshot/Satty annotation comparisons.
- Hyprshot README (modes and dependencies).
- Zipline's Wayland guide (grim/slurp/satty recipes and the portal caveat).
