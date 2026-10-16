"""Optional, shell-free integration with Visual Studio Code on Linux."""

from pathlib import Path
import shutil
import subprocess

from .core import OctoShipError


def vscode_command(path):
    target = Path(path).expanduser().resolve(strict=True)
    if not target.is_file() and not target.is_dir():
        raise OctoShipError('Choose an existing regular file or folder to open in VS Code.')
    executable = shutil.which('code')
    if not executable:
        raise OctoShipError('VS Code command `code` was not found. Install VS Code or add its command to PATH.')
    args = [executable, '--reuse-window']
    if target.is_file() and target.suffix.casefold() != '.code-workspace':
        args.append('--goto')
    args.append(str(target))
    return args, str(target if target.is_dir() else target.parent)


def open_in_vscode(path):
    args, working_directory = vscode_command(path)
    return subprocess.Popen(args, cwd=working_directory, shell=False, close_fds=True)
