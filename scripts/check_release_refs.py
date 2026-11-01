"""Exercise actual release workflow verification against isolated Git remotes."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import yaml


def check(workflow: Path, branch: str, version: str, kind: str) -> None:
    data = yaml.safe_load(workflow.read_text(encoding="utf-8"))
    script = next(
        step["run"]
        for step in data["jobs"]["verify"]["steps"]
        if step.get("id") == "verify"
    )
    bash = shutil.which("bash")
    if os.name == "nt":
        git = Path(shutil.which("git") or "")
        git_bash = git.parent.parent / "bin/bash.exe"
        if git_bash.is_file():
            bash = str(git_bash)
    if not bash:
        raise RuntimeError("Bash is required to verify GitHub release workflows.")
    with tempfile.TemporaryDirectory(prefix="pyfuncai-release-refs-") as directory:
        root = Path(directory)
        remote, source, checkout = (
            root / name for name in ("remote", "source", "checkout")
        )

        def git(*args: str, cwd: Path = root) -> str:
            return subprocess.check_output(
                ["git", *args], cwd=cwd, text=True, stderr=subprocess.DEVNULL
            ).strip()

        git("init", "--bare", "--initial-branch", branch, str(remote))
        git("init", "--initial-branch", branch, str(source))
        git("config", "user.name", "Release protocol test", cwd=source)
        git("config", "user.email", "release-test@example.invalid", cwd=source)
        (source / "pyproject.toml").write_text(f'[project]\nversion = "{version}"\n')
        git("add", "pyproject.toml", cwd=source)
        git("commit", "-m", "Release fixture", cwd=source)
        expected = git("rev-parse", "HEAD", cwd=source)
        tag = "v" + version
        if kind == "unreachable":
            git("switch", "-c", "outside", cwd=source)
            (source / "outside.txt").write_text("Not on the release branch.")
            git("add", "outside.txt", cwd=source)
            git("commit", "-m", "Outside branch", cwd=source)
        if kind == "lightweight":
            git("tag", tag, cwd=source)
        else:
            git("tag", "-a", tag, "-m", "Annotated release fixture", cwd=source)
        git("remote", "add", "origin", str(remote), cwd=source)
        git("push", "origin", branch, "refs/tags/" + tag, cwd=source)
        git("clone", str(remote), str(checkout))
        # Reproduce checkout's local tag peeling without modifying the remote tag.
        peeled = git("rev-parse", tag + "^{commit}", cwd=checkout)
        git("update-ref", "refs/tags/" + tag, peeled, cwd=checkout)
        output = root / "outputs"
        environment = {
            **os.environ,
            "RELEASE_TAG": tag,
            "GITHUB_OUTPUT": output.as_posix(),
        }
        result = subprocess.run(
            [bash, "-e", "-o", "pipefail", "-c", script],
            cwd=checkout,
            env=environment,
            capture_output=True,
            text=True,
        )
        if kind == "unreachable":
            if result.returncode == 0:
                raise AssertionError(
                    "Release accepted a tag outside its required branch."
                )
        elif result.returncode or output.read_text().strip() != "sha=" + expected:
            raise AssertionError(result.stdout + result.stderr)
        print(f"Verified {workflow.name}: {kind}", flush=True)


def main() -> None:
    root = Path(__file__).resolve().parents[1] / ".github/workflows"
    for workflow, branch, version in [
        ("release.yml", "main", "1.2.3"),
        ("prerelease.yml", "preview", "1.2.3rc1"),
    ]:
        for kind in ("annotated", "lightweight", "unreachable"):
            check(root / workflow, branch, version, kind)


if __name__ == "__main__":
    main()
