"""Entry point run by the bundled interpreter with Python isolated mode."""
from pathlib import Path
import sys
import os

ROOT = Path(__file__).resolve().parent
os.environ['OCTOSHIP_BUNDLE_ROOT'] = str(ROOT)
sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'app'))

if sys.argv[1:2] == ['--diagnostics']:
    import json
    import ssl
    import subprocess
    import tkinter
    from octoship import __version__
    print(json.dumps({
        'octoship': __version__, 'python': sys.version.split()[0],
        'python_executable': sys.executable, 'isolated': bool(sys.flags.isolated),
        'tk': tkinter.TkVersion, 'tcl': tkinter.TclVersion,
        'github_cli': subprocess.check_output([str(ROOT / 'bin/gh'), '--version'], text=True).splitlines()[0],
        'ca_certificates': len(ssl.create_default_context().get_ca_certs()),
        'bundle': str(ROOT),
    }, indent=2))
elif sys.argv[1:2] == ['--installer']:
    from installer import main
    main(sys.argv[2:])
elif sys.argv[1:2] == ['--uninstall']:
    from installer import uninstall
    uninstall(ROOT)
else:
    from octoship.app import main
    main()
