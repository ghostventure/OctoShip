#!/usr/bin/env python3
"""Run under xvfb-run. Verify a built installer in a Python-free Debian rootfs."""
import argparse
import os
from pathlib import Path
import subprocess
import tempfile

parser = argparse.ArgumentParser()
parser.add_argument('installer', type=Path)
parser.add_argument('rootfs', type=Path)
args = parser.parse_args()
source_tests = Path(__file__).resolve().parent
with tempfile.TemporaryDirectory(prefix='octoship-clean-home-') as home:
    command = [
        'bwrap', '--die-with-parent', '--unshare-net', '--clearenv',
        '--ro-bind', str(args.rootfs.resolve()), '/', '--dev', '/dev', '--proc', '/proc',
        '--tmpfs', '/tmp', '--tmpfs', '/home', '--tmpfs', '/opt', '--bind', home, '/home/test',
        '--ro-bind', str(args.installer.resolve()), '/opt/installer.run',
        '--ro-bind', str(source_tests), '/opt/tests',
        '--ro-bind', str(source_tests.parent / 'packaging'), '/opt/packaging',
        '--ro-bind', '/tmp/.X11-unix', '/tmp/.X11-unix',
        '--ro-bind', os.environ['XAUTHORITY'], '/tmp/xauthority',
        '--setenv', 'HOME', '/home/test', '--setenv', 'PATH', '/usr/bin:/bin',
        '--setenv', 'LANG', 'C.UTF-8', '--setenv', 'DISPLAY', os.environ['DISPLAY'],
        '--setenv', 'XAUTHORITY', '/tmp/xauthority', '--setenv', 'XDG_RUNTIME_DIR', '/tmp/runtime',
        '--chdir', '/home/test', '/bin/sh', '-ec', r'''
for tool in python3 gh wish; do
    if command -v "$tool"; then echo "Unexpected host dependency: $tool" >&2; exit 1; fi
done
mkdir -m 700 /tmp/runtime
/bin/sh /opt/installer.run --install --prefix '/home/test/OctoShip offline'
'/home/test/OctoShip offline/octoship' --diagnostics
'/home/test/OctoShip offline/octoship' --smoke-test
/home/test/.local/bin/octoship --cli --version
BUNDLE=$(find '/home/test/OctoShip offline/builds' -mindepth 1 -maxdepth 1 -type d)
export TCL_LIBRARY="$BUNDLE/runtime/lib/tcl9.0" TK_LIBRARY="$BUNDLE/runtime/lib/tk9.0"
export PYTHONPATH="$BUNDLE/app" SSL_CERT_FILE="$BUNDLE/certs/cacert.pem"
"$BUNDLE/runtime/bin/python3" -m unittest discover -s /opt/tests -v
"$BUNDLE/runtime/bin/python3" /opt/tests/gui_smoke.py
"$BUNDLE/runtime/bin/python3" /opt/tests/gui_workflows.py
/bin/sh /opt/installer.run --install --prefix '/home/test/OctoShip offline'
test "$(find '/home/test/OctoShip offline/builds' -mindepth 1 -maxdepth 1 -type d | wc -l)" -eq 1
printf 'uninstall\n' | '/home/test/OctoShip offline/octoship' --uninstall
test ! -e /home/test/.local/bin/octoship
test ! -e /home/test/.local/share/applications/octoship.desktop
printf 'PASS: offline installation, bundled diagnostics, GUI and backend workflows, reinstall, and uninstall.\n'
''',
    ]
    subprocess.run(command, check=True)
