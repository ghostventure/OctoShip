"""Bounded local inspection. Files are never executed and ZIPs never extracted."""
import difflib
import json
import os
from pathlib import Path
import re
import stat
import struct
from urllib.parse import unquote, urlsplit
import zipfile
from .core import OctoShipError, EXCLUDED, MAX_BYTES, open_regular, sensitive, validate_path
from .scanner import scan_bytes, check_cancel


def project_files(root, cancel=None, exclusions=()):
    import fnmatch
    root = Path(os.path.abspath(Path(root).expanduser()))
    if not root.is_dir() or any(p.is_symlink() for p in (root, *root.parents)):
        raise OctoShipError('Choose a regular project folder without symlink ancestors.')
    count = folders = 0
    def excluded(rel):
        return any(fnmatch.fnmatchcase(rel, p) or fnmatch.fnmatchcase(rel + '/', p) for p in exclusions)
    def failed(error):
        raise OctoShipError('Project inspection incomplete: unreadable folder.') from error
    for folder, dirs, files in os.walk(root, followlinks=False, onerror=failed):
        folders += 1
        if folders > 10000: raise OctoShipError('Project exceeds 10,000 folders.')
        check_cancel(cancel)
        dirs[:] = [d for d in dirs if d not in EXCLUDED and not excluded(Path(folder, d).relative_to(root).as_posix())]
        for name in dirs + files:
            if Path(folder, name).is_symlink(): raise OctoShipError('Project contains a symbolic link: ' + name)
        for name in files:
            path = Path(folder, name); rel = path.relative_to(root).as_posix()
            if excluded(rel): continue
            if not stat.S_ISREG(path.lstat().st_mode): raise OctoShipError('Nonregular project file: ' + rel)
            count += 1
            if count > 50000: raise OctoShipError('Project exceeds 50,000 files.')
            yield path


def selective_changes(before, after):
    if max(len(before), len(after)) > 1024**2: raise OctoShipError('Selective text is limited to 1 MiB.')
    try: a, b = before.decode('utf-8').splitlines(True), after.decode('utf-8').splitlines(True)
    except UnicodeError: raise OctoShipError('Selective publishing requires UTF-8 text.') from None
    if b'\0' in before + after or max(len(a), len(b)) > 2000:
        raise OctoShipError('Selective publishing requires text with at most 2,000 lines.')
    changes = [(i, j, b[x:y]) for tag, i, j, x, y in difflib.SequenceMatcher(None, a, b, autojunk=False).get_opcodes() if tag != 'equal']
    return a, changes


def apply_changes(lines, changes, selected):
    result, pos = [], 0
    for index, (start, end, added) in enumerate(changes):
        result.extend(lines[pos:start]); result.extend(added if index in selected else lines[start:end]); pos = end
    return ''.join(result + lines[pos:]).encode('utf-8')


def inspect_zip(path, cancel=None):
    rows, total, scanned = [], 0, 0
    with open_regular(path) as stream:
        if os.fstat(stream.fileno()).st_size > 512 * 1024**2: raise OctoShipError('ZIP exceeds 512 MiB.')
        with zipfile.ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > 10000: raise OctoShipError('ZIP exceeds 10,000 entries.')
            for entry in entries:
                check_cancel(cancel)
                total += entry.file_size
                if total > 2 * 1024**3: raise OctoShipError('ZIP expansion exceeds 2 GiB.')
                name = entry.filename.rstrip('/')
                unsafe = False
                try: validate_path(name)
                except OctoShipError: unsafe = True
                unsafe |= sensitive(name) or stat.S_ISLNK(entry.external_attr >> 16) or bool(re.match(r'^[A-Za-z]:', name))
                status = 'UNSAFE / sensitive path; not scanned' if unsafe else 'Not scanned: entry or total scan limit'
                if entry.is_dir(): status = 'Directory' if not unsafe else status
                elif not unsafe and entry.file_size <= 512 * 1024 and scanned + entry.file_size <= 8 * 1024**2:
                    try:
                        with archive.open(entry) as content: data = content.read(512 * 1024 + 1)
                        scanned += len(data)
                        status = scan_bytes(data, cancel).summary if len(data) <= 512 * 1024 else 'Not scanned: expanded beyond limit'
                    except (RuntimeError, zipfile.BadZipFile, NotImplementedError): status = 'Not scanned: encrypted, corrupt, or unsupported ZIP entry'
                rows.append((name, f'{entry.file_size:,} bytes; {status}'))
    return rows


