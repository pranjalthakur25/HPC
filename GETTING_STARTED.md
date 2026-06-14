# Getting Started — What This Does, and How to Run/Demo It

This doc answers two questions:

1. **What does the implemented workflow actually do, in plain language?**
2. **How do I run it myself and show it to other people?**

For the deeper "why is the code organized this way" tour, see
[`EXPLAINED.md`](./EXPLAINED.md). For full technical diagrams, see
[`ARCHITECTURE.md`](./ARCHITECTURE.md).

---

## 1. The 30-second explanation

When you run a job on an HPC cluster (e.g. training an AI model with Slurm),
you get output files at the end — a model checkpoint, a dataset, a binary.

**The question this tool answers: "Where did this file actually come from?"**

- Which exact version of the code (git commit) produced it?
- Which Slurm job ran it — on what nodes, what partition, as which user?
- What input files went into it?
- Has the file (or this answer) been tampered with since?

This tool automatically generates a **signed receipt** for every job that
answers all of these questions, using three well-known open standards:
**SLSA** (the receipt's content), **in-toto** (the receipt's envelope/shape),
and **DSSE** (the tamper-proof seal/signature on the envelope).

Analogy: it's a **shipping label + tamper-evident seal** for the output of a
compute job.

---

## 2. The workflow, step by step

The whole thing is built around **three hooks you add to your normal Slurm
`sbatch` script**, plus a **fourth command anyone can run later**:

```
 ┌─────────────┐     ┌────────────────────┐     ┌──────────────┐     ┌────────────────┐
 │  PROLOGUE   │ ──▶ │   YOUR ACTUAL JOB   │ ──▶ │   EPILOGUE   │ ──▶ │  VERIFY (later) │
 │ snapshot of │     │ (e.g. train.py —    │     │ build + sign │     │ by anyone with  │
 │ job & git   │     │  produces files)    │     │ the "receipt"│     │ the public key  │
 │ state       │     │                     │     │              │     │                 │
 └─────────────┘     └────────────────────┘     └──────────────┘     └────────────────┘
  prologue.json         out/model.bin            provenance.json       VALID / INVALID
                                                   attestation.dsse
```

### Step 1 — Prologue (start of job)

```bash
hpc-provenance slurm prologue --git-repo . --output-dir out
```

Reads Slurm's environment variables (`SLURM_JOB_ID`, `SLURM_JOB_USER`,
`SLURM_JOB_NODELIST`, `SLURM_JOB_PARTITION`, `SLURM_SUBMIT_DIR`) plus the
current git commit/branch, and writes a `prologue.json` snapshot.

In case dummy of no slurm job set env:

$env:SLURM_JOB_ID="123456"
$env:SLURM_JOB_USER="pranjal"
$env:SLURM_JOB_NODELIST="node01"
$env:SLURM_JOB_PARTITION="gpu"
$env:SLURM_SUBMIT_DIR=(Get-Location).Path

hpc-provenance slurm prologue --git-repo . --output-dir out
This is **just informational** — a "this is what the world looked like when
the job started" log. The epilogue (step 3) re-collects everything itself, so
nothing downstream depends on this file.

### Step 2 — Your actual job

Your normal command — completely unchanged:

```bash
python train.py --epochs 5 --output out/model.safetensors
```

### Step 3 — Epilogue (end of job)

```bash
hpc-provenance slurm epilogue \
  --product out/model.safetensors \
  --material train.py \
  --git-repo . \
  --key-id cluster-key-1 \
  --output-dir out
```

This is where the real work happens:

1. Re-collects job info (Slurm), source info (git), and computes a SHA-256
   checksum of every `--product` (output) and `--material` (input) file.
2. Assembles all of that into a **SLSA provenance predicate** — "this output
   was built from these inputs, by this job, on these nodes, starting/ending
   at these times" — and wraps it in an **in-toto Statement** that names the
   output file(s) as its subject. This is written to `provenance.json`
   (human-readable, **not yet signed**).
3. Signs that statement with your private key, producing a **DSSE envelope**
   — `attestation.dsse`. This is the tamper-proof, shareable receipt.
4. Also saves a copy of the signed envelope into a local "catalog"
   (`HPC_PROVENANCE_OUTPUT_DIRECTORY`, default `./provenance/`) under a
   random record id, for later lookup.

### Step 4 — Verify (any time later, by anyone)

```bash
hpc-provenance verify attestation out/attestation.dsse --trusted-key-id cluster-key-1
```

Anyone with the **public** key can check:

- Is the signature genuine (was it really signed by `cluster-key-1`, and has
  the content not changed since)?
- (Optionally) does it match policy — expected builder id, expected source
  repo, expected predicate type?

Prints `VALID (verified keys: ...)` and exits `0`, or prints each problem and
exits non-zero.

