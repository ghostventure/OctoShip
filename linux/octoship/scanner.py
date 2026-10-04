"""Bounded heuristic scanning; results never contain matched credential values."""
from dataclasses import dataclass
import re
from .core import OctoShipError

MAX_SCAN = 2 * 1024 * 1024
RULES = (
    ('Private key', r'-----BEGIN (?:RSA |EC |OPENSSH |DSA |ENCRYPTED )?PRIVATE KEY-----'),
    ('GitHub token', r'\b(?:gh[pousr]_[A-Za-z0-9]{20,255}|github_pat_[A-Za-z0-9_]{20,255})\b'),
    ('AWS access key ID', r'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
    ('Slack token', r'\bxox[baprs]-[A-Za-z0-9-]{20,255}\b'),
    ('Google API key', r'\bAIza[A-Za-z0-9_-]{35}\b'),
    ('Possible credential assignment', r'''(?im)\b(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|secret[_-]?key)\b["']?\s*[:=]\s*["'][^"'\r\n]{8,256}["']'''),
    ('Possible unquoted credential assignment', r'''(?im)^\s*(?:export\s+)?(?:password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|secret[_-]?key)\s*[:=]\s*[^\s"'${<][^\s#]{7,255}\s*$'''),
)

@dataclass(frozen=True)
class Scan:
    findings: tuple
    status: str
    complete: bool

    @property
    def needs_review(self):
        return bool(self.findings) or not self.complete

    @property
    def summary(self):
        return self.status + ''.join(f'\n{kind} near line {line} (value hidden)' for kind, line in self.findings)


def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise OctoShipError('Operation cancelled. Completed remote operations remain.')


def scan_bytes(data, cancel=None):
    check_cancel(cancel)
    if len(data) > MAX_SCAN:
        return Scan((), 'Not scanned: exceeds the 2 MiB scan limit.', False)
    try:
        if data.startswith((b'\xff\xfe', b'\xfe\xff')):
            content = data.decode('utf-16')
        elif b'\0' in data:
            return Scan((), 'Not scanned: binary content. Archives are not unpacked.', False)
        else:
            content = data.decode('utf-8-sig')
    except UnicodeError:
        return Scan((), 'Not scanned: unsupported text encoding.', False)
    findings = []
    # Scan bounded lines so whitespace patterns cannot backtrack across a whole file.
    # Oversized lines are explicitly incomplete, never reported as clean.
    complete = True
    for line_number, line in enumerate(content.splitlines(), 1):
        check_cancel(cancel)
        if len(line) > 8192:
            complete = False
            line = line[:8192]
        for kind, pattern in RULES:
            for _ in re.finditer(pattern, line):
                findings.append((kind, line_number))
                if len(findings) >= 30:
                    return Scan(tuple(findings), 'Scan stopped at 30 findings. Review the entire file.', False)
    status = ('Potential secrets detected. Review before uploading.' if findings else
              'No supported secret patterns detected. This cannot prove a file is safe.')
    if not complete:
        status += ' Incomplete: a line exceeds 8,192 characters.'
    return Scan(tuple(findings), status, complete)


def require_scan_approval(data, approved=False, cancel=None):
    result = scan_bytes(data, cancel)
    if result.needs_review and not approved:
        raise OctoShipError('Content review acknowledgement required. ' + result.summary)
    return result
