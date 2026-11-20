# hyprtk-shot — plan

Status: **v0.2.0 in progress 2026-11-20** (v0.1.0/v0.1.1 released and wired
into the suite). Batches land here as they are finished.

## Decisions (and why)

Survey and measurements: [RESEARCH.md](RESEARCH.md).

| Decision | Rationale |
|---|---|
| `grim` for capture | the only reliable wlroots/Hyprland CLI; one process, no portal prompt, no GPU/compositor API in our code |
| Capture first, then show an overlay | the frozen frame cannot include the overlay, and annotations land on the exact pixels the user is looking at |
| Annotate in-app, not via `satty`/`swappy` | one tool, one palette, one keymap; no "which editor is installed" capability dance |
| Selection = crop | one meaning for the rectangle; no separate crop tool to discover |
| Window mode from `hyprctl clients` geometry | deterministic, no foreign-toplevel handshake, works today on Hyprland 0.57 |
| All coordinates in image pixels | preview and output cannot disagree |
| PySide6 + QML, same palette resolver | one wallpaper repaints the suite; no new runtime dependency |
| `slurp` only as an optional extra | the overlay covers the daily case; slurp stays for cross-output selection in v0.2 |

## Architecture

```
hyprtk_shot/
  capture.py   grim argv, hyprctl monitors/clients, region via slurp
  annotate.py  Shape model; paint_shape() + render()
  canvas.py    QQuickPaintedItem: fit, selection, drag, veil, preview
  store.py     naming, save, clipboard, history
  settings.py  ~/.config/hyprtk-shot/config.json
  palette.py   pywal/bar theme -> overlay and launcher tokens
  bridge.py    QML facade: session, selection, shapes, undo, output
  cli.py       capture modes and flags; the no-editor path
  app.py       QGuiApplication, engine, type registration
  qml/
    Main.qml              launcher window, overlay window, toolbar, text entry
    components/           BarButton, Toggle
```

Python owns geometry, pixels and storage; QML owns chrome. One `Bridge` context
property and one registered type (`CaptureCanvas`).

## v0.1.0 — what the scaffold does

- [x] Region / window / monitor / all-outputs capture through grim
- [x] Frozen fullscreen overlay; drag to select, drag inside to move, right
      click to reselect the whole frame
- [x] Eleven tools: select, pen, line, arrow, rect, ellipse, highlighter, step
      marker, text, blur, pixelate
- [x] Colour swatches, stroke width, undo/redo/clear
- [x] Save (cropped to the selection), copy, save+copy, notification
- [x] Launcher with modes, delay, toggles, save directory, recent captures
- [x] Settings persisted and validated; history JSONL
- [x] CLI incl. `--stdout`, `--json`, `--no-edit`, `--list-outputs`, `last`, `open PATH`
- [x] pywal palette, v09 icon, desktop entry, `--system`/`--uninstall`
- [x] 60 unit tests, `qmllint`, headless boot check, installer round-trip
- [x] Offscreen screenshots for the README

Not in v0.1.0, deliberately: pin-to-screen, scrolling capture, upload, OCR,
built-in crop, multi-monitor overlay in one window.

## v0.2 — the things a daily user will ask for

- [x] **Pin to screen** — a frameless always-on-top window sized to the crop,
      `float`+`pin` by a Hyprland rule; dragged by the compositor, dismissed by
      double-click / close button / compositor close.
- [x] **Cross-output region** — `--slurp` / `picker: slurp`; slurp spans all
      outputs and prints `x,y WxH`, the overlay stays the default.
- [x] **Window picker** — the Window card lists `hyprctl clients` with titles
      (focused row first); `--window ADDRESS`.
- [x] **Crop after the fact** — eight grips resize the selection after
      annotations exist (anchored opposite edge, `selection.resize()`).
- [x] **Selection aspect lock** (`Shift` = square) and arrow-key nudging
      (1 px, `Shift` = 10 px, clamped).
- [x] **Undo for selection changes**, not just shapes (snapshot history).

## v0.3 — polish and reach

- [ ] Scrolling capture (stitch overlapping frames by correlation).
- [ ] Upload target (a configurable command, e.g. `zipline`), never a hardcoded
      service.
- [ ] OCR through `tesseract` when installed.
- [ ] A small `hyprtk-shot --daemon` mode that keeps a hotkey listener? Only if
      the keybind path proves too slow (it is ~150 ms today).
- [ ] Optional external editor hand-off (`satty`/`swappy`) for people who want
      the capture in their own tool.
- [ ] JPEG quality/format UI in the launcher (settings file already has them).

## Suite integration — the exact edits

`hyprtk-merged` is a source tree, not a destination. Steps 1–3 are needed for a
first release; 4–7 are the normal publish path.

