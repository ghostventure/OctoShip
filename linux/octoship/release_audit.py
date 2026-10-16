"""Bounded, read-only audits for local release artifact directories.

Artifacts are never executed or extracted and no network access is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import tempfile
import zipfile
from collections import Counter
from .core import open_regular

MAX_ARTIFACTS = 500
MAX_ARTIFACT_BYTES = 2 * 1024**3
MAX_TOTAL_BYTES = 5 * 1024**3
MAX_MANIFEST_BYTES = 2 * 1024**2
MAX_MANIFEST_LINES = 20000
MAX_ZIP_ENTRIES = 10000
MAX_ZIP_CHECK_BYTES = 256 * 1024**2
CHUNK = 1024 * 1024
KNOWN_EXTENSIONS = {'.zip', '.tar', '.gz', '.tgz', '.xz', '.bz2', '.7z', '.deb', '.rpm', '.msi', '.exe', '.dmg', '.pkg', '.run', '.AppImage', '.sha256', '.txt', '.json', '.sig', '.asc'}


@dataclass(frozen=True)
class AuditCheck:
    key: str
    title: str
    status: str
    detail: str


class ReleaseAuditError(ValueError):
    """Selected release directory cannot be safely inspected."""


def _check(key, title, status, detail):
    return AuditCheck(key, title, status, str(detail))


def _version_tokens(filename):
    return re.findall(r'(?<![A-Za-z0-9])v?(\d+\.\d+(?:\.\d+){0,2})(?!\d)', filename, re.I)


def _checksum_manifest(path):
    with path.open('rb') as stream:
        if os.fstat(stream.fileno()).st_size > MAX_MANIFEST_BYTES:
            return [], ['manifest exceeds 2 MiB'], True
        raw = stream.read(MAX_MANIFEST_BYTES + 1)
    if len(raw) > MAX_MANIFEST_BYTES:
        return [], ['manifest exceeds 2 MiB'], True
    try:
        lines = raw.decode('utf-8-sig').splitlines()
    except UnicodeError:
        return [], ['manifest is not UTF-8'], False
    if len(lines) > MAX_MANIFEST_LINES:
        return [], ['manifest exceeds 20,000 lines'], True
    entries, errors = [], []
    for number, line in enumerate(lines, 1):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        match = re.fullmatch(r'([0-9a-fA-F]{64})\s+[* ](.+)', line)
        if not match:
            errors.append(f'line {number}: unsupported or malformed checksum row')
            continue
        name = match.group(2).strip()
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or '\\' in name or not name:
            errors.append(f'line {number}: unsafe artifact path')
            continue
        entries.append((name, match.group(1).lower()))
    return entries, errors, False


def _digest(path, algorithm='sha256'):
    digest = hashlib.new(algorithm)
    with path.open('rb') as stream:
        while True:
            block = stream.read(CHUNK)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def _zip_facts(path):
    names, exact, folded = [], set(), set()
    total_expanded = 0
    entry_count = 0
    crc_state = 'not checked: byte budget'
    crc_bytes = 0
    crc_error = ''
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        entry_count = len(members)
        for member in members:
            name = member.filename
            names.append(name)
            total_expanded += member.file_size
        if entry_count <= MAX_ZIP_ENTRIES:
            crc_state = 'checked'
            for member in members:
                if member.is_dir():
                    continue
                if member.file_size > MAX_ZIP_CHECK_BYTES or crc_bytes + member.file_size > MAX_ZIP_CHECK_BYTES:
                    crc_state = 'partial: 256 MiB read budget reached'
                    break
                try:
                    member_bytes = 0
                    with archive.open(member) as source:
                        while True:
                            block = source.read(CHUNK)
                            if not block:
                                break
                            member_bytes += len(block)
                            if member_bytes > member.file_size or crc_bytes + member_bytes > MAX_ZIP_CHECK_BYTES:
                                crc_state = 'partial: ZIP member exceeded declared or total byte limit'
                                break
                    if crc_state.startswith('partial'):
                        break
                    crc_bytes += member_bytes
                except (OSError, RuntimeError, zipfile.BadZipFile, NotImplementedError):
                    crc_state = 'failed'
                    crc_error = name
                    break
    top = {PurePosixPath(n.rstrip('/')).parts[0] for n in names if n.rstrip('/') and PurePosixPath(n.rstrip('/')).parts}
    return entry_count, total_expanded, names, top, crc_state, crc_error


def audit_release(directory: str | Path, expected_version: str = '', host_platform: str | None = None) -> list[AuditCheck]:
    """Return exactly 40 stable checks on regular top-level release files."""
    selected = Path(directory).expanduser().absolute()
    if selected.is_symlink() or not selected.is_dir():
        raise ReleaseAuditError('Choose an existing regular release directory.')
    root = selected.resolve()
    host_platform = (host_platform or platform.system()).lower()
    try:
        with os.scandir(root) as iterator:
            children = []
            for index, entry in enumerate(iterator, 1):
                if index > 2000:
                    raise ReleaseAuditError('Release directory exceeds 2,000 immediate entries.')
                children.append(Path(entry.path))
    except OSError as exc:
        raise ReleaseAuditError('Release directory could not be read.') from exc
    children.sort(key=lambda p: p.name.casefold())
    symlinks = [p.name for p in children if p.is_symlink()]
    files = [p for p in children if p.is_file() and not p.is_symlink()]
    if len(files) > MAX_ARTIFACTS:
        raise ReleaseAuditError('Release directory exceeds 500 regular artifacts.')
    total_size = sum(p.stat().st_size for p in files)
    oversized = [p.name for p in files if p.stat().st_size > MAX_ARTIFACT_BYTES]
    empty = [p.name for p in files if p.stat().st_size == 0]
    manifests = [p for p in files if p.name.lower() in {'sha256sums', 'sha256sums.txt', 'checksums.txt', 'checksums.sha256'} or p.name.lower().endswith('.sha256')]
    manifest_entries, manifest_errors = [], []
    manifest_overflow = False
    for path in manifests:
        rows, errors, overflow = _checksum_manifest(path)
        manifest_entries.extend((path.name, name, digest) for name, digest in rows)
        manifest_errors.extend(f'{path.name}: {error}' for error in errors)
        manifest_overflow |= overflow
    actual_names = {p.name for p in files}
    artifact_names = {p.name for p in files if p not in manifests and p.suffix.lower() not in {'.sig', '.asc'} }
    hash_names = [name for _manifest, name, _digest_value in manifest_entries]
    duplicate_hash_paths = sorted(name for name, count in Counter(hash_names).items() if count > 1)
    unlisted = sorted(name for name in hash_names if name not in actual_names)
    missing_hash = sorted(name for name in artifact_names if name not in hash_names)
    extra_hash = sorted(name for name in hash_names if name in {p.name for p in manifests})
    manifest_path_unsafe = any('unsafe artifact path' in error for error in manifest_errors)
    digest_mismatch, checked_hashes = [], 0
    hash_budget_hit = False
    hashed_total = 0
    for manifest_name, name, wanted in manifest_entries:
        artifact = root / name
        if name not in actual_names or not artifact.is_file() or artifact.is_symlink():
            continue
        size = artifact.stat().st_size
        if size > MAX_ARTIFACT_BYTES or hashed_total + size > MAX_TOTAL_BYTES:
            hash_budget_hit = True
            continue
        if artifact.name in manifests:
            continue
        got = _digest(artifact)
        hashed_total += size
        checked_hashes += 1
        if got != wanted:
            digest_mismatch.append(name)
    duplicate_names = len({p.name.casefold() for p in files}) != len(files)
    suffixes = sorted({p.suffix for p in files if p.suffix and p not in manifests})
    known_lower = {extension.lower() for extension in KNOWN_EXTENSIONS}
    unknown = sorted(p.name for p in files if p.suffix and p.suffix.lower() not in known_lower and p not in manifests)
    version_pairs = [(p.name, _version_tokens(p.name)) for p in files if p not in manifests]
    versions = sorted({v.lstrip('v') for _name, found in version_pairs for v in found})
    expected = expected_version.strip().removeprefix('v')
    version_mismatch = sorted(name for name, found in version_pairs if expected and found and all(v.lstrip('v') != expected for v in found))
    zip_files = [p for p in files if p.suffix.lower() == '.zip']
    zip_rows = []
    zip_errors, zip_partial, zip_many, zip_mixed_roots = [], [], [], []
    zip_total_entries = zip_total_expanded = 0
    for path in zip_files:
        try:
            count, expanded, names, top, crc, error = _zip_facts(path)
            zip_total_entries += count
            zip_total_expanded += expanded
            if count > MAX_ZIP_ENTRIES: zip_many.append(path.name)
            if crc == 'failed': zip_errors.append(f'{path.name}: {error}')
            if crc.startswith('partial'): zip_partial.append(path.name)
            if len(top) > 1: zip_mixed_roots.append(path.name)
            zip_rows.append((path.name, count, expanded))
        except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
            zip_errors.append(path.name + ': invalid or unreadable ZIP')
    platforms = {'linux': ('linux', 'linux-', 'linux_', '.deb', '.rpm', '.appimage', '.run'),
                 'windows': ('windows', 'win-', 'win_', '.exe', '.msi'),
                 'darwin': ('macos', 'mac-', 'mac_', 'darwin', '.dmg', '.pkg')}
    host_key = 'linux' if host_platform.startswith('linux') else ('windows' if host_platform.startswith('win') else ('darwin' if host_platform in ('darwin', 'macos') else host_platform))
    host_patterns = platforms.get(host_key, (host_key,))
    named_for_host = [p.name for p in files if any(pattern in p.name.lower() for pattern in host_patterns)]
    linux_package_names = [p.name for p in files if p.suffix.lower() in {'.deb', '.rpm', '.appimage', '.run'}]
    deb_files = [p for p in files if p.suffix.lower() == '.deb']
    deb_magic = []
    for path in deb_files:
        try:
            with path.open('rb') as stream: deb_magic.append((path.name, stream.read(8) == b'!<arch>\n'))
        except OSError: deb_magic.append((path.name, False))
    deb_invalid = [name for name, valid in deb_magic if not valid]
    extensions = {p.suffix.lower() for p in files}
    archive_without_manifest = bool(artifact_names) and not manifests
    signature_count = sum(p.suffix.lower() in {'.sig', '.asc'} for p in files)
    standalone_count = sum(p.suffix.lower() in {'.run', '.appimage', '.exe'} for p in files)
    checks = [
        _check('directory', 'Release directory', 'ok', root),
        _check('artifact_count', 'Regular artifact count', 'review' if not files else 'ok', len(files)),
        _check('artifact_limit', 'Artifact count within limit', 'ok', f'{len(files)} / {MAX_ARTIFACTS}'),
        _check('symlinks', 'Symbolic link entries', 'review' if symlinks else 'ok', ', '.join(symlinks) or 'None'),
        _check('empty_files', 'Zero-byte files', 'review' if empty else 'ok', ', '.join(empty) or 'None'),
        _check('total_size', 'Total artifact bytes', 'info', f'{total_size:,}'),
        _check('artifact_size_limit', 'Artifacts above 2 GiB', 'review' if oversized else 'ok', ', '.join(oversized) or 'None'),
        _check('artifact_total_limit', 'Checksum processing budget', 'review' if total_size > MAX_TOTAL_BYTES else 'ok', f'{total_size:,} / {MAX_TOTAL_BYTES:,} bytes'),
        _check('filename_case_duplicates', 'Case-insensitive duplicate filenames', 'review' if duplicate_names else 'ok', 'Present' if duplicate_names else 'None'),
        _check('artifact_extensions', 'Artifact file types', 'info', ', '.join(suffixes) or 'No extensions'),
        _check('unknown_extensions', 'Unrecognized extensions', 'review' if unknown else 'ok', ', '.join(unknown) or 'None'),
        _check('filename_versions', 'Versions found in artifact names', 'info', ', '.join(versions) or 'None'),
        _check('version_consistency', 'Mixed artifact versions', 'review' if len(versions) > 1 else 'ok', ', '.join(versions) or 'No version tokens found'),
        _check('expected_version', 'Expected version', 'info' if expected else 'review', expected or 'Not supplied'),
        _check('version_mismatches', 'Artifact names that differ from expected version', 'review' if version_mismatch else 'ok', ', '.join(version_mismatch) or 'None'),
        _check('checksum_manifests', 'Checksum manifest count', 'ok' if manifests else 'review', len(manifests)),
        _check('checksum_manifest_names', 'Checksum manifest filenames', 'info', ', '.join(p.name for p in manifests) or 'None'),
        _check('checksum_entries', 'Parsed SHA-256 entries', 'info', len(manifest_entries)),
        _check('checksum_manifest_errors', 'Malformed checksum rows', 'error' if manifest_errors else 'ok', '; '.join(manifest_errors[:8]) or 'None'),
        _check('checksum_manifest_budget', 'Manifest size and line limits', 'review' if manifest_overflow else 'ok', 'Exceeded' if manifest_overflow else 'Within bounds'),
        _check('checksum_path_safety', 'Unsafe checksum paths', 'error' if manifest_path_unsafe else 'ok', 'Present' if manifest_path_unsafe else 'None'),
        _check('checksum_duplicate_paths', 'Duplicate manifest paths', 'review' if duplicate_hash_paths else 'ok', ', '.join(duplicate_hash_paths) or 'None'),
        _check('checksum_missing_artifacts', 'Manifest references to missing files', 'error' if unlisted else 'ok', ', '.join(unlisted) or 'None'),
        _check('checksum_unlisted_artifacts', 'Artifacts without checksum entries', 'review' if missing_hash else 'ok', ', '.join(missing_hash) or 'None'),
        _check('checksum_unlisted_rows', 'Manifest files included as artifacts', 'review' if extra_hash else 'ok', ', '.join(extra_hash) or 'None'),
        _check('checksum_verified', 'Verified SHA-256 entries', 'ok' if checked_hashes and not digest_mismatch else ('review' if not checked_hashes else 'error'), checked_hashes),
        _check('checksum_mismatch', 'Checksum mismatches', 'error' if digest_mismatch else 'ok', ', '.join(digest_mismatch) or 'None'),
        _check('checksum_read_budget', 'Checksum byte budget', 'review' if hash_budget_hit else 'ok', 'Some artifacts skipped' if hash_budget_hit else f'{hashed_total:,} bytes hashed'),
        _check('checksum_algorithm', 'Checksum algorithm supported', 'info', 'SHA-256 rows only; other formats are reported malformed'),
        _check('checksum_absent', 'Release artifacts have checksum coverage', 'review' if archive_without_manifest or missing_hash else 'ok', 'Manifest absent or entries missing' if archive_without_manifest or missing_hash else 'Covered'),
        _check('zip_count', 'ZIP artifact count', 'info', len(zip_files)),
        _check('zip_entry_count', 'ZIP member count', 'review' if zip_many else 'ok', f'{zip_total_entries} total; {MAX_ZIP_ENTRIES} per ZIP limit'),
        _check('zip_expanded_size', 'ZIP declared expanded bytes', 'review' if zip_total_expanded > MAX_TOTAL_BYTES else 'info', f'{zip_total_expanded:,}'),
        _check('zip_integrity', 'ZIP member CRC read check', 'error' if zip_errors else ('review' if zip_partial else ('info' if zip_files else 'ok')), '; '.join(zip_errors + zip_partial) or ('Checked' if zip_files else 'No ZIP artifacts')),
        _check('zip_layout', 'ZIP files with multiple top-level roots', 'review' if zip_mixed_roots else 'info', ', '.join(zip_mixed_roots) or 'None'),
        _check('platform_coverage', 'Artifacts named for host platform', 'ok' if named_for_host else 'review', ', '.join(named_for_host) or f'No filename matches {host_key}'),
        _check('linux_packages', 'Linux package artifacts', 'info', ', '.join(linux_package_names) or 'None'),
        _check('deb_archive_format', 'Debian archive magic', 'error' if deb_invalid else ('ok' if deb_files else 'info'), ', '.join(deb_invalid) or (f'{len(deb_files)} valid ar archive(s)' if deb_files else 'No .deb artifacts')),
        _check('signatures', 'Detached signature artifact count', 'info', signature_count),
        _check('standalone_installers', 'Standalone installer count', 'info', standalone_count),
    ]
    assert len(checks) == 40
    return checks


def audit_json(directory: str | Path, expected_version: str = '', host_platform: str | None = None) -> str:
    return json.dumps([asdict(row) for row in audit_release(directory, expected_version, host_platform)], ensure_ascii=False, indent=2)


def create_checksum_manifest(directory: str | Path, output: str | Path) -> tuple[Path, int]:
    """Write an atomic SHA-256 manifest for regular top-level artifacts only."""
    root = Path(directory).expanduser().absolute()
    if root.is_symlink() or not root.is_dir():
        raise ReleaseAuditError('Choose an existing regular release directory.')
    target = Path(output).expanduser().absolute()
    if target.exists() and (target.is_symlink() or not target.is_file()):
        raise ReleaseAuditError('Checksum output must be a regular file, not a link or directory.')
    allowed_names = {'sha256sums', 'sha256sums.txt', 'checksums.txt', 'checksums.sha256'}
    if target.name.lower() not in allowed_names and not target.name.lower().endswith('.sha256'):
        raise ReleaseAuditError('Choose a checksum manifest name such as SHA256SUMS.txt.')
    if target.exists() and target.name not in ('SHA256SUMS', 'SHA256SUMS.txt', 'checksums.txt', 'checksums.sha256') and not target.name.lower().endswith('.sha256'):
        raise ReleaseAuditError('Refusing to replace a file that is not a checksum manifest.')
    if not target.parent.is_dir():
        raise ReleaseAuditError('Checksum output folder does not exist.')
    try:
        children = list(root.iterdir())
    except OSError:
        raise ReleaseAuditError('Release directory could not be read.') from None
    if len(children) > 2000:
        raise ReleaseAuditError('Release directory exceeds 2,000 immediate entries.')
    if any(path.is_symlink() for path in children):
        raise ReleaseAuditError('Release directory contains symbolic links; no manifest was written.')
    files = [p for p in children if p.is_file() and not p.is_symlink()
             and p.name.lower() not in allowed_names and not p.name.lower().endswith(('.sha256', '.sig', '.asc'))]
    files.sort(key=lambda p: p.name.casefold())
    if len(files) > MAX_ARTIFACTS:
        raise ReleaseAuditError('Release directory exceeds 500 regular artifacts.')
    total = sum(p.stat().st_size for p in files)
    if total > MAX_TOTAL_BYTES or any(p.stat().st_size > MAX_ARTIFACT_BYTES for p in files):
        raise ReleaseAuditError('Release artifacts exceed the 5 GiB total or 2 GiB per-file hash budget.')
    rows = []
    for path in files:
        if any(ord(ch) < 32 or ch in '\r\n' for ch in path.name):
            raise ReleaseAuditError('Artifact filename cannot be represented safely in a checksum manifest.')
        digest = hashlib.sha256()
        try:
            with open_regular(path) as stream:
                before = os.fstat(stream.fileno())
                size = 0
                while block := stream.read(CHUNK):
                    size += len(block)
                    if size > MAX_ARTIFACT_BYTES:
                        raise ReleaseAuditError('Artifact exceeded the per-file hash budget while reading.')
                    digest.update(block)
                after = os.fstat(stream.fileno())
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns) or size != before.st_size:
                raise ReleaseAuditError('Artifact changed while its checksum was being generated: ' + path.name)
        except OSError:
            raise ReleaseAuditError('Artifact could not be read safely: ' + path.name) from None
        rows.append(f'{digest.hexdigest()}  {path.name}\n')
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', newline='\n', dir=target.parent,
                                         prefix='.octoship-checksums-', delete=False) as stream:
            temporary = Path(stream.name)
            os.chmod(temporary, 0o600)
            stream.writelines(rows)
            stream.flush()
            os.fsync(stream.fileno())
        if target.is_symlink():
            raise ReleaseAuditError('Checksum output became a symbolic link; no file was replaced.')
        os.replace(temporary, target)
        temporary = None
        return target, len(rows)
    except OSError:
        raise ReleaseAuditError('Checksum manifest could not be written atomically.') from None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