---

## 3. What's actually inside the receipt?

Here's a real `provenance.json` produced by the steps above (trimmed):

```json
{
  "_type": "https://in-toto.io/Statement/v1",
  "subject": [
    {
      "name": "model.bin",
      "digest": { "sha256": "4e45d688...c65920" },
      "annotations": { "sizeBytes": 19 }
    }
  ],
  "predicateType": "https://slsa.dev/provenance/v1",
  "predicate": {
    "buildDefinition": {
      "buildType": "https://hpc-provenance.dev/build-types/slurm-job/v1",
      "internalParameters": {
        "scheduler": "slurm",
        "jobId": "slurm:123456",
        "user": "DELL",
        "partition": "gpu",
        "nodeList": ["node01"]
      },
      "resolvedDependencies": [
        { "name": "train.py", "digest": { "sha256": "03e693d9...05824" } },
        { "digest": { "gitCommit": "5e44e388dd58043ef2b3621b3767cf3942bff2c1" } }
      ]
    },
    "runDetails": {
      "builder": { "id": "https://example.org/hpc-provenance/builder/v1" },
      "metadata": { "invocationId": "slurm:123456", "startedOn": "2026-06-13T12:41:22Z" }
    }
  }
}
```

In plain English, this says: *"File `model.bin` (with this exact checksum)
was produced by Slurm job `123456`, run by user `DELL` on node `node01` in
partition `gpu`, using `train.py` (with this checksum) and git commit
`5e44e388...` as inputs."*

`attestation.dsse` wraps the **exact same JSON** plus a cryptographic
signature, so nobody can edit any of those fields afterward without the
signature breaking.

---

## 4. One-time setup

**Requirements:** Python 3.12+

```bash
cd HPC_AI_BOMs
python -m venv .venv

# Windows (PowerShell)
.venv\Scripts\Activate.ps1
# macOS / Linux / Git Bash
source .venv/Scripts/activate

pip install -e ".[dev]"
```

Sanity-check the install:

```bash
hpc-provenance --help
pytest -q          # optional — confirms the whole test suite passes
```

> If `hpc-provenance` isn't on your `PATH` for some reason, you can always
> run it as `python -m hpc_provenance.presentation.cli ...` with
> `PYTHONPATH=src` set — that's what was used to verify every command below.

Generate a signing key pair (one-time, represents "the cluster's identity"):

```bash
hpc-provenance keys generate cluster-key-1 --algorithm ecdsa --keys-dir keys
```

This creates:
- `keys/cluster-key-1.private.pem` — keep this secret, used to **sign**
- `keys/cluster-key-1.public.pem` — share this freely, used to **verify**

---

## 5. Run the full demo (no real Slurm cluster needed)

`slurm prologue`/`slurm epilogue` read Slurm info from environment variables
only — so you can simulate "being inside a Slurm job" just by setting those
variables yourself. This is the easiest way to run and demo the whole flow.

```bash
# --- pretend we're inside Slurm job 123456 ---
export SLURM_JOB_ID=123456
export SLURM_JOB_USER=$(whoami)
export SLURM_JOB_NODELIST=node01
export SLURM_JOB_PARTITION=gpu
export SLURM_SUBMIT_DIR=$PWD
export HPC_PROVENANCE_KEYS_DIRECTORY="$PWD/keys"

# --- Step 1: prologue ---
hpc-provenance slurm prologue --git-repo . --output-dir out

# --- Step 2: the actual job ---
mkdir -p out
python train.py --output out/model.bin     # or: echo "weights" > out/model.bin

# --- Step 3: epilogue (generate + sign) ---
hpc-provenance slurm epilogue \
  --product out/model.bin \
  --material train.py \
  --git-repo . \
  --key-id cluster-key-1 \
  --output-dir out

# --- Step 4: verify ---
hpc-provenance verify attestation out/attestation.dsse --trusted-key-id cluster-key-1
```

**PowerShell equivalent for the environment variables:**

```powershell
$env:SLURM_JOB_ID = "123456"
$env:SLURM_JOB_USER = $env:USERNAME
$env:SLURM_JOB_NODELIST = "node01"
$env:SLURM_JOB_PARTITION = "gpu"
$env:SLURM_SUBMIT_DIR = (Get-Location).Path
$env:HPC_PROVENANCE_KEYS_DIRECTORY = "$($env:SLURM_SUBMIT_DIR)\keys"
```

### Expected output

```
wrote out\prologue.json

wrote out\provenance.json
wrote out\attestation.dsse
record id: 1ed16a12-a8a7-4255-b059-b24b36ec9341

VALID (verified keys: cluster-key-1)
```

### Files you'll end up with

