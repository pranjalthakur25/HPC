#!/bin/bash
#SBATCH --job-name=train-model
#SBATCH --output=logs/train-%j.out
#SBATCH --error=logs/train-%j.err
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --partition=gpu
#SBATCH --gres=gpu:1
#
# Example sbatch script demonstrating hpc-provenance's Slurm prologue/epilogue
# hooks. Everything below runs as the submitting user via the hpc-provenance
# CLI -- no slurm.conf or admin access is required.
#
# One-time setup (run once, before submitting jobs):
#   pip install hpc-provenance
#   hpc-provenance keys generate cluster-key-1 --algorithm ecdsa --keys-dir keys

set -euo pipefail

cd "$SLURM_SUBMIT_DIR"
mkdir -p logs out

export HPC_PROVENANCE_KEYS_DIRECTORY="$SLURM_SUBMIT_DIR/keys"
export HPC_PROVENANCE_OUTPUT_DIRECTORY="$SLURM_SUBMIT_DIR/provenance"

# --- Prologue: snapshot job/git state at the start of the job ---------------
hpc-provenance slurm prologue \
    --git-repo "$SLURM_SUBMIT_DIR" \
    --output-dir "$SLURM_SUBMIT_DIR/out"

# --- Job: the actual workload ------------------------------------------------
python train.py --epochs 5 --output "$SLURM_SUBMIT_DIR/out/model.safetensors"

# --- Epilogue: generate and sign provenance for this run ---------------------
hpc-provenance slurm epilogue \
    --product "$SLURM_SUBMIT_DIR/out/model.safetensors" \
    --material "$SLURM_SUBMIT_DIR/train.py" \
    --git-repo "$SLURM_SUBMIT_DIR" \
    --key-id cluster-key-1 \
    --output-dir "$SLURM_SUBMIT_DIR/out"

# To verify the resulting attestation afterwards, run:
#   hpc-provenance verify attestation out/attestation.dsse --trusted-key-id cluster-key-1
