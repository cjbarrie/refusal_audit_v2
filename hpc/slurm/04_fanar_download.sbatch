#!/bin/bash
#SBATCH --job-name=fanar-download
#SBATCH --account=torch_pr_309_social_sciences
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=2
#SBATCH --mem=8G
#SBATCH --output=hpc/logs/fanar_download_%j.out
#SBATCH --error=hpc/logs/fanar_download_%j.err

set -euo pipefail
module purge
REFUSAL_PROJECT_ROOT="${REFUSAL_PROJECT_ROOT:-${SLURM_SUBMIT_DIR}}"
export REFUSAL_HPC_ROOT="${REFUSAL_HPC_ROOT:-/scratch/${USER}/refusal_audit_hpc}"
cd "${REFUSAL_PROJECT_ROOT}"
python hpc/download_models.py \
  --config config/model_rosters/fanar_experiments_v1.json \
  --model-index 1
