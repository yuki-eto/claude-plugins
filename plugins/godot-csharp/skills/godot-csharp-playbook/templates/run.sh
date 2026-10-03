#!/usr/bin/env bash
# Debug-launches the game straight from source: dotnet build -> --import -> launch.
# `dotnet build` must precede `--import` (importing a never-built C# project
# crashes with "assemblies not found"), and both must precede the launch so
# C# changes and new assets are picked up.
#
# Usage: godot/tools/run.sh [-- <extra godot args>]
# Place at godot/tools/run.sh; replace MyGame with the solution name.
# GODOT_BIN overrides the Godot .NET binary (a plain symlink does not work for
# the .NET build -- GodotSharp is resolved relative to the symlink).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

GODOT_BIN="${GODOT_BIN:-/Applications/Godot_mono.app/Contents/MacOS/Godot}"
SOLUTION="godot/MyGame.sln"

if [ ! -x "$GODOT_BIN" ]; then
    echo "Godot .NET binary not found/executable at $GODOT_BIN -- set GODOT_BIN to override" >&2
    exit 1
fi

# Optional native pieces: warn and continue, never abort (callers fall back).
# if ! "$SCRIPT_DIR/build-native.sh" macos; then
#     echo "warning: native bridge unavailable; falling back" >&2
# fi

echo "==> dotnet build $SOLUTION"
dotnet build "$SOLUTION" -m:1 -nodeReuse:false --disable-build-servers

echo "==> $GODOT_BIN --headless --path godot --import"
"$GODOT_BIN" --headless --path godot --import

echo "==> $GODOT_BIN --path godot $*"
exec "$GODOT_BIN" --path godot "$@"
