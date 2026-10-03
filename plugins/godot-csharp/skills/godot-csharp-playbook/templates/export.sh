#!/usr/bin/env bash
# Exports a preset in the order that avoids the assemblies-not-found crash:
# export-template preflight -> dotnet build -> --import -> --export-* -> iOS fixups.
#
# Usage: godot/tools/export.sh <iOS|macOS> [debug|release] [output-path]
# - Preset names must match `name=` in godot/export_presets.cfg exactly.
# - output-path is relative to godot/ unless absolute.
#
# Replace MyGame and REQUIRED_ORIENTATIONS below. iOS signing: set
# application/app_store_team_id in export_presets.cfg.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

GODOT_BIN="${GODOT_BIN:-/Applications/Godot_mono.app/Contents/MacOS/Godot}"
SOLUTION="godot/MyGame.sln"
APP_NAME="MyGame"
# Orientation keys the generated iOS Info.plist must list (project.godot's
# display/window/handheld/orientation is an int enum; a Godot-3-style string
# silently reads back as 0/Landscape).
REQUIRED_ORIENTATIONS=("UIInterfaceOrientationPortrait")

PRESET="${1:?usage: $0 <iOS|macOS> [debug|release] [output-path]}"
CONFIG="${2:-debug}"

case "$PRESET" in
    iOS) DEFAULT_OUTPUT="build/ios/$APP_NAME.ipa" ;;
    macOS) DEFAULT_OUTPUT="build/macos/$APP_NAME.app" ;;
    *) echo "Unknown preset '$PRESET'" >&2; exit 1 ;;
esac
OUTPUT="${3:-$DEFAULT_OUTPUT}"

case "$CONFIG" in
    debug) EXPORT_FLAG="--export-debug" ;;
    release) EXPORT_FLAG="--export-release" ;;
    *) echo "Unknown config '$CONFIG' -- expected 'debug' or 'release'" >&2; exit 1 ;;
esac

OUTPUT_DIR="$(dirname "$OUTPUT")"
OUTPUT_BASE="$(basename "$OUTPUT")"
OUTPUT_BASE="${OUTPUT_BASE%.*}"

if [ "$PRESET" = "iOS" ] && pgrep -x Xcode >/dev/null 2>&1; then
    # An Xcode window open on the previous export writes its stale
    # project.pbxproj back a few minutes later, undoing the signing patch below.
    echo "warning: Xcode is running -- close the exported project before exporting" >&2
fi

# Godot does not create the output directory itself.
case "$OUTPUT" in
    /*) OUTPUT_DIR_ABS="$OUTPUT_DIR" ;;
    *) OUTPUT_DIR_ABS="$REPO_ROOT/godot/$OUTPUT_DIR" ;;
esac
mkdir -p "$OUTPUT_DIR_ABS"

# Editor upgrades do not install matching export templates; catch that before
# the slow build/import steps instead of at the end of a long export log.
GODOT_VERSION="$("$GODOT_BIN" --version 2>/dev/null | tail -1 || true)"
TEMPLATE_DIR="${GODOT_VERSION%.*}"
TEMPLATE_DIR="${TEMPLATE_DIR%.*}"
TEMPLATES_ROOT="$HOME/Library/Application Support/Godot/export_templates"
case "$TEMPLATE_DIR" in
    [0-9]*)
        if [ ! -d "$TEMPLATES_ROOT/$TEMPLATE_DIR" ]; then
            echo "error: no export templates for $GODOT_VERSION at $TEMPLATES_ROOT/$TEMPLATE_DIR" >&2
            echo "Install Godot_v${TEMPLATE_DIR%.stable*}-stable_mono_export_templates.tpz (Editor > Manage Export Templates)." >&2
            exit 1
        fi
        ;;
esac

echo "==> dotnet build $SOLUTION"
dotnet build "$SOLUTION" -m:1 -nodeReuse:false --disable-build-servers

echo "==> godot --headless --path godot --import"
"$GODOT_BIN" --headless --path godot --import

echo "==> godot --headless --path godot $EXPORT_FLAG \"$PRESET\" $OUTPUT"
"$GODOT_BIN" --headless --path godot "$EXPORT_FLAG" "$PRESET" "$OUTPUT"

if [ "$PRESET" = "iOS" ]; then
    XCODEPROJ="$OUTPUT_DIR_ABS/$OUTPUT_BASE.xcodeproj"
    PLIST="$OUTPUT_DIR_ABS/$OUTPUT_BASE/$OUTPUT_BASE-Info.plist"
    PBXPROJ="$XCODEPROJ/project.pbxproj"

    echo "==> checking $PLIST orientations"
    [ -f "$PLIST" ] || { echo "error: $PLIST not found" >&2; exit 1; }
    for key in "${REQUIRED_ORIENTATIONS[@]}"; do
        if ! grep -q "$key" "$PLIST"; then
            echo "error: $PLIST lacks $key -- check project.godot's handheld/orientation (int enum, not a string). Don't hand-edit the plist." >&2
            exit 1
        fi
    done

    # Godot writes CODE_SIGN_STYLE = "Manual" per target regardless of the
    # preset (its TargetAttributes say Automatic), so Xcode opens with
    # automatic signing off and Team = None. No preset option fixes it.
    [ -f "$PBXPROJ" ] || { echo "error: $PBXPROJ not found" >&2; exit 1; }
    TEAM_ID="$(grep -m1 '^application/app_store_team_id=' godot/export_presets.cfg | cut -d'"' -f2)"
    [ -n "$TEAM_ID" ] || { echo "error: set application/app_store_team_id in export_presets.cfg" >&2; exit 1; }

    echo "==> patching $PBXPROJ: automatic signing (team $TEAM_ID)"
    sed -i '' \
        -e 's/CODE_SIGN_STYLE = "Manual";/CODE_SIGN_STYLE = Automatic;/g' \
        -e '/PROVISIONING_PROFILE = "";/d' \
        -e '/PROVISIONING_PROFILE_SPECIFIER = "";/d' \
        "$PBXPROJ"
    sed -i '' -E "s/DEVELOPMENT_TEAM = [^;]*;/DEVELOPMENT_TEAM = $TEAM_ID;/g" "$PBXPROJ"

    AUTOMATIC_COUNT="$(grep -c 'CODE_SIGN_STYLE = Automatic;' "$PBXPROJ" || true)"
    TEAM_COUNT="$(grep -c "DEVELOPMENT_TEAM = $TEAM_ID;" "$PBXPROJ" || true)"
    if [ "$AUTOMATIC_COUNT" -lt 2 ] || [ "$TEAM_COUNT" -lt 2 ]; then
        echo "error: signing patch incomplete (Automatic x$AUTOMATIC_COUNT, team x$TEAM_COUNT; expected 2 each)" >&2
        exit 1
    fi
fi

echo "==> done: $OUTPUT_DIR_ABS/$(basename "$OUTPUT")"
