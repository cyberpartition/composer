"""Launch Composer from a terminal: python composer.py"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
if not getattr(sys, "frozen", False) and VENV_PYTHON.is_file():
    current = os.path.normcase(str(Path(sys.executable).resolve()))
    bundled = os.path.normcase(str(VENV_PYTHON.resolve()))
    if current != bundled:
        os.execv(str(VENV_PYTHON), [str(VENV_PYTHON), str(Path(__file__).resolve()), *sys.argv[1:]])

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:
    from composer.app import main
except ImportError:
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(
            0,
            "Composer is missing its setup.\n\nDouble-click run_composer.bat once to install it.",
            "Composer",
            0x40,
        )
    else:
        print("Composer is missing its setup. Run: pip install -r requirements.txt")
    raise SystemExit(1)

raise SystemExit(main())
