#!/bin/bash
#SBATCH --job-name=refusal-bootstrap
#SBATCH --account=torch_pr_309_social_sciences
#SBATCH --time=01:00:00
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --output=hpc/logs/bootstrap_%j.out
#SBATCH --error=hpc/logs/bootstrap_%j.err

set -euo pipefail
module purge
# Torch exposes Apptainer on the base system PATH; it is not an Lmod module.
command -v apptainer >/dev/null

REFUSAL_HPC_ROOT="${REFUSAL_HPC_ROOT:-/scratch/${USER}/refusal_audit_hpc}"
mkdir -p "${REFUSAL_HPC_ROOT}/containers" "${REFUSAL_HPC_ROOT}/models" "${REFUSAL_HPC_ROOT}/locks"
python3 -m venv "${REFUSAL_HPC_ROOT}/venv"
source "${REFUSAL_HPC_ROOT}/venv/bin/activate"
python -m pip install --upgrade pip
python -m pip install 'huggingface_hub[cli]==0.34.4'

CONTAINER="${REFUSAL_HPC_ROOT}/containers/llama-server-cuda-b10335.sif"
if [[ ! -f "${CONTAINER}" ]]; then
  apptainer pull "${CONTAINER}" docker://ghcr.io/ggml-org/llama.cpp:server-cuda-b10335
fi
sha256sum "${CONTAINER}" > "${REFUSAL_HPC_ROOT}/locks/container.sha256"
apptainer inspect "${CONTAINER}" > "${REFUSAL_HPC_ROOT}/locks/container.inspect.txt"
