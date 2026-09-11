#!/bin/bash
#SBATCH --job-name=refusal-models
#SBATCH --account=torch_pr_309_social_sciences
#SBATCH --array=0-3%2
#SBATCH --time=04:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=hpc/logs/download_%A_%a.out
#SBATCH --error=hpc/logs/download_%A_%a.err

set -euo pipefail
REFUSAL_PROJECT_ROOT="${REFUSAL_PROJECT_ROOT:-${SLURM_SUBMIT_DIR}}"
REFUSAL_HPC_ROOT="${REFUSAL_HPC_ROOT:-/scratch/${USER}/refusal_audit_hpc}"
export HF_HOME="${REFUSAL_HPC_ROOT}/hf_cache"
source "${REFUSAL_HPC_ROOT}/venv/bin/activate"
cd "${REFUSAL_PROJECT_ROOT}"
python hpc/download_models.py --model-index "${SLURM_ARRAY_TASK_ID}"