1. **Repo + tag.** `git init` in `~/Projects/AI-Projects/hyprtk-shot`, push
   `hyprtk/hyprtk-shot` on `main`, tag `v0.1.0`, set topics (`wayland`,
   `hyprland`, `screenshot`, `qt`, `quickshell-suite`).
2. **Vendor into merged.** Copy the payload only (`hyprtk_shot/`, `bin/`,
   `install.sh`, `pyproject.toml`, `README.md`, `CHANGELOG.md`, `LICENSE`,
   `hyprtk-shot.desktop`, `docs/`) to
   `hyprtk-merged/installer/hyprtk-shot/`. No tests, scripts, PLAN or RESEARCH.
3. **`1-install.sh` step** after hyprtk-calc:

   ```sh
   _step "Installing hyprtk-shot"
   _spin "Installing hyprtk-shot..." "bash $SCRIPT_DIR/installer/hyprtk-shot/install.sh" "$LOG_FILE"
   _ok "hyprtk-shot installed (hyprtk-shot; screenshots)"
   ```

4. **Keybindings** in `hypr/keybindings.lua` — replace the `ssdetect.sh` binds:

   ```lua
   hl.bind(mainMod .. " + PRINT", hl.dsp.exec_cmd("sh -c 'p=$HOME/.local/bin/hyprtk-shot; [ -x \"$p\" ] && exec \"$p\" region'"))
   hl.bind(mainMod .. " + P",     hl.dsp.exec_cmd("sh -c 'p=$HOME/.local/bin/hyprtk-shot; [ -x \"$p\" ] && exec \"$p\" region'"))
   hl.bind(mainMod .. " + SHIFT + PRINT", hl.dsp.exec_cmd("sh -c 'p=$HOME/.local/bin/hyprtk-rec; [ -x \"$p\" ] && exec \"$p\" --toggle'"))
   ```

   Keep `installer/scripts/ssdetect.sh` for one release as the documented
   fallback, then delete it with the vendored HyprQuickFrame tree (and its
   `vendor/patches/` entry, `vendor/hyprquickframe.SOURCE.md`, the
   `hyprquickframe` package line and `PLAN-HYPRQUICKFRAME.md`).
5. **Window rules** in `hypr/windowrules.lua` — the overlay asks for fullscreen
   itself, but a rule keeps the launcher and the overlay honest:

   ```lua
   hl.window_rule({
       name = "windowrule-hyprtk-shot",
       match = { class = "hyprtk-shot" },
       float = true,
       size = "560 640",
   })
   hl.window_rule({
       name = "windowrule-hyprtk-shot-overlay",
       match = { class = "hyprtk-shot", title = "^hyprtk-shot$" },
       fullscreen = true,
       no_anim = true,
   })
   ```

   Verify the second rule against Hyprland 0.57 before shipping: the overlay
   calls `showFullScreen()` on Wayland, which the compositor may honour without
   a rule (tested offscreen only).
6. **Docs in merged**: `README.md` app table, `cheatsheet.md` (Print,
   Super+Shift+Print), suite `CHANGELOG`, and the ISO (`packages.hyprtk` needs
   `grim`, `slurp`, `wl-clipboard`; `customize_airootfs.sh` runs
   `--system`; `hyprtk-first-run` adds the `~/.local/bin` link).
7. **`push-all`** — gate (T1 matrix, T2 dry-run, audit at zero TODO), suite
   `CHANGELOG` + tag, merged → dotfiles + live, then reinstall.

Bar quick link: add a `shot` entry to `hyprtk-bar-qt/config.json` quicklinks
(and the launcher list), bump the bar version, re-vendor. Only reaches fresh
installs otherwise.

## Gate

`./scripts/qa.sh` must stay green, and every check must be able to fail:

| Check | Catches |
|---|---|
| `unittest discover` | bad grim argv, wrong window pick, renderer regressions, naming, settings, CLI |
| `compileall` | syntax drift |
| `qmllint` | QML syntax, unqualified properties, missing ids |
| `bootcheck.py` | a QML load failure, a renamed slot, a palette key the QML binds to that no longer exists, a save that does not crop |
| installer round-trip | `--system`/`--uninstall`, absolute desktop entry |
| CLI smoke | `__main__` GUI/CLI dispatch, exit codes |

## Open questions

- **Multi-output overlay.** One fullscreen window covers the focused output. Is
  a per-output window per monitor worth the Hyprland-specific placement, or is
  slurp the honest answer? Leaning slurp for v0.2.
- **Pin-to-screen without client-side positioning** — `moveactive exact` works
  but is a compositor command, not a window-manager-neutral one.
- **Text rendering**: the halo is drawn per glyph run; a font with a real
  outline would look better at small sizes.
- **Background grab before the overlay**: `grim` measures ~480 ms for a
  3840x1080 PNG on this box (encode-bound). Is a "freeze on keypress, capture
  in the background" mode worth it, or is the honest answer a lower-cost
  capture format during selection?
