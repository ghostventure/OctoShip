"""Bounded, read-only project readiness diagnostics.

This audit checks common repository metadata, package manifests, source hygiene,
and CI workflow hazards. It never executes project code and never prints file
contents. Each diagnostic has a stable code suitable for UI filtering.
"""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import stat
import xml.etree.ElementTree as ET

MAX_FILES = 10_000
MAX_FILE_BYTES = 256 * 1024
MAX_TOTAL_BYTES = 8 * 1024 * 1024


@dataclass(frozen=True)
class Diagnostic:
    code: str
    path: str
    message: str


def _files(root):
    """Yield regular files in a bounded tree; reject links and traversal errors."""
    count = 0
    for folder, dirs, names in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in {'.git', '.hg', '.svn', 'node_modules', '.venv', 'venv', '__pycache__', 'bin', 'obj', 'dist', 'build'})
        for name in sorted(dirs + names):
            path = Path(folder, name)
            mode = path.lstat().st_mode
            if stat.S_ISLNK(mode):
                yield path, 'symlink'
        for name in names:
            path = Path(folder, name)
            if stat.S_ISREG(path.lstat().st_mode):
                count += 1
                if count > MAX_FILES:
                    raise ValueError('Project audit stopped: more than 10,000 files.')
                yield path, 'file'


