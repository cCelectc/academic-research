import os
import subprocess
import sys
from pathlib import Path


def _create_venv(venv_dir, requirements):
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
    script_path = Path(script_file).resolve()
    script_dir = script_path.parent
    venv_dir = script_dir / ".venv"
    venv_python = venv_dir / "bin" / "python"
    requirements = script_dir / "requirements.txt"

    if not venv_dir.exists():
        _create_venv(venv_dir, requirements)

    if sys.executable != str(venv_python) and venv_python.exists():
        os.execv(str(venv_python), [str(venv_python), str(script_path)] + sys.argv[1:])
