"""Run under xvfb-run; requires bwrap and a trusted minimal Debian rootfs archive."""
from pathlib import Path
import os, subprocess, tempfile, tarfile
import argparse
parser = argparse.ArgumentParser(description='Test a bundled .deb in a disposable minimal Linux rootfs.')
parser.add_argument('deb', type=Path)
parser.add_argument('rootfs_archive', type=Path)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix='octoship-deb-root-') as temporary:
    root = Path(temporary) / 'root'; root.mkdir()
    with tarfile.open(args.rootfs_archive.resolve()) as archive:
        archive.extractall(root, filter='tar')
    command = ['bwrap', '--die-with-parent', '--unshare-user', '--uid', '0', '--gid', '0', '--unshare-net', '--clearenv',
               '--bind', str(root), '/', '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp',
               '--ro-bind', str(args.deb.resolve()), '/tmp/octoship.deb',
               '--ro-bind', '/tmp/.X11-unix', '/tmp/.X11-unix',
               '--ro-bind', os.environ['XAUTHORITY'], '/tmp/xauthority',
               '--setenv', 'HOME', '/root', '--setenv', 'PATH', '/usr/sbin:/usr/bin:/sbin:/bin',
               '--setenv', 'DISPLAY', os.environ['DISPLAY'], '--setenv', 'XAUTHORITY', '/tmp/xauthority',
               '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'XDG_RUNTIME_DIR', '/tmp/runtime',
               '/bin/sh', '-ec', '''
for tool in python3 gh wish; do
    if command -v "$tool"; then echo "Unexpected host dependency: $tool" >&2; exit 1; fi
done
mkdir -m 700 /tmp/runtime
dpkg -i /tmp/octoship.deb
/usr/bin/octoship --diagnostics
/usr/bin/octoship --smoke-test
dpkg --audit
dpkg -r octoship
test ! -e /usr/bin/octoship
printf 'PASS: bundled Debian package installed, launched, and removed offline without Python/Tk/gh packages.\n'
''']
    subprocess.run(command, check=True)
