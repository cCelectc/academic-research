import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT = REPO_ROOT / "pyproject.toml"
REQUIREMENTS = (
    REPO_ROOT / "skills" / "academic-research" / "scripts" / "requirements.txt"
)


def main():
    with open(PYPROJECT, "rb") as fh:
        data = tomllib.load(fh)
    deps = data["project"]["dependencies"]
    REQUIREMENTS.write_text("".join(f"{dep}\n" for dep in deps), encoding="utf-8")


if __name__ == "__main__":
    main()
