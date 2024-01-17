#!/bin/bash
#NOTSBATCH --partition=imgvoltaq,imgpascalq
#SBATCH --partition=imghmemq,imgcomputeq
#SBATCH --qos=img
#SBATCH --ntasks=1
#SBATCH --mem=32g
#SBATCH --time=06:00:00
#SBATCH --array=0-10
#SBATCH --job-name=demistifi
#NOTSBATCH --gres=gpu:1
#SBATCH --export=NONE
#SBATCH --output demistifi_logs/%A_%a.out
#SBATCH --error demistifi_logs/%A_%a.err

module load conda-img
module load ukbbseg-img
module load dcm2niix-img
module load renal-preproc-img
module load quantiphyse-img
source activate img

DATA_DIR=/share/ukbiobank/Release_1_body/
OUTDIR=/spmstore/project/RenalMRI/demistifi/output
GROUPSDIR=/spmstore/project/RenalMRI/demistifi/subgroups/
SLURM_ARRAY_TASK_ID=1
SUBJGROUP=Spleen_disease

echo "Processing from group $SUBJGROUP"
python3 -u demistifi_pipeline.py --input "${DATA_DIR}" --output "${OUTDIR}/${SUBJGROUP}" --subjids $GROUPSDIR/$SUBJGROUP --subjid-idx=${SLURM_ARRAY_TASK_ID} --skip-rcoh --skip-seg
