#!/bin/sh
set -eu
SOURCE=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
OUTPUT="$SOURCE/../dist/linux"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT
mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/share/octoship" "$STAGE/usr/bin" "$STAGE/usr/share/applications" "$STAGE/usr/share/icons/hicolor/scalable/apps" "$OUTPUT"
cp -r "$SOURCE/octoship" "$STAGE/usr/share/octoship/"
find "$STAGE" -type d -name __pycache__ -exec rm -rf {} +
cp "$SOURCE/octoship-linux" "$STAGE/usr/share/octoship/"
cat > "$STAGE/usr/bin/octoship" <<'LAUNCH'
#!/bin/sh
exec /usr/share/octoship/octoship-linux "$@"
LAUNCH
chmod 755 "$STAGE/usr/bin/octoship" "$STAGE/usr/share/octoship/octoship-linux"
cp "$SOURCE/packaging/octoship.desktop" "$STAGE/usr/share/applications/"
cp "$SOURCE/packaging/octoship.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/"
cat > "$STAGE/DEBIAN/control" <<'CONTROL'
Package: octoship
Version: 1.6.1-1
Section: devel
Priority: optional
Architecture: all
Depends: python3 (>= 3.10), python3-tk, gh
Maintainer: OctoShip local build <noreply@localhost>
Description: Native Linux desktop uploader for GitHub
 Search and review local files, browse repositories and branches,
 and upload files with GitHub CLI authentication.
CONTROL
chmod -R go-w "$STAGE"
find "$STAGE" -type d -exec chmod 755 {} +
dpkg-deb --root-owner-group --build "$STAGE" "$OUTPUT/octoship_1.6.1-1_all.deb"
tar --exclude=__pycache__ -czf "$OUTPUT/octoship-linux-1.6.1.tar.gz" -C "$SOURCE" octoship octoship-linux README.md
printf 'Built packages in %s\n' "$OUTPUT"
