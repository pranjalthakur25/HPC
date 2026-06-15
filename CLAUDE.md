# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

`hpc-provenance` is a SLSA-inspired provenance generation, signing, and verification
system for jobs run on HPC clusters (Slurm initially). It collects git, Slurm job, and
artifact metadata, assembles it into a signed in-toto Statement carrying a SLSA
Provenance v1 predicate, wraps it in a DSSE envelope, and supports later verification
against a policy. See `README.md` for usage/CLI walkthroughs and `ARCHITECTURE.md` for
the full design (class/sequence/data-flow diagrams and extension strategy) — read
`ARCHITECTURE.md` before making structural changes.

## Development commands

```bash
pip install -e ".[dev]"   # install package + dev deps (pytest, mypy, ruff)

pytest                     # run the full test suite
pytest tests/unit/domain/test_dsse.py          # run one test file
pytest tests/unit/domain/test_dsse.py::test_name  # run one test
pytest -k "slurm"          # run tests matching a name pattern

ruff check .               # lint
mypy                        # type-check (strict mode, see [tool.mypy] in pyproject.toml)
```

CLI entry point: `hpc-provenance` (Typer app, `src/hpc_provenance/presentation/cli/app.py`).
Key command groups: `generate run`, `sign run`, `verify attestation`, `keys generate`,
`slurm prologue` / `slurm epilogue`. `verify run` (catalog-based) is stubbed
(`NotImplementedError`).

## Architecture

Clean Architecture / Ports & Adapters with a strict Dependency Rule — source
dependencies point only **inward**:

```
presentation (Typer CLI) -> config (Settings + Container) -> application (use cases, DTOs)
                                                            -> domain (models, ports/Protocols)
infrastructure (adapters: Git, Slurm, DSSE, filesystem repos) -> implements domain ports
```

- **`domain/`** — entities, value objects, enums, exceptions, and **ports** as
  `typing.Protocol` (`@runtime_checkable`). Zero third-party dependencies (stdlib only:
  dataclasses, enum, typing). Fully unit-testable without mocks.
- **`application/`** — use cases (`GenerateProvenanceUseCase`, `SignProvenanceUseCase`,
  `VerifyProvenanceUseCase`) and the `SlurmProvenanceService` (composes generate+sign for
  the prologue/epilogue flow). Depends only on domain ports — never on concrete adapters.
  DTOs live in `application/dto/`.
- **`infrastructure/`** — concrete adapters implementing domain ports: `GitPythonMetadataCollector`,
  `SlurmEnvMetadataCollector` (env-var based, for use *inside* a running job) /
  `SlurmCliMetadataCollector` (`sacct`/`scontrol`, for post-hoc queries),
  `FilesystemArtifactCollector`, `SLSAv1PredicateBuilder`, `InTotoV1StatementBuilder`,
  `DsseSigner`/`DsseVerifier`, `RSAPayloadSigner`/`ECDSAPayloadSigner`,
  `FilesystemProvenanceRepository`, `LocalFileKeyRepository`.
- **`config/`** — `Settings` (pydantic-settings, env vars prefixed `HPC_PROVENANCE_`, or
  a `.env` file — the *only* place config is read) and `Container` (composition root).
  `Container` is the **only** module that imports both domain ports and concrete
  infrastructure classes; adapters are lazily-cached `@cached_property`s, use cases are
  built fresh via factory methods (`generate_provenance_use_case()`, etc.). Adapter
  selection (e.g. scheduler type) is a `Settings`-driven `match` inside `Container`.
- **`presentation/cli/`** — Typer commands. Each command constructs one `Container` from
  `Settings` and asks it for a use case; no business logic lives here.
- **`shared/`** — `DomainError` hierarchy is in `domain/exceptions.py`; ports raise these
  (never raw library exceptions). `shared/errors.py` has `ApplicationError`/`ConfigurationError`
  for config-level failures. Use cases propagate domain errors to the presentation layer.

### Key flow: generate -> sign -> verify

1. `GenerateProvenanceUseCase` collects git/scheduler/artifact metadata, assembles a
   `ProvenanceContext`, builds a `SLSAProvenancePredicate` (`SLSAv1PredicateBuilder`),
   then wraps it as an `InTotoStatement` (`InTotoV1StatementBuilder`).
2. `SignProvenanceUseCase` wraps the statement in a DSSE envelope (`DsseSigner`, keyed by
   `key_id` via `LocalFileKeyRepository`), and persists it via `FilesystemProvenanceRepository`.
3. `verify attestation` reads a `.dsse` file directly and checks it against a
   `VerificationPolicy` (trusted keys, expected builder/source repo, predicate type) using
   `DsseVerifier` — no provenance catalog needed.

### Slurm prologue/epilogue (the "runtime" flow)

`SlurmProvenanceService` (`application/services/slurm_provenance_service.py`) runs as the
submitting user from inside an `sbatch` script — no scheduler-admin access or
`slurm.conf` changes needed (see `examples/train.sh`):

- `run_prologue` — writes an informational `prologue.json` snapshot (job/git state at
  start). Uses `SlurmEnvMetadataCollector` (reads `SLURM_*` env vars), since `sacct`
  accounting isn't final yet for a running job.
- `run_epilogue` — **independently re-collects** all metadata (does not depend on the
  prologue snapshot), runs `GenerateProvenanceUseCase` + `SignProvenanceUseCase`, and
  writes `provenance.json` + `attestation.dsse`.

`Container.slurm_provenance_service()` always wires `slurm_env_collector`
(`SlurmEnvMetadataCollector`), not `scheduler_collector` (`SlurmCliMetadataCollector`) —
intentional, since prologue/epilogue run *inside* the job.

## Testing patterns

- `tests/fakes/` — hand-written in-memory fakes for every port (`FixedClock`,
  `FakeGitMetadataCollector`, `InMemoryProvenanceRepository`, etc.), type-checked against
  the real `Protocol`s. No mocking framework.
- `tests/conftest.py` — shared fixtures: `sample_git_metadata`, `sample_job_metadata`,
  `sample_provenance_context`, `rsa_key_pair`/`ec_key_pair` (session-scoped real
  `cryptography` keys), `fixed_clock`.
- Presentation-layer tests use Typer's `CliRunner` with a `Container` built from fakes.
- Test tree mirrors `src/hpc_provenance/` layer-by-layer
  (`tests/unit/{domain,application,infrastructure,presentation}/...`).

## Gotchas

- `infrastructure/provenance/` contains both `slsa_predicate_builder.py` /
  `in_toto_statement_builder.py` (wired into `Container`, used by the real flow) **and**
  `slsa_predicate_generator.py` / `in_toto_statement_generator.py` (standalone
  predicate/statement generators with their own JSON-writing helpers, not referenced by
  `Container`). Check `Container` to see which implementation is actually live before
  editing either.
- Extending the system (new schedulers, artifact kinds, predicate versions, signing
  backends, storage backends) should be **additive**: new enum member + new adapter +
  a `Settings`-driven switch in `Container`, without changing domain models/ports/use
  cases — see `ARCHITECTURE.md` §12 ("Future Extension Strategy").
- `ResourceDescriptor.to_dict()`/`from_dict()` omit unset/empty fields to match in-toto's
  JSON shape (no emitted `null`s).
