# Contributing to PyFuncAI

Use Python 3.10 or newer and a virtual environment. Install the checkout with
`python -m pip install -e ".[dev]"`. Keep runtime dependencies minimal.

Start a topic branch from the intended target (`dev` for integration, `preview` for
release candidates, or `main` for a stable maintenance release). Include regression
coverage for each behavior change. Provider unit tests must mock HTTP calls rather
than require API credentials; live Ollama tests must remain opt-in.

Update README.md and CHANGELOG.md for every implementation change. Describe public
API behavior, defaults, failures, and migration requirements. README.md is the PyPI
long description, so documentation and code must ship in the same versioned release.

Before submitting a pull request:

```bash
python -m black --check src tests scripts example.py
python -m pytest --cov=pyfuncai --cov-report=term-missing
python scripts/check_release_refs.py
python -m build
python -m twine check --strict dist/*
python scripts/check_distribution.py dist/*
```

Pass explicit distribution paths on PowerShell. Maintain at least 85% coverage;
add meaningful failure-path tests rather than assertions that mirror implementation.
Run the optional local Ollama suite when changing prompts, compilation, or provider
behavior. Do not include credentials, local cache contents, or build artifacts in commits.

Open a pull request with the problem, resulting behavior, tests, and compatibility
notes. Wait for CI, inspect the diff, and obtain maintainer review when another
maintainer is available. Do not bypass configured branch or environment protections.
A sole maintainer can merge a fully checked maintenance change if repository policy permits.

To receive GitHub contributor credit, author commits with an email linked to your
GitHub account (your GitHub-provided noreply address also works). Keep your own
authorship when using coding assistants. Maintainers should preserve contributor
commits when promoting `dev` through `preview` to the default branch, `main`.
GitHub's contributors graph uses commits on the default branch and may take time
to refresh. README acknowledgments can also credit PR submitters whose commits
were authored under another account.

For a release, update the package version and documentation together. After merging,
create an annotated version tag from the target branch. Follow the release procedure
in README.md and verify both GitHub and PyPI. Never overwrite published versions or tags.
