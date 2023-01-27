#!/bin/bash
#SBATCH --partition=imgcomputeq,imghmemq
#SBATCH --qos=img
#SBATCH --ntasks=1
#SBATCH --mem=16g
#SBATCH --time=01:00:00
#SBATCH --array=1-597
#SBATCH --job-name=ukbbseg

module load ukbbseg-img
module load quantiphyse-img
module load renal-preproc-img
module load dcm2niix-img
export PYTHONIOENCODING=utf_8

#DEMISTIFI_SKIP_PREPROC=1
#DEMISTIFI_SKIP_RENAL_PREPROC=1
#DEMISTIFI_SKIP_DIXON=1
#DEMISTIFI_SKIP_PANCREAS=1
#DEMISTIFI_SKIP_LIVER=1
#DEMISTIFI_SKIP_STATS=1

DATA_DIR=/share/ukbiobank/Release_1_body/
OUTDIR=/share/ukbiobank/body_seg

#SLURM_ARRAY_TASK_ID=1
#SUBJECT_INDIR=$(ls -d1 ${DATA_DIR}/*/Abdominal_MRI/ | sed -n ${SLURM_ARRAY_TASK_ID}p)
#SUBJECT_BASEDIR=`dirname ${SUBJECT_INDIR}`
#SUBJECT=`basename ${SUBJECT_BASEDIR}`

SUBJECT=`cat subjids |sed -n ${SLURM_ARRAY_TASK_ID}p`
SUBJECT_BASEDIR=${DATA_DIR}/${SUBJECT}
SUBJECT_INDIR=${SUBJECT_BASEDIR}/Abdominal_MRI

echo "Running subject ${SUBJECT}"

SUBJECT_OUTDIR=${OUTDIR}/${SUBJECT}
PREPROC_OUTDIR=${SUBJECT_OUTDIR}/preproc
SEG_OUTDIR=${SUBJECT_OUTDIR}/seg
mkdir -p "${PREPROC_OUTDIR}"
mkdir -p "${SEG_OUTDIR}"

if [ -z $DEMISTIFI_SKIP_PREPROC ]; then
  echo "Doing preprocessing for subject ${SUBJECT}"
  r-coh.py process "${SUBJECT_INDIR}" "${PREPROC_OUTDIR}" --biobank-project=None 2>&1 >"$SUBJECT_OUTDIR/logfile.txt"
  SUBJECT_ID=`ls "${PREPROC_OUTDIR}"`
  mv $SUBJECT_OUTDIR/logfile.txt ${PREPROC_OUTDIR}/$SUBJECT_ID/
  echo "DONE preprocessing for subject ${SUBJECT}"
fi
SUBJECT_ID=`ls "${PREPROC_OUTDIR}"`

RENAL_OUTDIR=${PREPROC_OUTDIR}/$SUBJECT_ID/renal
if [ -z $DEMISTIFI_SKIP_RENAL_PREPROC ]; then
  echo "Doing renal preprocessing for subject ${SUBJECT}"

  mkdir -p "$PREPROC_OUTDIR/$SUBJECT_ID/renal"
  renal-preproc --indir "$PREPROC_OUTDIR/$SUBJECT_ID/tmp/dicom_series/" --outdir "$PREPROC_OUTDIR/$SUBJECT_ID/renal" --t2star-matcher=_gre_ --t2star-method=loglin --overwrite 2>"$PREPROC_OUTDIR/$SUBJECT_ID/renal/err.txt" >"$PREPROC_OUTDIR/$SUBJECT_ID/renal/logfile.txt"

  echo "DONE renal preprocessing for subject ${SUBJECT}"
fi

echo $SUBJECT_ID > "${SUBJECT_OUTDIR}/subjid.txt"
NIFTI_DIR=$PREPROC_OUTDIR/$SUBJECT_ID/nifti
TMP_NIFTI_DIR=$PREPROC_OUTDIR/$SUBJECT_ID/tmp/nifti_series

SEG_MODELS_DIR=/software/imaging/ukbbseg/ukbb-mri-sseg/trained_models

if [ -z $DEMISTIFI_SKIP_DIXON ]; then

  echo "Doing knee-to-neck segmentation for subject ${SUBJECT}"

  KNEE_TO_NEXT_MODEL=$SEG_MODELS_DIR/knee_to_neck_dixon/20200401-mpgp118-best_xe/model.ckpt-20000
  infer_knee_to_neck_dixon \
    --output_folder="${SEG_OUTDIR}" \
    --reference_header_nifti="${NIFTI_DIR}/mask.nii.gz" \
    --save_what=prob \
    --threshold_method=fg \
    --fat=$NIFTI_DIR/fat.nii.gz\
    --water=$NIFTI_DIR/water.nii.gz\
    --inphase=$NIFTI_DIR/ip.nii.gz\
    --outphase=$NIFTI_DIR/op.nii.gz\
    --mask=$NIFTI_DIR/mask.nii.gz\
    --restore_string=${KNEE_TO_NEXT_MODEL}

  echo "DONE knee-to-neck segmentation for subject ${SUBJECT}"
fi

if [ -z $DEMISTIFI_SKIP_PANCREAS ]; then

  echo "Doing pancreas T1w segmentation for subject ${SUBJECT}"

  PANCREAS_MODEL_H5=$SEG_MODELS_DIR/pancreas_t1w/20200104_shape-rep-a-dice2-ep50.h5
  infer_pancreas_t1w --action=infer \
      --output_folder=$SEG_OUTDIR \
      --IDS_FILE=${SUBJECT_OUTDIR}/subjid.txt \
      --model_h5_path=$PANCREAS_MODEL_H5 \
      --input_nifti_subject_dir=$PREPROC_OUTDIR

  echo "DONE pancreas T1w segmentation for subject ${SUBJECT}"
