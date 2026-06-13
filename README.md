# HPC Provenance

A SLSA-inspired provenance generation, signing, and verification system for jobs
executed on HPC clusters (Slurm initially).

> **Status: design-only skeleton.** This repository currently contains the
> architecture, folder structure, domain models, and interface (port)
> definitions only. No business logic is implemented yet — see
> [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design.

## What this will do

For a given HPC job (e.g. a Slurm job), the system collects:

- **Git metadata** — commit, branch, dirty state, remote
- **Slurm metadata** — job id, allocation, resource usage, exit status
- **Artifact metadata** — digests of input/output files

...and turns that into a signed, verifiable **in-toto Statement** carrying a
**SLSA Provenance predicate**, wrapped in a **DSSE envelope**.

## Project layout

```
src/hpc_provenance/
├── domain/          # entities, value objects, ports (zero external deps)
├── application/     # use cases orchestrating ports
├── infrastructure/  # adapters implementing ports (Git, Slurm, DSSE, storage)
├── presentation/    # CLI entry point
├── config/          # settings + dependency-injection composition root
└── shared/          # cross-cutting concerns (errors, logging)
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for layer responsibilities, class
diagrams, sequence diagrams, data-flow diagrams, and the future extension
strategy.

## Requirements

- Python 3.12+
- See `pyproject.toml` for intended (not-yet-wired) dependencies.

## Development

```bash
pip install -e ".[dev]"
pytest
```