def markdown_links(root, path, text):
    root = Path(root).absolute(); rows = []
    for match in re.finditer(r'!?\[[^\]\r\n]*\]\(\s*(<[^>]+>|[^\s)]+)', text):
        link = match[1].strip('<>')
        if link.startswith(('#', '/')) or urlsplit(link).scheme: continue
        relative = unquote(link.split('#')[0].split('?')[0])
        if not relative: continue
        target = Path(os.path.abspath(path.parent / relative))
        if not target.is_relative_to(root): rows.append((str(path.relative_to(root)), link + ' — outside project')); continue
        current, wrong, missing = root, False, False
        for part in target.relative_to(root).parts:
            if current.is_symlink() or not current.is_dir(): missing = True; break
            names = [p.name for p in current.iterdir()]
            name = part if part in names else next((n for n in names if n.casefold() == part.casefold()), None)
            if name is None: missing = True; break
            wrong |= name != part; current /= name
        if current.is_symlink(): missing = True
        if missing or wrong: rows.append((str(path.relative_to(root)), link + (' — missing / unsupported link' if missing else ' — capitalization mismatch')))
    return rows


def inspect_project(root, expected='', cancel=None):
    root = Path(root).expanduser().absolute(); rows = []
    expected = expected.strip().removeprefix('v')
    for path in project_files(root, cancel):
        check_cancel(cancel)
        rel = path.relative_to(root).as_posix(); size = path.stat().st_size
        if size > MAX_BYTES: rows.append((rel, 'Over 50 MiB: use Git LFS or a release asset.'))
        versions = []
        if size <= 2 * 1024**2 and (path.suffix.lower() in ('.md', '.csproj', '.iss') or path.name in ('package.json', '.gitattributes')):
            with open_regular(path) as stream: text = stream.read(2 * 1024**2 + 1).decode('utf-8', errors='replace')
            if path.suffix.lower() == '.md': rows.extend(markdown_links(root, path, text))
            if path.name == '.gitattributes' and re.search(r'filter\s*=\s*lfs', text): rows.append((rel, 'Git LFS rules present; use Git LFS for matching files.'))
            if path.name == 'package.json':
                try: versions = [str(json.loads(text).get('version', ''))]
                except ValueError: rows.append((rel, 'Invalid JSON'))
            if path.suffix == '.csproj': versions = re.findall(r'<(?:Version|AssemblyVersion)>([^<]+)', text)
            if path.suffix == '.iss': versions = re.findall(r'#define\s+\w*Version\s+"([^"]+)"', text)
        if path.suffix.lower() in ('.exe', '.zip', '.msi', '.deb', '.run'):
            versions += re.findall(r'(?<!\d)(\d+\.\d+(?:\.\d+){0,2}(?:-[\w.]+)?)', path.name)
        if expected:
            for version in versions:
                if version and version != expected: rows.append((rel, f'Version {version} differs from expected {expected}'))
    return rows or [('Project', 'No supported issues detected; dynamic versions and arbitrary manifests are not inferred.')]


def inspect_installer(path):
    with open_regular(path) as stream:
        header = stream.read(64)
        if header.startswith(b'\x7fELF') and len(header) >= 20:
            machine = int.from_bytes(header[18:20], 'little' if header[5] == 1 else 'big')
            architecture = {3:'x86', 62:'x86_64', 40:'ARM', 183:'AArch64'}.get(machine, str(machine))
            result = f'ELF {32 if header[4] == 1 else 64}-bit; architecture {architecture}'
        elif header.startswith(b'MZ') and len(header) == 64:
            offset = struct.unpack_from('<I', header, 60)[0]
            stream.seek(offset); pe = stream.read(6)
            if pe[:4] != b'PE\0\0': raise OctoShipError('Invalid PE header.')
            machine = struct.unpack_from('<H', pe, 4)[0]
            result = 'PE architecture ' + {0x14c:'x86', 0x8664:'x86_64', 0xaa64:'ARM64'}.get(machine, hex(machine))
        else: result = 'Architecture unavailable for this package format.'
    return result + '\nVersion and signature trust are not verified on Linux. The inspected file was not executed.'


def redact(text):
    text = re.sub(r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----[\s\S]*?(?:-----END [^-]*PRIVATE KEY-----|$)', '[PRIVATE KEY REDACTED]', text)
    text = re.sub(r'(?i)([?&](?:access_token|token|key|sig|signature|password)=)[^&\s]+', r'\1[REDACTED]', text)
    text = re.sub(r'(?i)\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+|Bearer\s+\S+)', '[REDACTED]', text)
    text = re.sub(r'(?im)(token|password|secret|authorization|api[_-]?key)\s*[:=]\s*[^\r\n]+', r'\1=[REDACTED]', text)
    text = re.sub(r'https?://[^/\s@]+@', 'https://[REDACTED]@', text)
    text = re.sub(r'[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}', '[EMAIL]', text)
    return text.replace(str(Path.home()), '~')
