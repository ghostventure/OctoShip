"""Private, atomic local JSON settings and explicit preparation plans."""
import json
import os
from pathlib import Path
import tempfile
from .core import OctoShipError


def state_root():
    return Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'octoship'


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix='.octoship-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name): os.unlink(name)


def load_json(path, limit=1024**2):
    from .core import open_regular
    with open_regular(path) as stream:
        data = stream.read(limit + 1)
    if len(data) > limit: raise OctoShipError('JSON file exceeds its size limit.')
    try: return json.loads(data)
    except (ValueError, UnicodeError): raise OctoShipError('Invalid JSON file.') from None
