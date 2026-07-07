"""Self-bootstrap a per-script virtual environment before third-party imports.

Each CLI script calls :func:`ensure_venv` at import time so it can run
standalone: on first run it creates a local ``.venv`` next to the script from
``requirements.txt`` (via ``uv`` when available, else ``venv`` + ``pip``) and
re-executes itself inside that interpreter.
"""

import os
import subprocess
import sys
from pathlib import Path


def _create_venv(venv_dir, requirements):
    """Create ``venv_dir`` and install ``requirements`` into it.

    Prefers ``uv venv`` + ``uv pip install``; falls back to stdlib ``venv`` plus
    ``pip`` if ``uv`` is unavailable. Exits if the requirements file is missing.
    """
    if not requirements.exists():
        print(
            f"[bootstrap] Error: requirements not found: {requirements}",
            file=sys.stderr,
        )
        sys.exit(1)
    print("[bootstrap] Creating virtual environment...", file=sys.stderr)
    venv_python = venv_dir / "bin" / "python"
    try:
        subprocess.run(["uv", "venv", str(venv_dir)], check=True, capture_output=True)
        subprocess.run(
            [
                "uv",
                "pip",
                "install",
                "--python",
                str(venv_python),
                "-r",
                str(requirements),
            ],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        pip = str(venv_dir / "bin" / "pip")
        subprocess.run([pip, "install", "-r", str(requirements)], check=True)
    print("[bootstrap] Done.", file=sys.stderr)


def ensure_venv(script_file):
    """Ensure the script's local ``.venv`` exists and re-exec into it.

    ``script_file`` is the calling script's ``__file__``. Creates the sibling
    ``.venv`` on first run, then, if not already running under it, replaces the
    current process with the venv interpreter (``os.execv``).
    """
    script_path = Path(script_file).resolve()
    script_dir = script_path.parent
    venv_dir = script_dir / ".venv"
    venv_python = venv_dir / "bin" / "python"
    requirements = script_dir / "requirements.txt"

    if not venv_dir.exists():
        _create_venv(venv_dir, requirements)

    if sys.executable != str(venv_python) and venv_python.exists():
        os.execv(str(venv_python), [str(venv_python), str(script_path)] + sys.argv[1:])
