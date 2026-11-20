#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "$0")/.." && pwd)
cd "$ROOT"

# /usr/bin/qmllint is Qt5 on this box; the Qt6 one lives under /usr/lib/qt6/bin.
QMLLINT=/usr/lib/qt6/bin/qmllint
[ -x "$QMLLINT" ] || QMLLINT=$(command -v qmllint || true)

echo "== unit tests =="
PYTHONPATH=. python3 -m unittest discover -s tests

echo "== python syntax =="
python3 -m compileall -q hyprtk_shot tests scripts

echo "== qml lint =="
if [ -n "${QMLLINT:-}" ]; then
    failed=0
    while IFS= read -r f; do
        out=$("$QMLLINT" --unqualified disable --context-properties disable "$f" 2>&1 || true)
        # The CaptureCanvas type is registered from Python, so qmllint cannot
        # resolve the module; that is expected. Anything else is a defect.
        filtered=$(printf '%s\n' "$out" | grep -v 'HyprtkShot\|CaptureCanvas\|Warnings occurred while importing\|Failed to import\|import paths' || true)
        if printf '%s' "$filtered" | grep -q 'Error:'; then
            echo "qmllint: $f" >&2
            printf '%s\n' "$filtered" >&2
            failed=1
        fi
    done < <(find hyprtk_shot/qml -name '*.qml')
    [ "$failed" -eq 0 ] || exit 1
else
    echo "qmllint not installed — skipped"
fi

echo "== shell syntax =="
bash -n install.sh
sh -n bin/hyprtk-shot

echo "== headless boot =="
timeout 90 python3 scripts/bootcheck.py

echo "== cli =="
PYTHONPATH=. python3 -m hyprtk_shot --version | grep -q '^hyprtk-shot '
PYTHONPATH=. python3 -m hyprtk_shot --list-outputs | head -1 | grep -q 'DP-\|eDP-\|HDMI-\|^$'
PYTHONPATH=. python3 -m hyprtk_shot --definitely-not-a-flag >/dev/null 2>&1 && {
    echo "an unknown flag should have exited 2" >&2
    exit 1
} || [ $? -eq 2 ]

echo "== installer round-trip =="
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
HOME="$TMP" XDG_DATA_HOME="$TMP/.local/share" ./install.sh >/dev/null
test -x "$TMP/.local/bin/hyprtk-shot"
test -f "$TMP/.local/share/applications/hyprtk-shot.desktop"
test -f "$TMP/.local/share/hyprtk-shot/hyprtk-shot.svg"
grep -q "Exec=$TMP/.local/share/hyprtk-shot/bin/hyprtk-shot" "$TMP/.local/share/applications/hyprtk-shot.desktop"
HOME="$TMP" XDG_DATA_HOME="$TMP/.local/share" "$TMP/.local/share/hyprtk-shot/bin/hyprtk-shot" --version >/dev/null
HYPRTK_DRYRUN=1 ./install.sh --system | grep -q 'would install'
HOME="$TMP" XDG_DATA_HOME="$TMP/.local/share" ./install.sh --uninstall >/dev/null
test ! -e "$TMP/.local/share/hyprtk-shot"

echo "QA PASS"
