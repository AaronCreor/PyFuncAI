# PyFuncAI

[![CI](https://github.com/AaronCreor/PyFuncAI/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/AaronCreor/PyFuncAI/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/pyfuncai)](https://pypi.org/project/PyFuncAI/)
[![Python](https://img.shields.io/pypi/pyversions/pyfuncai)](https://pypi.org/project/PyFuncAI/)
[![License](https://img.shields.io/badge/License-Apache--2.0-blue.svg)](https://github.com/AaronCreor/PyFuncAI/blob/main/LICENSE)

Define Python functions with prompts and generate their implementations using a local
Ollama model, OpenAI, or Gemini. Generation can happen on first use or immediately.
Validated source can be cached across runs. There are no runtime package dependencies.

Version **0.1.9** fixes annotated-tag releases, signature evaluation, cache correctness, import restrictions,
provider response handling, and concurrent generation. See the
[changelog](https://github.com/AaronCreor/PyFuncAI/blob/main/CHANGELOG.md).

## Installation

Requires Python **3.10 or newer**. CI tests Python 3.10 through 3.14 on Linux, plus Windows
and macOS configurations.

```bash
python -m pip install --upgrade pyfuncai
```

## Quick start with Ollama

Install and start [Ollama](https://ollama.com/), then pull and check your model:

```bash
ollama pull qwen3.5:latest
ollama list
```

If Ollama is not already serving, run `ollama serve`. The default endpoint is
`http://localhost:11434`; the model name must match a name in `ollama list`.

```python
from pyfuncai import connect, create_function

connect("ollama", model="qwen3.5:latest", timeout=180)

greet = create_function(
    "Return exactly 'Hello, ' followed by name and an exclamation mark.",
    signature="(name: str) -> str",
    function_name="greet",
    mode="eager",
)

print(greet("Alice"))  # Hello, Alice!
print(greet.source)    # Inspect the generated Python source
```

Generated implementations still need behavior tests for your use case.

## Remote providers

Set `OPENAI_API_KEY` or `GEMINI_API_KEY` in your environment. Select a model available
to your account. Keys are read from the environment automatically; avoid committing
credentials or placing secrets in prompts.

```python
import os
from pyfuncai import connect, create_function

connect("openai", model=os.environ["OPENAI_MODEL"])
# Alternatively:
# connect("gemini", model=os.environ["GEMINI_MODEL"])

slugify = create_function(
    "Lowercase text, replace runs of non-ASCII-alphanumeric characters with '-', "
    "and strip leading and trailing '-'.",
    signature="(text: str) -> str",
    function_name="slugify",
)
print(slugify("Hello, World!"))
```

OpenAI uses the Responses API; Gemini uses `generateContent`. Sampling options vary
by model. Leave `temperature=None` when a model does not support that setting.

## API reference

### `connect(provider, **config) -> BaseProvider`

Configures the process-wide default provider and cache for future functions. Existing
functions retain their provider and cache. Supported provider names are `ollama`,
`openai`, and `gemini`.

| Configuration | Default | Meaning |
| --- | --- | --- |
| `model` | Required | Provider model identifier |
| `timeout` | `60.0` | Positive socket timeout in seconds per HTTP attempt |
| `cache_dir` | OS cache directory | Default source cache for subsequent functions |
| `base_url` | Provider endpoint | Ollama: `http://localhost:11434`; OpenAI: `https://api.openai.com/v1`; Gemini: `https://generativelanguage.googleapis.com/v1beta` |
| `api_key` | Environment variable | OpenAI/Gemini only; explicit key overrides the environment |
| `max_retries` | `0` | Additional transport attempts, from 0 to 5 |
| `retry_backoff` | `0.5` | Nonnegative retry delay in seconds, doubled each retry and capped at 10 seconds |

Retries are opt-in. Timeouts, connection errors, HTTP 429, and HTTP 500/502/503/504
can be retried; authentication errors, invalid JSON, and invalid generated code are
not retried. A retry can cause another billable generation. The socket timeout is
not a total generation or execution deadline.

For multiple models or concurrent applications, create provider instances explicitly
and pass both `provider=` and `cache_dir=` instead of changing global defaults:

```python
from pyfuncai import OllamaProvider, create_function

provider = OllamaProvider(model="qwen3.5:latest", timeout=180, max_retries=1)
add = create_function(
    "Return the sum of a and b.",
    signature="(a: int, b: int) -> int",
    function_name="add",
    provider=provider,
    cache_dir=".pyfuncai-cache",
)
```

Provider constructors accept the corresponding provider configuration except
`cache_dir`. `BaseProvider` is available from `pyfuncai.providers` for custom adapters.

### `create_function(prompt, *, signature, ...) -> GeneratedFunction`

| Argument | Default | Meaning |
| --- | --- | --- |
| `prompt` | Required | Nonempty behavior specification |
| `signature` | Required | Python parameter and return annotation text, such as `(x: int = 1) -> int` |
| `function_name` | Derived from prompt | Normalized Python name; keywords are prefixed with `generated_` |
| `mode` | `"lazy"` | `lazy` builds on first call; `eager` builds during creation |
| `cache` | `True` | Read and write the disk source cache |
| `provider` | Last `connect()` provider | Explicit provider instance |
| `cache_dir` | Last `connect()` cache or OS default | Per-function cache override |
| `system_prompt` | `None` | Additional provider instruction |
| `temperature` | `None` | Finite nonnegative sampling value, if the model supports it |
| `max_output_tokens` | `None` | Positive integer response token limit |
| `allow_modules` | Default modules below | `None` uses defaults; `[]` disables all imports |

`createFunction(...)` remains a compatibility alias.

Signatures support positional-only, keyword-only, variadic parameters, literal
defaults, and inert type annotations. Defaults may be literals such as `None`,
`1`, `"text"`, lists, tuples, sets, and dictionaries. Function calls, default
factories, variable references in defaults, executable annotations, decorators,
and injected function bodies are rejected. Signatures are limited to 4096 characters.
Signature metadata is constructed without executing Python code. Annotations are
stored as strings and do not enforce argument or return types at runtime.

### Generated function methods

| Member | Behavior |
| --- | --- |
| `fn(*args, **kwargs)` | Build if necessary, then call the generated implementation |
| `fn.build(force=False)` | Return the compiled callable; `force=True` requests regeneration |
| `fn.source` | Return in-memory or cached source, or `None`; does not contact the provider |
| `fn.is_built` | Whether this instance has a compiled callable |
| `fn.cache_key` | Deterministic key for this generation request |

Concurrent first calls to the same instance serialize generation and reuse one
successful build. Separate instances or processes can still generate independently.
Function execution itself is not serialized. The runtime registry uses weak
references; the CLI holds script-created functions only during a build.

### Exceptions

All library exceptions derive from `PyFuncAIError` and are exported from `pyfuncai`:

| Exception | Typical cause |
| --- | --- |
| `ConfigurationError` | Missing provider/key, invalid signature, invalid cache key, or invalid configuration |
| `ProviderError` | Connection failure, timeout, HTTP failure, malformed JSON, missing text, or incomplete output |
| `GenerationError` | Empty generated source |
| `ValidationError` | Generated code violates the requested signature or execution policy |

Filesystem failures can raise `OSError`. Exceptions raised by the generated function
itself propagate normally, for example `ValueError` for invalid input. Provider
errors omit raw HTTP response bodies to avoid disclosing credentials or prompt data.

## Cache behavior and migration

Cache keys include the prompt, signature, normalized name, provider identity
(provider/model/endpoint), mode, allowed modules, system prompt, temperature, output
token limit, and generation-template version. Credentials and retry settings are
not part of cache identity. Changing any generation input creates a different entry.
Version 0.1.9 uses new keys; older entries remain on disk but are not automatically reused.
Model tags can change upstream; use `fn.build(force=True)` after replacing a model
under the same tag.

Default cache directories:

- Windows: `%LOCALAPPDATA%\PyFuncAI\cache` (with an AppData fallback).
- Other systems: `$XDG_CACHE_HOME/pyfuncai`, or `~/.cache/pyfuncai` when unset.

Cache entries contain plaintext prompts, generated source, and provider identity.
Keep the directory private and avoid including secrets in prompts. Restricting
imports does not protect a writable cache from another local user.

Only successfully validated and compiled code is written, using atomic file
replacement. Truncated, malformed, and incompatible entries are treated as misses.
Cached code is revalidated before execution. Invalid cached source is evicted and
raises `ValidationError`; the next build can regenerate, or use `build(force=True)`.
A failed forced refresh preserves the previously working in-memory callable.

Cache keys must contain 1 to 128 ASCII letters, digits, underscores, or hyphens.
Generated keys are SHA-256 hashes. Paths and links resolving outside the cache root
are rejected. Cache commands skip entries with unsafe names or external links.

## Command line

```bash
pyfuncai --version
pyfuncai build path/to/script.py
pyfuncai build --force path/to/script.py
pyfuncai cache path
pyfuncai cache list
pyfuncai cache remove FULL_CACHE_KEY
pyfuncai cache clear
pyfuncai cache --cache-dir .pyfuncai-cache list
```

`pyfuncai --version` prints `pyfuncai <version>` using the installed package version
and exits successfully without configuring a provider.

For machine-readable cache metadata, use:

```bash
pyfuncai cache list --json
pyfuncai cache --cache-dir .pyfuncai-cache list --json
```

The JSON array contains exactly `cache_key`, `function_name`, `mode`, and
`created_at` for each entry, in the same newest-first order as the plain listing.
An empty cache prints `[]`. Prompts, generated source, and provider configuration
are omitted. Plain listings retain their existing output.

`pyfuncai build` **executes the entire target script**, including its `__main__`
block and other side effects, then builds the functions it created. Use a dedicated
script containing definitions when prebuilding. A script can create eager functions
before `--force` rebuilds them. Cache commands use the OS default unless `--cache-dir`
is supplied; they do not load settings from an application's `connect()` call.
Library and filesystem failures print an error and return a nonzero exit status.

## Execution policy and safety

PyFuncAI checks the AST, requires an exact requested signature, restricts imports,
and supplies a limited builtin namespace. Generated source may contain one top-level
function, allowed imports, and an optional module docstring. Async functions,
decorators, relative imports, blocked builtins, and dunder attribute access are rejected.

Default allowed module roots:
`collections`, `csv`, `datetime`, `decimal`, `fractions`, `functools`, `itertools`,
`json`, `math`, `operator`, `re`, `statistics`, `string`.
An allowed root also permits its submodules. Custom `allow_modules` replaces this
list; adding a module expands what generated code can access.

Available builtins (the same list is sent to the model):

`ArithmeticError`, `AssertionError`, `Exception`, `IndexError`, `KeyError`, `LookupError`, `NotImplementedError`, `OverflowError`, `RuntimeError`, `StopIteration`, `TypeError`, `ValueError`, `ZeroDivisionError`, `abs`, `all`, `any`, `bool`, `bytearray`, `bytes`, `chr`, `dict`, `divmod`, `enumerate`, `filter`, `float`, `frozenset`, `hex`, `int`, `isinstance`, `iter`, `len`, `list`, `map`, `max`, `min`, `next`, `ord`, `pow`, `range`, `repr`, `reversed`, `round`, `set`, `slice`, `sorted`, `str`, `sum`, `tuple`, `zip`.

Import statements additionally use a restricted internal import hook. File access,
network access, shell commands, `eval`, and `exec` are outside the intended policy.
These checks are **not a hardened sandbox**: code runs in your Python process,
can consume CPU/memory, can mutate supplied objects, and has no execution timeout.
Use separate, appropriately restricted processes for untrusted workloads. Validation
checks source shape and policy, not behavioral correctness. Test generated behavior
before relying on it.

For vulnerability reporting, see the
[security policy](https://github.com/AaronCreor/PyFuncAI/blob/main/SECURITY.md).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Cannot connect to Ollama | Confirm Ollama is running and `base_url` is reachable |
| Model not found | Run `ollama list`, then pull or select the exact model name |
| Generation times out | Increase `timeout`; local model loading can be slow |
| Incomplete output | Increase `max_output_tokens` or use the model default |
| Signature/validation error | Use literal defaults, supported modules/builtins, and a precise prompt; inspect available source and retry with `build(force=True)` |
| Cache behavior seems stale | Force regeneration or remove the matching cache key |
| Invalid distribution metadata locally | Upgrade development tooling in your virtual environment, including Twine and packaging |

## Development and testing

Use a virtual environment, then install the checkout:

```bash
python -m pip install -e ".[dev]"
python -m black --check src tests scripts example.py
python -m pytest --cov=pyfuncai --cov-report=term-missing
python scripts/check_release_refs.py
python -m build
python -m twine check --strict dist/*
python scripts/check_distribution.py dist/*
```

The offline suite mocks provider HTTP calls and enforces at least 85% coverage.
Tests import the installed package; they do not inject the repository's `src` path.
The distribution check installs both artifacts into an isolated environment and
runs the offline suite outside the checkout. On PowerShell, pass artifact paths
explicitly:

```powershell
python scripts/check_distribution.py dist/pyfuncai-0.1.9-py3-none-any.whl dist/pyfuncai-0.1.9.tar.gz
```

Run optional live Ollama tests:

```bash
PYFUNCAI_RUN_OLLAMA_TESTS=1 python -m pytest tests/test_ollama_live.py -q
```

PowerShell:

```powershell
$env:PYFUNCAI_RUN_OLLAMA_TESTS = "1"
$env:PYFUNCAI_OLLAMA_MODEL = "qwen3.5:latest"
$env:PYFUNCAI_OLLAMA_BASE_URL = "http://localhost:11434"
$env:PYFUNCAI_OLLAMA_TIMEOUT = "180"
python -m pytest tests/test_ollama_live.py -q
Remove-Item Env:PYFUNCAI_RUN_OLLAMA_TESTS
```

Only `PYFUNCAI_RUN_OLLAMA_TESTS=1` is required to opt in. The other values shown are
the defaults. Live tests cover deterministic greetings, arithmetic, JSON parsing,
literal defaults, allowed imports, and disk cache reuse. Remote providers are tested
with mocked responses, without billable live requests.

## Contributing and releasing

The repository uses `dev` for integration, `preview` for release candidates, and
`main` for stable releases. See
[contributing instructions](https://github.com/AaronCreor/PyFuncAI/blob/main/CONTRIBUTING.md).

Every implementation change must include regression tests, an updated README,
and a changelog entry. The README is embedded into wheel/sdist metadata and becomes
the PyPI description; editing GitHub alone does not update PyPI.

Stable release procedure:

1. Update `pyproject.toml` version, README, and `CHANGELOG.md` together.
2. Open a pull request into `main`; wait for all CI checks to pass and review the diff.
3. Merge, fetch the resulting `main`, then create an annotated matching tag.
4. Push the tag to run `release.yml`. For this release the tag is `v0.1.9`.
5. Verify the GitHub release, PyPI version/description, and a clean PyPI installation.

```bash
git switch main
git pull --ff-only
git tag -a v0.1.9 -m "Release PyFuncAI 0.1.9"
git push origin v0.1.9
```

Do not reuse an existing release tag or package version. `release.yml` verifies the
tag's version and ancestry on `main` using a separate local verification ref, runs the complete test matrix on the exact
commit, and tests installed artifacts. The same verified artifacts are published
through PyPI Trusted Publishing, then attached to a GitHub release only after PyPI
publication succeeds. The GitHub `pypi` environment and PyPI trusted publisher must
continue to authorize `AaronCreor/PyFuncAI`, workflow `release.yml`.

`prerelease.yml` applies the same checks to `preview` tags such as `v0.1.10rc1`, then
creates a GitHub prerelease. Preview artifacts are not published to PyPI. CI and both
release workflows share `.github/workflows/checks.yml`.

## Contributors

Thanks to [29rdx](https://github.com/29rdx) for
[JSON cache listings](https://github.com/AaronCreor/PyFuncAI/pull/6) and
[ShahadatTest](https://github.com/ShahadatTest) for submitting
[the version command](https://github.com/AaronCreor/PyFuncAI/pull/7).
See the [full contributor history](https://github.com/AaronCreor/PyFuncAI/graphs/contributors).

## License

Apache-2.0. See [LICENSE](https://github.com/AaronCreor/PyFuncAI/blob/main/LICENSE).
