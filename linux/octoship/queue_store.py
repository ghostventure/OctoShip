"""Opt-in local queue journals. No tokens, file bodies, or review approvals persist."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from .core import GitHub, OctoShipError, validate_path, MAX_BYTES, read_file
from .workflows import validate_branch

class QueueStore:
    def __init__(self, directory=None):
        self.directory = Path(directory or Path(os.environ.get('XDG_STATE_HOME', Path.home() / '.local/state')) / 'octoship/queues')

    def path(self, repo, branch):
        GitHub('').repo_path(repo)
        validate_branch(branch)
        return self.directory / (hashlib.sha256((repo.lower() + '\n' + branch).encode()).hexdigest() + '.json')

    def validate(self, snapshot, repo, branch):
        try:
            if (set(snapshot) != {'version', 'repository', 'branch', 'mode', 'message', 'entries'}
                    or snapshot['version'] != 1 or snapshot['repository'].lower() != repo.lower()
                    or snapshot['branch'] != branch or snapshot['mode'] not in ('per-file', 'atomic')
                    or not isinstance(snapshot['message'], str) or not 1 <= len(snapshot['message']) <= 250
                    or not isinstance(snapshot['entries'], list) or not 1 <= len(snapshot['entries']) <= 100):
                raise ValueError()
            paths = set()
            for row in snapshot['entries']:
                if set(row) != {'source', 'destination', 'digest', 'size', 'status'}:
                    raise ValueError()
                if (not isinstance(row['source'], str) or not Path(row['source']).is_absolute()
                        or not isinstance(row['size'], int) or not 0 <= row['size'] <= MAX_BYTES
                        or not re.fullmatch('[0-9a-f]{64}', row['digest'])
                        or row['status'] not in ('pending', 'uploading', 'uploaded', 'failed', 'uncertain')):
                    raise ValueError()
                validate_path(row['destination'])
                if row['destination'] in paths: raise ValueError()
                paths.add(row['destination'])
        except (KeyError, TypeError, AttributeError, ValueError):
            raise OctoShipError('Saved queue is invalid. Forget it and select the files again.') from None
        return snapshot

    def save(self, snapshot):
        repo, branch = snapshot['repository'], snapshot['branch']
        self.validate(snapshot, repo, branch)
        path = self.path(repo, branch)
        self.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.directory, 0o700)
        fd, temporary = tempfile.mkstemp(prefix='.queue-', dir=self.directory)
        try:
            with os.fdopen(fd, 'w') as stream:
                json.dump(snapshot, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary): os.unlink(temporary)

    def load(self, repo, branch):
        path = self.path(repo, branch)
        try:
            with path.open('rb') as stream:
                data = stream.read(2 * 1024 * 1024 + 1)
            if len(data) > 2 * 1024 * 1024: raise ValueError()
            return self.validate(json.loads(data), repo, branch)
        except FileNotFoundError:
            return None
        except (ValueError, UnicodeError):
            raise OctoShipError('Saved queue is damaged or too large.') from None

    def delete(self, repo, branch):
        self.path(repo, branch).unlink(missing_ok=True)

    def resume(self, repo, branch):
        snapshot = self.load(repo, branch)
        if snapshot is None: raise OctoShipError('No saved queue for this repository and branch.')
        pending = [row for row in snapshot['entries'] if row['status'] != 'uploaded']
        for row in pending:
            data = read_file(row['source'])
            if len(data) != row['size'] or hashlib.sha256(data).hexdigest() != row['digest']:
                raise OctoShipError('Saved source changed. Select it again for a new review: ' + Path(row['source']).name)
        return snapshot, pending

    @staticmethod
    def snapshot(repo, branch, mode, message, items):
        return {'version': 1, 'repository': repo, 'branch': branch, 'mode': mode, 'message': message,
                'entries': [{'source': str(item.local.absolute()), 'destination': item.destination,
                             'digest': item.digest, 'size': item.size, 'status': 'pending'} for item in items]}
