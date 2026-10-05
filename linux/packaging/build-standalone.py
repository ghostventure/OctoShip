#!/usr/bin/env python3
"""Build pinned, offline x86_64 Linux installers; no host Python/Tk gets bundled."""
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent
OUTPUT = SOURCE.parent / 'dist/linux'


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(entry, cache):
    target = cache / entry['filename']
    if not target.exists():
        print('Downloading ' + entry['filename'], flush=True)
        temporary = target.with_suffix(target.suffix + '.partial')
        try:
            request = urllib.request.Request(entry['url'], headers={'User-Agent': 'OctoShip-bundle-builder'})
            with urllib.request.urlopen(request, timeout=90) as source, temporary.open('wb') as out:
                shutil.copyfileobj(source, out)
            if digest(temporary) != entry['sha256']: raise ValueError('Download checksum mismatch: ' + entry['filename'])
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    if digest(target) != entry['sha256']: raise ValueError('Cached download checksum mismatch: ' + entry['filename'])
    return target


def extract(archive, destination):
    with tarfile.open(archive) as package: package.extractall(destination, filter='data')


def build():
    if platform.machine() not in ('x86_64', 'amd64'): raise SystemExit('This builder targets Linux x86_64.')
    lock = json.loads((HERE / 'bundle-lock.json').read_text())
    cache = OUTPUT / 'bundle-cache'; cache.mkdir(parents=True, exist_ok=True)
    archives = {key: download(value, cache) for key, value in lock.items() if isinstance(value, dict)}
    version = (SOURCE / 'octoship/__init__.py').read_text().split('__version__ = "')[1].split('"')[0]
    with tempfile.TemporaryDirectory(prefix='octoship-build-', dir=OUTPUT) as temporary:
        work = Path(temporary); bundle = work / 'octoship'; bundle.mkdir()
        extract(archives['python'], work / 'python-unpack')
        shutil.move(str(work / 'python-unpack/python'), bundle / 'runtime')
        extract(archives['gh'], work / 'gh-unpack')
        gh_root = next((work / 'gh-unpack').iterdir())
        (bundle / 'bin').mkdir(); shutil.copy2(gh_root / 'bin/gh', bundle / 'bin/gh')
        notices = bundle / 'licenses'; notices.mkdir()
        shutil.copy2(gh_root / 'LICENSE', notices / 'GitHub-CLI-LICENSE')
        with tarfile.open(archives['python_notices']) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if len(parts) == 2 and member.isfile() and (parts[-1].startswith('LICENSE') or parts[-1] == 'python-licenses.rst'):
                    (notices / ('python-' + parts[-1])).write_bytes(tar.extractfile(member).read())
        with zipfile.ZipFile(archives['certifi']) as wheel:
            (bundle / 'certs').mkdir()
            (bundle / 'certs/cacert.pem').write_bytes(wheel.read('certifi/cacert.pem'))
            for name in wheel.namelist():
                if 'LICENSE' in name and not name.endswith('/'):
                    (notices / ('certifi-' + Path(name).name)).write_bytes(wheel.read(name))
        shutil.copytree(SOURCE / 'octoship', bundle / 'app/octoship', ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
        shutil.copy2(HERE / 'bundle-launcher.sh', bundle / 'octoship')
        shutil.copy2(HERE / 'bundle-bootstrap.py', bundle / 'bootstrap.py')
        shutil.copy2(HERE / 'installer.py', bundle / 'installer.py')
        shutil.copy2(HERE / 'octoship.svg', bundle / 'octoship.svg')
        shutil.copy2(SOURCE / 'README.md', bundle / 'README.md')
        (bundle / 'packaging').mkdir()
        shutil.copy2(HERE / 'README.md', bundle / 'packaging/README.md')
        shutil.copy2(HERE / 'bundle-lock.json', bundle / 'bundle-lock.json')
        (bundle / 'octoship').chmod(0o755)
        info = {'version': version, 'platform': lock['platform'], 'minimum_glibc': lock['minimum_glibc'],
                'python': lock['python']['version'], 'github_cli': lock['gh']['version'],
                'certificates': lock['certifi']['version']}
        (bundle / 'bundle.json').write_text(json.dumps(info, indent=2) + '\n')
        (notices / 'README.txt').write_text('Third-party notices for the bundled Python runtime, Tcl/Tk and supporting libraries, GitHub CLI, and Mozilla CA data.\nVersions, source URLs, and download SHA-256 values are in ../bundle-lock.json.\nOctoShip source is provided in ../app/octoship.\n')
        for directory in list(bundle.rglob('__pycache__')):
            if directory.is_dir(): shutil.rmtree(directory)
        files, links = {}, {}
        for path in sorted(bundle.rglob('*')):
            name = path.relative_to(bundle).as_posix()
            if path.is_symlink(): links[name] = os.readlink(path)
            elif path.is_file(): files[name] = digest(path)
        (bundle / 'payload-hashes.json').write_text(json.dumps({'files': files, 'symlinks': links}, indent=2) + '\n')
        archive = OUTPUT / f'octoship-{version}-linux-x86_64-bundled.tar.gz'
        with tarfile.open(archive, 'w:gz') as tar: tar.add(bundle, arcname='octoship')
        archive_hash = digest(archive)
        installer = OUTPUT / f'OctoShip-{version}-linux-x86_64.run'
        header = (HERE / 'self-extract.sh').read_text().replace('@PAYLOAD_SHA256@', archive_hash).replace('@VERSION@', version)
        with installer.open('wb') as out, archive.open('rb') as payload:
            out.write(header.encode()); shutil.copyfileobj(payload, out)
        installer.chmod(0o755)
        stage = work / 'deb'; target = stage / 'opt/octoship'
        target.parent.mkdir(parents=True); shutil.copytree(bundle, target, symlinks=True)
        (stage / 'DEBIAN').mkdir()
        size = sum(p.stat().st_size for p in bundle.rglob('*') if p.is_file() and not p.is_symlink()) // 1024
        (stage / 'DEBIAN/control').write_text(f'''Package: octoship
Version: {version}-1
Section: devel
Priority: optional
Architecture: amd64
Installed-Size: {size}
Depends: libc6 (>= 2.17)
Maintainer: OctoShip local build <noreply@localhost>
Description: Self-contained OctoShip GitHub desktop client
 Bundles Python, Tcl/Tk, GitHub CLI, and certificate data.
 Requires an X11 or XWayland desktop; no system Python or GitHub CLI needed.
''')
        (stage / 'usr/bin').mkdir(parents=True)
        (stage / 'usr/bin/octoship').write_text('#!/bin/sh\nexec /opt/octoship/octoship "$@"\n')
        (stage / 'usr/bin/octoship').chmod(0o755)
        desktop = stage / 'usr/share/applications'; desktop.mkdir(parents=True)
        (desktop / 'octoship.desktop').write_text('[Desktop Entry]\nType=Application\nName=OctoShip for GitHub\nExec=/opt/octoship/octoship\nIcon=octoship\nTerminal=false\nCategories=Development;\nStartupNotify=true\n')
        (desktop / 'octoship-login.desktop').write_text('[Desktop Entry]\nType=Application\nName=OctoShip GitHub Sign-in\nExec=/opt/octoship/octoship --login\nIcon=octoship\nTerminal=true\nCategories=Development;\n')
        icons = stage / 'usr/share/icons/hicolor/scalable/apps'; icons.mkdir(parents=True)
        shutil.copy2(HERE / 'octoship.svg', icons / 'octoship.svg')
        deb = OUTPUT / f'octoship_{version}-1_amd64.deb'
        subprocess.run(['dpkg-deb', '--root-owner-group', '--build', str(stage), str(deb)], check=True)
        checksums = OUTPUT / f'OctoShip-{version}-SHA256SUMS.txt'
        checksums.write_text(''.join(f'{digest(path)}  {path.name}\n' for path in (installer, deb, archive)))
        print('Built:\n' + '\n'.join(str(p) for p in (installer, deb, archive, checksums)))


if __name__ == '__main__': build()