| File | What it is |
|---|---|
| `out/prologue.json` | Informational snapshot taken at job start |
| `out/provenance.json` | The "receipt" content — unsigned in-toto/SLSA statement |
| `out/attestation.dsse` | The **signed** receipt — share this one |
| `provenance/<record-id>.dsse.json` + `.meta.json` | A local catalog copy of every signed receipt |

---

## 6. Run it on a real Slurm cluster

[`examples/train.sh`](./examples/train.sh) is a ready-to-submit `sbatch`
script using exactly the same three commands. No `slurm.conf` changes or
admin access needed — everything runs as the submitting user.

```bash
# one-time setup on the cluster
pip install -e ".[dev]"
hpc-provenance keys generate cluster-key-1 --algorithm ecdsa --keys-dir keys

# submit the job
sbatch examples/train.sh

# after it finishes
hpc-provenance verify attestation out/attestation.dsse --trusted-key-id cluster-key-1
```

---

## 7. Demonstrating this to others (5-minute walkthrough)

A good live-demo script:

1. **Set up the problem.** "Here's `model.bin`. Can you tell me which code
   and which job produced it?" → no, not without this tool.

2. **Run the three commands** from §5 live (prologue → job → epilogue).

3. **Show `out/provenance.json`** — point at the git commit SHA, the Slurm
   job id/nodes/partition, and the SHA-256 digests of the input and output
   files. Everyone can read this; it's just JSON.

4. **Show `out/attestation.dsse`** — "this is the same content, but sealed."

5. **Run `verify attestation`** → `VALID`. This is the "everything checks
   out" moment.

6. **The tamper-detection payoff.** Flip one character in the signature and
   re-verify — this is the actual security property DSSE provides:

   ```bash
   python -c "
   import json
   d = json.load(open('out/attestation.dsse'))
   sig = list(d['signatures'][0]['sig'])
   sig[-4] = 'A' if sig[-4] != 'A' else 'B'
   d['signatures'][0]['sig'] = ''.join(sig)
   json.dump(d, open('out/attestation_tampered.dsse', 'w'))
   "
   hpc-provenance verify attestation out/attestation_tampered.dsse --trusted-key-id cluster-key-1
   ```

   Output:
   ```
   ERROR: INVALID_SIGNATURE: Signature from key id 'cluster-key-1' did not verify
   INVALID
   ```
   (exit code 1)

7. **Wrap up with `examples/train.sh`** — show that in a real deployment,
   this is just three extra lines in a normal `sbatch` script.

---

## 8. Command cheat sheet

| Command | When | What it does |
|---|---|---|
| `hpc-provenance keys generate <key-id> --algorithm {ecdsa,rsa} --keys-dir keys` | once, per cluster/signer | Creates a signing key pair |
| `hpc-provenance slurm prologue --git-repo . --output-dir out` | start of job | Writes `prologue.json` snapshot |
| `hpc-provenance slurm epilogue --product <file> [--material <file>] --git-repo . --key-id <key-id> --output-dir out` | end of job | Writes `provenance.json` + `attestation.dsse`, saves to local catalog |
| `hpc-provenance verify attestation <file>.dsse --trusted-key-id <key-id>` | any time, by anyone with the public key | Checks signature + policy, exits 0/non-zero |
| `hpc-provenance generate run ...` / `hpc-provenance sign run ...` | advanced/manual flow (needs `--job-id` or a real `$SLURM_JOB_ID` + `sacct`/`scontrol`) | Lower-level equivalents of prologue/epilogue, for non-`sbatch` use |

Useful environment variables (all prefixed `HPC_PROVENANCE_`):

| Variable | Default | Purpose |
|---|---|---|
| `HPC_PROVENANCE_KEYS_DIRECTORY` | `./keys` | Where signing/verification keys live |
| `HPC_PROVENANCE_OUTPUT_DIRECTORY` | `./provenance` | Local catalog of signed receipts |
| `HPC_PROVENANCE_BUILDER_ID` | `https://example.org/hpc-provenance/builder/v1` | Identity recorded as the "builder" |

---

## 9. Current limitations (be honest about these in a demo)

- `hpc-provenance verify run <record-id>` (looking a receipt up by id from
  the catalog) is **not implemented yet** — use `verify attestation
  <path>.dsse` instead, which works directly off the file.
- `hpc-provenance generate run` / `sign run` need either `--job-id` or a real
  Slurm job (`$SLURM_JOB_ID` + working `sacct`/`scontrol`) — for local demos
  without a cluster, use `slurm prologue` / `slurm epilogue` (env-var based,
  as shown in §5).
- Verifying a payload that's been corrupted badly enough to break base64/JSON
  decoding currently raises an error rather than a clean `INVALID` result —
  tampering with the **signature** (as in §7) is the realistic attack and is
  handled cleanly.
