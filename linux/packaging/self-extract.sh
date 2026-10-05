#!/bin/sh
# OctoShip @VERSION@: offline self-extracting installer.
set -eu
case "$(uname -m)" in x86_64|amd64) ;; *) echo 'This installer requires Intel/AMD 64-bit Linux (x86_64).' >&2; exit 1 ;; esac
case "$(uname -s)" in Linux) ;; *) echo 'This installer is for Linux.' >&2; exit 1 ;; esac
case "${1:-}" in
    --help|-h)
        echo 'OctoShip @VERSION@ self-contained Linux installer'
        echo 'Run with no arguments to open the installer window.'
        echo '  --install [--prefix PATH] [--no-desktop]   Offline command-line installation'
        echo 'Requires glibc 2.17+ and an X11/XWayland desktop to run the app.'
        exit 0 ;;
esac
GLIBC=$(getconf GNU_LIBC_VERSION 2>/dev/null || true)
case "$GLIBC" in
    'glibc '*)
        GLIBC_VERSION=${GLIBC#glibc }
        GLIBC_MAJOR=${GLIBC_VERSION%%.*}
        GLIBC_MINOR=${GLIBC_VERSION#*.}; GLIBC_MINOR=${GLIBC_MINOR%%.*}
        if [ "$GLIBC_MAJOR" -lt 2 ] || { [ "$GLIBC_MAJOR" -eq 2 ] && [ "$GLIBC_MINOR" -lt 17 ]; }; then
            echo 'This installer requires glibc 2.17 or newer.' >&2; exit 1
        fi ;;
    *) echo 'A glibc-based Linux system is required; musl/Alpine is not supported by this package.' >&2; exit 1 ;;
esac
for TOOL in tail tar gzip sha256sum mktemp awk; do
    command -v "$TOOL" >/dev/null 2>&1 || { echo "Required system utility is missing: $TOOL" >&2; exit 1; }
done
umask 077
WORK=$(mktemp -d "${TMPDIR:-/tmp}/octoship-install-XXXXXXXX")
trap 'rm -rf "$WORK"' EXIT HUP INT TERM
PAYLOAD_LINE=$(awk '/^__OCTOSHIP_PAYLOAD_BELOW__$/ {print NR + 1; exit}' "$0")
tail -n +"$PAYLOAD_LINE" "$0" > "$WORK/payload.tar.gz"
printf '%s  %s\n' '@PAYLOAD_SHA256@' "$WORK/payload.tar.gz" | sha256sum -c - >/dev/null
# Downloaded dependencies have already been pinned and checked by the builder.
tar -xzf "$WORK/payload.tar.gz" -C "$WORK"
"$WORK/octoship/octoship" --installer "$@"
exit 0
__OCTOSHIP_PAYLOAD_BELOW__