def audit_project(folder):
    """Return bounded diagnostics for a local project folder (read-only)."""
    root = Path(folder).expanduser().absolute()
    if not root.is_dir() or root.is_symlink():
        raise ValueError('Choose a regular project folder.')
    paths = {}
    symlinks = []
    total = 0
    for path, kind in _files(root):
        rel = path.relative_to(root).as_posix()
        if kind == 'symlink':
            symlinks.append(rel)
            continue
        size = path.stat().st_size
        total += min(size, MAX_FILE_BYTES)
        if total > MAX_TOTAL_BYTES:
            raise ValueError('Project audit stopped: content exceeds the 8 MiB read limit.')
        data = b''
        if size <= MAX_FILE_BYTES:
            with path.open('rb') as stream:
                data = stream.read(MAX_FILE_BYTES + 1)
        paths[rel] = (path, size, data)
    lower = {name.casefold(): name for name in paths}
    diagnostics = []

    def add(code, path, message):
        diagnostics.append(Diagnostic(code, path, message))

    def exists(*candidates):
        for candidate in candidates:
            folded = candidate.casefold().rstrip('/')
            if folded in lower or any(name.startswith(folded + '/') for name in lower):
                return True
        return False

    # Repository handoff metadata (12 independent checks).
    required = (
        ('META_README', ('README', 'README.md', 'README.rst'), 'Add a README with project purpose and startup instructions.'),
        ('META_LICENSE', ('LICENSE', 'LICENSE.md', 'LICENSE.txt', 'COPYING'), 'Add a license so reuse terms are clear.'),
        ('META_SECURITY', ('SECURITY.md',), 'Add a security reporting route.'),
        ('META_CONTRIBUTING', ('CONTRIBUTING.md',), 'Document how contributors can build and submit changes.'),
        ('META_CODE_OF_CONDUCT', ('CODE_OF_CONDUCT.md',), 'Add contributor conduct guidance.'),
        ('META_CHANGELOG', ('CHANGELOG.md', 'CHANGES.md', 'HISTORY.md'), 'Add release history for users and maintainers.'),
        ('META_GITIGNORE', ('.gitignore',), 'Add ignore rules for generated and local files.'),
        ('META_EDITORCONFIG', ('.editorconfig',), 'Add shared editor defaults for consistent files.'),
        ('META_CODEOWNERS', ('.github/CODEOWNERS', 'CODEOWNERS'), 'Add ownership routing for review requests.'),
        ('META_ISSUE_TEMPLATE', ('.github/ISSUE_TEMPLATE',), 'Add an issue template directory or file.'),
        ('META_PR_TEMPLATE', ('.github/PULL_REQUEST_TEMPLATE.md', 'PULL_REQUEST_TEMPLATE.md'), 'Add a pull request checklist.'),
        ('META_CI', ('.github/workflows',), 'Add a CI workflow so changes receive repeatable checks.'),
    )
    for code, candidates, message in required:
        if not exists(*candidates):
            add(code, '.', message)

    texts = {}
    for rel, (path, size, data) in paths.items():
        if size > MAX_FILE_BYTES:
            add('FILE_TOO_LARGE', rel, 'File exceeds the 256 KiB audit read limit; inspect separately.')
            continue
        if b'\0' in data:
            continue
        try:
            texts[rel] = data.decode('utf-8-sig')
        except UnicodeError:
            continue

    # Manifest checks (12).
    package_name = lower.get('package.json')
    if package_name:
        rel = package_name; text = texts.get(rel, '')
        try:
            package = json.loads(text)
            if not isinstance(package, dict): raise ValueError()
        except (ValueError, TypeError):
            package = None; add('MANIFEST_PACKAGE_JSON', rel, 'package.json is not a valid JSON object.')
        if package is not None:
            if not isinstance(package.get('version'), str) or not package['version'].strip():
                add('MANIFEST_PACKAGE_VERSION', rel, 'Declare a non-empty package version.')
            scripts = package.get('scripts') if isinstance(package.get('scripts'), dict) else {}
            if not scripts.get('test'):
                add('MANIFEST_PACKAGE_TEST', rel, 'Define a package test script for repeatable checks.')
            if not scripts.get('build'):
                add('MANIFEST_PACKAGE_BUILD', rel, 'Define a package build script for reproducible output.')
            if not any(x in lower for x in ('package-lock.json', 'npm-shrinkwrap.json', 'yarn.lock', 'pnpm-lock.yaml')):
                add('MANIFEST_PACKAGE_LOCK', rel, 'No JavaScript dependency lockfile is present.')
    pyproject = lower.get('pyproject.toml')
    if pyproject:
        try:
            import tomllib
            tomllib.loads(texts.get(pyproject, ''))
        except (ValueError, ModuleNotFoundError):
            add('MANIFEST_PYPROJECT', pyproject, 'pyproject.toml is invalid TOML or cannot be checked by this Python runtime.')
    req = lower.get('requirements.txt')
    if req:
        lines = texts.get(req, '').splitlines()
        if not any(line.strip() and not line.lstrip().startswith('#') for line in lines):
            add('MANIFEST_REQUIREMENTS_EMPTY', req, 'requirements.txt contains no active dependency entries.')
        elif any(line.strip().startswith(('-e ', '--editable ')) for line in lines):
            add('MANIFEST_REQUIREMENTS_EDITABLE', req, 'Editable local dependencies may not resolve in clean builds.')
    csproj = next((x for x in lower.values() if x.endswith('.csproj')), None)
    if csproj:
        try:
            xml = ET.fromstring(texts.get(csproj, ''))
        except ET.ParseError:
            xml = None; add('MANIFEST_CSPROJ_XML', csproj, 'Project file is not well-formed XML.')
        if xml is not None and not any(x.tag.split('}')[-1] in ('TargetFramework', 'TargetFrameworks') for x in xml.iter()):
            add('MANIFEST_CSPROJ_FRAMEWORK', csproj, 'Declare TargetFramework or TargetFrameworks.')
    if 'global.json' in lower:
        try:
            global_data = json.loads(texts.get(lower['global.json'], ''))
            if not isinstance(global_data, dict) or not isinstance(global_data.get('sdk'), dict): raise ValueError()
            if not global_data['sdk'].get('version'): raise ValueError()
        except (ValueError, TypeError):
            add('MANIFEST_DOTNET_SDK', lower['global.json'], 'global.json needs a valid sdk.version.')
    if 'directory.build.props' in lower:
        rel = lower['directory.build.props']
        try: ET.fromstring(texts.get(rel, ''))
        except ET.ParseError: add('MANIFEST_BUILD_PROPS', rel, 'Directory.Build.props is not well-formed XML.')

    # Repository structure and source integrity (10).
    by_fold = {}
    for rel in paths:
        by_fold.setdefault(rel.casefold(), []).append(rel)
        if any(c.isspace() for c in Path(rel).name):
            add('PATH_WHITESPACE', rel, 'Whitespace in a filename can complicate scripts and release automation.')
        if Path(rel).name in ('.env', '.env.local', 'id_rsa', 'id_ed25519') or Path(rel).suffix.lower() in ('.pem', '.p12', '.pfx', '.keystore'):
            add('PATH_SENSITIVE_NAME', rel, 'Sensitive-looking file name should be excluded from source publication.')
        path, size, data = paths[rel]
        if size == 0 and Path(rel).name not in ('.gitkeep', '.keep'):
            add('FILE_EMPTY', rel, 'File is empty; remove it or add its intended content.')
        text = texts.get(rel)
        if text is not None and text:
            if not text.endswith('\n'):
                add('TEXT_FINAL_NEWLINE', rel, 'Text file has no final newline.')
            if re.search(r'(?m)[ \t]+$', text):
                add('TEXT_TRAILING_SPACE', rel, 'Text contains trailing whitespace.')
            if '\r\n' in text and re.search(r'(?<!\r)\n', text):
                add('TEXT_MIXED_EOL', rel, 'Text mixes CRLF and LF line endings.')
            if re.search(r'(?m)^(?:<<<<<<< |=======\s*$|>>>>>>> )', text):
                add('TEXT_CONFLICT_MARKER', rel, 'Text contains a merge conflict marker.')
    for names in by_fold.values():
        if len(names) > 1:
            add('PATH_CASE_COLLISION', ', '.join(sorted(names)), 'Paths differ only by letter case and collide on some filesystems.')
    for rel in symlinks:
        add('PATH_SYMLINK', rel, 'Symbolic links are not followed during this audit; review before publishing.')

    # GitHub workflow hardening (6 distinct diagnostics).
    workflow_files = [(p, t) for p, t in texts.items() if p.startswith('.github/workflows/') and p.lower().endswith(('.yml', '.yaml'))]
    for rel, text in workflow_files:
        if re.search(r'(?m)^\s*permissions\s*:\s*write-all\s*$', text):
            add('CI_WRITE_ALL', rel, 'Workflow grants write-all permissions; narrow permissions to required scopes.')
        if re.search(r'(?m)^\s*(?:-\s*)?uses\s*:\s*[^\s@]+@(main|master|latest)\s*$', text, re.I):
            add('CI_MUTABLE_REF', rel, 'Workflow action uses a mutable branch or latest tag; pin a reviewed version or commit.')
        if re.search(r'(?m)^\s*pull_request_target\s*:', text):
            add('CI_PR_TARGET', rel, 'pull_request_target workflows need careful untrusted-code and secret isolation review.')
        if re.search(r'(?m)^\s*permissions\s*:\s*write-all\s*$', text):
            pass
        elif re.search(r'(?m)^\s*permissions\s*:', text) and re.search(r'(?m)^\s*contents\s*:\s*write\s*$', text):
            add('CI_CONTENTS_WRITE', rel, 'Workflow can write repository contents; verify that job requires this permission.')
        if re.search(r'(?m)^\s*(?:-\s*)?uses\s*:\s*[^\s@]+@v?\d+(?:\.\d+)?\s*$', text):
            add('CI_TAG_PIN', rel, 'Workflow action is version-tag pinned, not immutable; consider a full commit SHA.')
        if not re.search(r'(?m)^\s*permissions\s*:', text):
            add('CI_PERMISSIONS', rel, 'Workflow has no explicit permissions block; set least-privilege token scopes.')

    # De-duplicate exact findings, preserving deterministic traversal order.
    unique = {}
    for item in diagnostics:
        unique[(item.code, item.path, item.message)] = item
    return sorted(unique.values(), key=lambda x: (x.code, x.path.casefold(), x.path))
