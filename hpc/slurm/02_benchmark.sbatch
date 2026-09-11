#!/bin/bash
#SBATCH --job-name=refusal-bench
#SBATCH --account=torch_pr_309_social_sciences
#SBATCH --array=0-3
#SBATCH --time=02:00:00
#SBATCH --cpus-per-task=8
#SBATCH --mem=32G
#SBATCH --gres=gpu:1
#SBATCH --constraint=l40s
#SBATCH --output=hpc/logs/benchmark_%A_%a.out
#SBATCH --error=hpc/logs/benchmark_%A_%a.err

set -euo pipefail
module purge
command -v apptainer >/dev/null
REFUSAL_PROJECT_ROOT="${REFUSAL_PROJECT_ROOT:-${SLURM_SUBMIT_DIR}}"
export REFUSAL_HPC_ROOT="${REFUSAL_HPC_ROOT:-/scratch/${USER}/refusal_audit_hpc}"
cd "${REFUSAL_PROJECT_ROOT}"
python hpc/run_local_gguf_shard.py benchmark --task-id "${SLURM_ARRAY_TASK_ID}"
