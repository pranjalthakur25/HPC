# HPC Provenance

A SLSA-inspired provenance generation, signing, and verification system for jobs
executed on HPC clusters (Slurm initially).

It collects **git**, **Slurm job**, and **artifact** metadata for a job, assembles
it into a signed, verifiable **in-toto Statement** carrying a **SLSA Provenance
v1 predicate**, wrapped in a **DSSE envelope** — so you can later prove *what
code*, *what inputs*, and *what cluster job* produced a given output file.

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for the full design (layer
responsibilities, class/sequence/data-flow diagrams, and the extension
strategy).

## What's implemented

- `generate run` — collect git/Slurm/artifact metadata and emit an in-toto
  statement with a SLSA provenance predicate.
- `sign run` — sign a statement into a DSSE envelope and store it.
- `verify attestation` — verify a standalone `.dsse` file against a policy
  (trusted keys, expected builder, expected source repo, predicate type).
- `keys generate` — generate an RSA or ECDSA signing key pair.
- `slurm prologue` / `slurm epilogue` — drop-in hooks for `sbatch` scripts
  that snapshot job state at the start and generate + sign provenance at the
  end (see [`examples/train.sh`](./examples/train.sh)).

> `verify run` (catalog/record-id based verification) is not yet implemented —
> use `verify attestation` instead, which reads a `.dsse` file directly.

## Requirements

- Python 3.12+

## Installation

```bash
git clone <this-repo>
cd HPC_AI_BOMs
pip install -e .
```

For development (tests, linting, type-checking):

```bash
pip install -e ".[dev]"
```

This installs the `hpc-provenance` CLI.

## Quick start

These steps generate a key pair, produce a provenance statement for an
example build, sign it, and verify the result. Run them from a directory
that is (or contains) a git repository.

**1. Generate a signing key pair**

```bash
hpc-provenance keys generate cluster-key-1 --algorithm ecdsa --keys-dir keys
```

This writes `keys/cluster-key-1.private.pem` and `keys/cluster-key-1.public.pem`.

**2. Generate a provenance statement**

```bash
hpc-provenance generate run \
  --builder-id "https://example.org/hpc-provenance/builder/v1" \
  --git-repo . \
  --material train.py \
  --product out/model.safetensors \
  --output provenance/statement.json
```

- `--product` (repeatable, required) — output artifact(s) the statement is *about*.
- `--material` (repeatable) — input artifact(s) used to produce the product(s).
- `--git-repo` — git repository recorded as source metadata.
- `--job-id` — Slurm job id (defaults to `$SLURM_JOB_ID` if set).

**3. Sign the statement**

```bash
hpc-provenance sign run provenance/statement.json \
  --key-id cluster-key-1 \
  --output provenance/attestation.dsse
```

This wraps the statement in a DSSE envelope, signs it with `cluster-key-1`,
saves it to the configured provenance repository, and prints a record id.

**4. Verify the attestation**

```bash
hpc-provenance verify attestation provenance/attestation.dsse \
  --trusted-key-id cluster-key-1
```

Prints `VALID` (exit 0) or `INVALID` plus a list of issues (exit 1). You can
additionally pin `--expected-builder-id`, `--expected-source-repo`, and
`--required-predicate-type` to enforce policy.

## Slurm integration (`sbatch` prologue/epilogue)

For real jobs, use the `slurm` command group from your `sbatch` script — no
`slurm.conf` changes or scheduler-admin access required. Both commands run as
the submitting user and read job info from `SLURM_*` environment variables.

```bash
# --- Prologue: snapshot job/git state at the start of the job ---
hpc-provenance slurm prologue \
  --git-repo "$SLURM_SUBMIT_DIR" \
  --output-dir "$SLURM_SUBMIT_DIR/out"

# --- Job: the actual workload ---
python train.py --epochs 5 --output "$SLURM_SUBMIT_DIR/out/model.safetensors"

# --- Epilogue: generate and sign provenance for this run ---
hpc-provenance slurm epilogue \
  --product "$SLURM_SUBMIT_DIR/out/model.safetensors" \
  --material "$SLURM_SUBMIT_DIR/train.py" \
  --git-repo "$SLURM_SUBMIT_DIR" \
  --key-id cluster-key-1 \
  --output-dir "$SLURM_SUBMIT_DIR/out"
```

`slurm epilogue` writes `provenance.json` and `attestation.dsse` to
`--output-dir`. See [`examples/train.sh`](./examples/train.sh) for a complete,
runnable `sbatch` script.

## Configuration

All settings can be overridden via environment variables prefixed with
`HPC_PROVENANCE_`, or via a `.env` file in the working directory
(see [`config/settings.py`](./src/hpc_provenance/config/settings.py)):

| Environment variable | Default | Description |
|---|---|---|
| `HPC_PROVENANCE_SCHEDULER_TYPE` | `slurm` | Which scheduler metadata collector to use. |
| `HPC_PROVENANCE_BUILDER_ID` | `https://example.org/hpc-provenance/builder/v1` | Default builder identity for generated provenance. |
| `HPC_PROVENANCE_DIGEST_ALGORITHM` | `sha256` | Hash algorithm for artifact digests (`sha256`, `sha512`, `sha1`). |
| `HPC_PROVENANCE_OUTPUT_DIRECTORY` | `./provenance` | Root directory for the provenance repository (signed envelopes/records). |
| `HPC_PROVENANCE_KEYS_DIRECTORY` | `./keys` | Root directory for signing/verification key pairs. |
| `HPC_PROVENANCE_TRUSTED_KEY_IDS` | *(all known keys)* | Optional set of key ids trusted by `verify`. |

## CLI reference

Run `hpc-provenance --help` or `hpc-provenance <group> --help` for full
details on any command.

| Command | Description |
|---|---|
| `hpc-provenance generate run` | Generate an in-toto/SLSA provenance statement. |
| `hpc-provenance sign run` | Sign a statement into a DSSE envelope. |
| `hpc-provenance verify attestation` | Verify a standalone DSSE attestation file. |
| `hpc-provenance keys generate` | Generate an RSA/ECDSA signing key pair. |
| `hpc-provenance slurm prologue` | Write a job-start snapshot (`sbatch` hook). |
| `hpc-provenance slurm epilogue` | Generate + sign provenance for a finished job (`sbatch` hook). |

## Project layout

```
src/hpc_provenance/
├── domain/          # entities, value objects, ports (zero external deps)
├── application/     # use cases and services orchestrating ports
├── infrastructure/  # adapters implementing ports (Git, Slurm, DSSE, storage)
├── presentation/    # CLI entry point (Typer)
├── config/          # settings + dependency-injection composition root
└── shared/          # cross-cutting concerns (errors, logging)
```

See [`ARCHITECTURE.md`](./ARCHITECTURE.md) for layer responsibilities, class
diagrams, sequence diagrams, data-flow diagrams, and the future extension
strategy.

## Development

```bash
pip install -e ".[dev]"
pytest              # run the test suite
ruff check .        # lint
mypy                # type-check
```
