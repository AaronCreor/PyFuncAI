"""Install wheel/sdist artifacts and test them outside the source checkout."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import venv


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("artifacts", nargs="+", type=Path)
    args = parser.parse_args()
    artifacts = [path.resolve(strict=True) for path in args.artifacts]
    root = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.pop("PYTHONPATH", None)
    environment.pop("PYFUNCAI_RUN_OLLAMA_TESTS", None)
    with tempfile.TemporaryDirectory(prefix="pyfuncai-distribution-") as directory:
        temporary = Path(directory)
        target = temporary / "venv"
        venv.EnvBuilder(with_pip=True).create(target)
        python = target / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        cli = target / ("Scripts/pyfuncai.exe" if os.name == "nt" else "bin/pyfuncai")
        tests = temporary / "tests"
        shutil.copytree(
            root / "tests", tests, ignore=shutil.ignore_patterns("__pycache__")
        )

        def run(*command: str) -> None:
            subprocess.run(command, cwd=temporary, env=environment, check=True)

        run(str(python), "-m", "pip", "install", "--quiet", "pytest>=8")
        for artifact in artifacts:
            print(f"Testing installed distribution: {artifact.name}", flush=True)
            run(
                str(python),
                "-m",
                "pip",
                "install",
                "--quiet",
                "--no-deps",
                "--force-reinstall",
                str(artifact),
            )
            run(
                str(python),
                "-I",
                "-c",
                "import pyfuncai; from importlib.resources import files; "
                "assert files('pyfuncai').joinpath('py.typed').is_file(); "
                "print('Installed:', pyfuncai.__version__, pyfuncai.__file__)",
            )
            run(str(cli), "--help")
            run(str(python), "-I", "-m", "pytest", str(tests), "-q")


if __name__ == "__main__":
    main()
