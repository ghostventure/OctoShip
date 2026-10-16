#!/bin/sh
# Build the current Linux source bundle, then start its installer.
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/../.." && pwd)
cd "$ROOT"

python3 "$SCRIPT_DIR/build-standalone.py"
VERSION=$(awk -F '"' '/^__version__ = / { print $2; exit }' linux/octoship/__init__.py)
if [ -z "$VERSION" ]; then
    echo 'Could not determine the OctoShip source version.' >&2
    exit 1
fi

INSTALLER="$ROOT/dist/linux/OctoShip-$VERSION-linux-x86_64.run"
if [ ! -f "$INSTALLER" ]; then
    echo "Build completed, but the installer was not found: $INSTALLER" >&2
    exit 1
fi

exec sh "$INSTALLER" "$@"
