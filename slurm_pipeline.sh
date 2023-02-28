#!/bin/bash
#SBATCH --partition=imgcomputeq,imghmemq
#SBATCH --qos=img
#SBATCH --ntasks=1
#SBATCH --mem=16g
#SBATCH --time=02:00:00
#SBATCH --array=2-596
#SBATCH --job-name=ukbbseg

module load ukbbseg-img
module load quantiphyse-img
module load renal-preproc-img
module load dcm2niix-img
module load conda-img
source activate renal

DATA_DIR=/share/ukbiobank/Release_1_body/
OUTDIR=/share/ukbiobank/body_seg2
#SLURM_ARRAY_TASK_ID=0

python3 -u demistifi_pipeline.py --input "${DATA_DIR}" --output "${OUTDIR}" --subjids subjids --subjid-idx=${SLURM_ARRAY_TASK_ID}
