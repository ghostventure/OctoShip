#!/bin/sh
set -eu
APP_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PATH="$APP_DIR/bin:${PATH:-/usr/bin:/bin}"
export PATH
# Preserve a user's explicit CA override; otherwise use bundled Mozilla roots.
SSL_CERT_FILE=${SSL_CERT_FILE:-"$APP_DIR/certs/cacert.pem"}
export SSL_CERT_FILE
# Explicit script locations keep Tcl/Tk independent of host installations.
TCL_LIBRARY="$APP_DIR/runtime/lib/tcl9.0"
TK_LIBRARY="$APP_DIR/runtime/lib/tk9.0"
export TCL_LIBRARY TK_LIBRARY
case "${1:-}" in
    --login) shift; exec "$APP_DIR/bin/gh" auth login --hostname github.com --git-protocol https --web "$@" ;;
    --cli) shift; exec "$APP_DIR/bin/gh" "$@" ;;
esac
exec "$APP_DIR/runtime/bin/python3" -I -B "$APP_DIR/bootstrap.py" "$@"
