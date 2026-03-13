# PyLazy

PyLazy is a Python framework for **lazy-evaluated, LLM-generated functions**.

Instead of writing a function body yourself, you describe the behavior in a string and let an LLM generate the implementation. PyLazy returns a normal Python callable, and can **cache** the generated code so future runs are repeatable and fast.

> Status: early concept / WIP. APIs below are a proposed direction and may change.

---

## Why PyLazy?

Sometimes you know *what* you want a function to do, but you don’t want to hand-write the implementation yet (or you want an LLM to do it for you). PyLazy aims to make this feel like a first-class Python workflow:

- **Define behavior in plain English**
- **Get back a real Python callable**
- **Generate at runtime** (lazy) and **cache** results
- Optionally **prebuild** generated code for more deterministic runs

---

## Core Idea

### A) Create a function from a prompt (primary API)

```python
from pylazy import connect, createFunction

connect("openai", api_key="...")  # provider-agnostic in design

greet = createFunction(
    "Greet the user politely by name.",
    signature="(name: str) -> str",
)

print(greet("Alice"))
```

### What happens under the hood (conceptually)

1. PyLazy builds a prompt from:
   - your description
   - an optional type signature
   - framework defaults (style, constraints, safety rules)
2. A configured LLM provider generates Python source code for the function.
3. PyLazy validates the generated code (e.g., AST checks), compiles it, and returns a callable.
4. PyLazy caches the generated source (and/or bytecode) keyed by prompt + signature + settings.

---

## Non-Goals

PyLazy is not trying to:
- be a fully autonomous agent framework
- replace unit tests and code review for production-critical code
- execute arbitrary untrusted code without sandboxing

---

## Safety Notes (Important)

LLM-generated code is still code.

If you `exec()` code produced by a model, you must assume it could be unsafe unless you add defenses such as:
- AST-based allow/deny lists
- restricted builtins / restricted globals
- subprocess isolation with resource limits
- containerization (Docker/gVisor) for higher assurance
- no network / no filesystem access by default

PyLazy intends to support a “safer-by-default” posture, but treat this project as experimental until hardened.

---

## Roadmap (Proposed)

- [ ] Provider abstraction (`connect()`):
  - [ ] OpenAI
  - [ ] Local models (Ollama / llama.cpp)
  - [ ] Others (Gemini/Claude/Copilot) as adapters
- [ ] `createFunction(prompt, signature=..., cache=..., mode=...)`
- [ ] Disk cache with versioning and invalidation
- [ ] Validation layer (AST checks + signature checks)
- [ ] Optional prebuild step:
  - `pylazy build` to materialize generated functions ahead of runtime
- [ ] Minimal examples + tests

---

## License

Apache-2.0

---

## Contributing

This repo is currently a sketch/early build. If you want to contribute, open an issue with:
- the API you wish existed
- a concrete example prompt
- expected input/output types
- any safety constraints

---

## Disclaimer

PyLazy can generate and execute code. Use responsibly. Do not run generated code against secrets or production environments without strong sandboxing and review.