fi

if [ -z $DEMISTIFI_SKIP_LIVER ]; then
  echo "Doing liver ideal segmentation for subject ${SUBJECT}"

  LIVER_IDEAL_MODEL_H5=$SEG_MODELS_DIR/liver_ideal/20191002_withphase_low_liver_2d_ideal.h5
  infer_liver_ideal_multiecho --action=infer \
      --output_folder=$SEG_OUTDIR \
      --data_modality=ideal_liver \
      --IDS_FILE=${SUBJECT_OUTDIR}/subjid.txt \
      --model_h5_path=$LIVER_IDEAL_MODEL_H5 \
      --input_nifti_subject_dir=$PREPROC_OUTDIR

  echo "DONE liver ideal segmentation for subject ${SUBJECT}"
fi

if [ -z $DEMISTIFI_SKIP_STATS ]; then

  echo "Linking segmentation and data sets for subject ${SUBJECT}"

  QP_DATA_DIR=${SUBJECT_OUTDIR}/qpdata
  rm -rf "$QP_DATA_DIR"
  mkdir -p "$QP_DATA_DIR"
  ln -s "$SEG_OUTDIR/pancreas_t1w_sseg/${SUBJECT_ID}.nii.gz" "$QP_DATA_DIR/seg_pancreas_t1w.nii.gz"
  ln -s "$SEG_OUTDIR/ideal_liver_seg/${SUBJECT_ID}.nii.gz" "$QP_DATA_DIR/seg_liver_gradecho.nii.gz"
  ln -s "$SEG_OUTDIR/knee_to_neck_dixon_seg/otsu_prob_argmax_liver.nii.gz" "$QP_DATA_DIR/seg_liver_dixon.nii.gz"
  ln -s "$SEG_OUTDIR/knee_to_neck_dixon_seg/otsu_prob_argmax_kidney_right.nii.gz" "$QP_DATA_DIR/seg_kidney_right_dixon.nii.gz"
  ln -s "$SEG_OUTDIR/knee_to_neck_dixon_seg/otsu_prob_argmax_kidney_left.nii.gz" "$QP_DATA_DIR/seg_kidney_left_dixon.nii.gz"
  ln -s "$SEG_OUTDIR/knee_to_neck_dixon_seg/otsu_prob_argmax_spleen.nii.gz" "$QP_DATA_DIR/seg_spleen_dixon.nii.gz"

  ln -s $TMP_NIFTI_DIR/*_ShMOLLI_*LIVER_T1MAP.nii.gz "$QP_DATA_DIR/t1_liver.nii.gz"
  ln -s $TMP_NIFTI_DIR/*_ShMOLLI_*pancreas_T1MAP.nii.gz "$QP_DATA_DIR/t1_pancreas.nii.gz"
  ln -s $TMP_NIFTI_DIR/*_ShMOLLI_*KIDNEY_T1MAP.nii.gz "$QP_DATA_DIR/t1_kidney.nii.gz"
  ln -s "$NIFTI_DIR/multiecho_pancreas_magnitude.nii.gz" "$QP_DATA_DIR/gradecho_pancreas.nii.gz"
  ln -s "$NIFTI_DIR/ideal_liver_magnitude.nii.gz" "$QP_DATA_DIR/gradecho_liver.nii.gz"
  ln -s $RENAL_OUTDIR/*_gre_*_pancreas*/t2star_out/*_loglin_t2star_map.nii.gz "$QP_DATA_DIR/t2star_pancreas.nii.gz"
  ln -s $RENAL_OUTDIR/*_gre_*_pancreas*/t2star_out/*_loglin_r2star_map.nii.gz "$QP_DATA_DIR/r2star_pancreas.nii.gz"
  ln -s $RENAL_OUTDIR/*_gre_*_kidney*/t2star_out/*_loglin_t2star_map.nii.gz "$QP_DATA_DIR/t2star_kidney.nii.gz"
  ln -s $RENAL_OUTDIR/*_gre_*_kidney*/t2star_out/*_loglin_r2star_map.nii.gz "$QP_DATA_DIR/r2star_kidney.nii.gz"
  ln -s $RENAL_OUTDIR/*_gre_*_liver*/t2star_out/*_loglin_t2star_map.nii.gz "$QP_DATA_DIR/t2star_liver.nii.gz"
  ln -s $RENAL_OUTDIR/*_gre_*_liver*/t2star_out/*_loglin_r2star_map.nii.gz "$QP_DATA_DIR/r2star_liver.nii.gz"

  echo "DONE Linking segmentation and data sets for subject ${SUBJECT}"

  echo "Extracting ROI stats for  ${SUBJECT}"

  QP_SCRIPT=/share/ukbiobank/body_seg/resample_and_stats.qp
  rm -rf "$QP_DATA_DIR/resample_and_stats.qp"
  sed "s/SUBJID/$SUBJECT/g" $QP_SCRIPT > $QP_DATA_DIR/resample_and_stats.qp
  quantiphyse --batch=$QP_DATA_DIR/resample_and_stats.qp

  echo "DONE Extracting ROI stats for  ${SUBJECT}"
fi

echo "DONE Running subject ${SUBJECT}"
