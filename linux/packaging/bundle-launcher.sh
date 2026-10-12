#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH="$APP_DIR/bin:${PATH:-/usr/bin:/bin}"
export PATH
SSL_CERT_FILE=${SSL_CERT_FILE:-"$APP_DIR/certs/cacert.pem"}
export SSL_CERT_FILE
case "${1:-}" in
    --login) shift; exec "$APP_DIR/bin/gh" auth login --hostname github.com --git-protocol https --web "$@" ;;
    --cli) shift; exec "$APP_DIR/bin/gh" "$@" ;;
esac
# Distro Tk generally includes Xft antialiased fonts. Prefer it when available;
# installations without system Python/Tk still run with the complete bundle.
# Never mix the bundled Tcl 9 scripts with a system Tcl/Tk installation.
case "${OCTOSHIP_UI_RUNTIME:-auto}" in
    auto|system)
        if command -v python3 >/dev/null 2>&1 && python3 -I -c 'import sys, tkinter; sys.exit(not (sys.version_info >= (3,10) and tkinter.TkVersion >= 8.6))' >/dev/null 2>&1; then
            unset TCL_LIBRARY TK_LIBRARY
            OCTOSHIP_UI_RUNTIME_ACTIVE=system
            export OCTOSHIP_UI_RUNTIME_ACTIVE
            exec python3 -I -B "$APP_DIR/bootstrap.py" "$@"
        fi
        if [ "${OCTOSHIP_UI_RUNTIME:-auto}" = system ]; then
            printf '%s\n' 'System Python 3.10+ with Tk 8.6+ is unavailable. Use OCTOSHIP_UI_RUNTIME=bundled.' >&2
            exit 1
        fi
        ;;
    bundled) ;;
    *) printf '%s\n' 'OCTOSHIP_UI_RUNTIME must be auto, system, or bundled.' >&2; exit 1 ;;
esac
TCL_LIBRARY="$APP_DIR/runtime/lib/tcl9.0"
TK_LIBRARY="$APP_DIR/runtime/lib/tk9.0"
OCTOSHIP_UI_RUNTIME_ACTIVE=bundled
export TCL_LIBRARY TK_LIBRARY OCTOSHIP_UI_RUNTIME_ACTIVE
exec "$APP_DIR/runtime/bin/python3" -I -B "$APP_DIR/bootstrap.py" "$@"
