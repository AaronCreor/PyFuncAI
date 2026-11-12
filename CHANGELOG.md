# Changelog

## Unreleased

### Added

- `pyfuncai cache show FULL_CACHE_KEY` prints the cached Python source for one
  entry to stdout, reusing `DiskCache.get()`. Missing, malformed, incompatible,
  or invalid-key entries are reported on stderr with a nonzero exit status.
  The `--cache-dir` option applies as with the other cache commands ([PR #26](https://github.com/AaronCreor/PyFuncAI/pull/26)).

## 0.1.11 - 2026-11-10

### Documentation

- Add a table of contents linking to the README's main sections, including the
  documentation published on PyPI ([PR #12](https://github.com/AaronCreor/PyFuncAI/pull/12),
  contributed by [29rdx](https://github.com/29rdx)).
- Update release examples and contributor acknowledgments for the documentation release.

## 0.1.10 - 2026-11-01

### Added

- `pyfuncai --version` prints the installed package version ([PR #7](https://github.com/AaronCreor/PyFuncAI/pull/7), submitted by
  [ShahadatTest](https://github.com/ShahadatTest)).
- `pyfuncai cache list --json` outputs an ordered array of cache keys, function
  names, modes, and creation timestamps. Empty caches produce `[]`; prompts,
  generated source, and provider configuration are omitted ([PR #6](https://github.com/AaronCreor/PyFuncAI/pull/6),
  [29rdx](https://github.com/29rdx)).

### Documentation

- Document both CLI additions in the README and PyPI description, and acknowledge
  their contributors with links to the original pull requests.
- Explain how contributors retain GitHub authorship credit when using coding
  assistants and when changes are promoted through the repository branches.

## 0.1.9 - 2026-10-31

- Ship all audited runtime fixes and documentation prepared for 0.1.8.
- Verify annotated release tags through a separate local ref so checkout cannot
  cause a tag-clobber rejection. Preserve the existing v0.1.8 tag; it was not published to PyPI.
- Add integration checks that execute the actual stable/prerelease verification
  steps against temporary Git repositories with annotated and lightweight tags,
  including rejection of tags outside the required branch.
- Update README/PyPI metadata, version examples, and security guidance to 0.1.9.

## 0.1.8 - 2026-10-31 (unpublished tag)

### Fixed

- Parse signature metadata without executing defaults or annotations; reject injected
  bodies, executable defaults, decorators, and invalid parameter layouts.
- Include generation settings and template version in cache keys; old keys are not reused.
- Cache source only after validation and compilation; evict invalid cached source.
- Honor empty import allowlists and provide common builtin exception types.
- Constrain cache paths, reject external symlinks, tolerate corrupt entries, and replace
  cache files atomically with temporary-file cleanup on failure.
- Serialize builds of the same function and avoid retaining unused functions in the registry.
- Normalize HTTP, timeout, JSON, and encoding errors into ProviderError; combine multipart
  output and reject incomplete generations. Send Gemini credentials in a header.
- Report CLI library/filesystem errors without a traceback.

### Added

- Optional bounded provider retries with exponential backoff, disabled by default.
- Regression and provider protocol tests, expanded live Qwen/Ollama checks, and an
  85% coverage requirement.
- Shared CI/release checks across Python 3.10 through 3.14, Linux, Windows, and macOS; test
  installed wheel and source distributions outside the checkout before publication.
- API, migration, concurrency, execution-policy, troubleshooting, contribution,
  security-reporting, and release documentation.

### Release process

- Bump package version to 0.1.8; use README.md as the GitHub and PyPI documentation source.
- Test the exact tagged commit and publish the verified artifacts to PyPI before
  creating the GitHub release. Prereleases remain GitHub-only.
- Require compatible metadata tooling (Twine 7 and packaging 26.3 or newer).

## 0.1.7 and earlier

See the historical [GitHub releases](https://github.com/AaronCreor/PyFuncAI/releases).
