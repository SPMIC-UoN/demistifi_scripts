"""
Processing pipeline for DEMISTIFI using UKB data
"""
import argparse
import glob
import os
import shutil
import sys

class ArgumentParser(argparse.ArgumentParser):
    """
    ArgumentParser for program options
    """

    def __init__(self, **kwargs):
        argparse.ArgumentParser.__init__(self, prog="demistifi-ukb-pipeline", add_help=True, **kwargs)
        self.add_argument("--input", required=True, help="Input directory containing subject dirs")
        self.add_argument("--output", required=True, help="Output directory")
        self.add_argument("--subjids", required=True, help="File containing subject IDs to process")
        self.add_argument("--subjid-idx", help="Index of individual subject ID to process. If not specified, process all")
        
        self.add_argument("--skip-preproc", action='store_true', default=False, help="Skip r_coh preprocessing step")
        self.add_argument("--skip-seg", action='store_true', default=False, help="Skip segmentation steps")
        self.add_argument("--skip-stats", action='store_true', default=False, help="Skip statistics generation")
        self.add_argument("--seg-models-dir", default="/software/imaging/ukbbseg/ukbb-mri-sseg/trained_models", help="Directory contained trained segmentation models")

def link(srcdir, srcfile, destdir, destfile):
    """
    Link supporting wildcards
    """
    srcfiles = list(glob.glob(os.path.join(srcdir, f"{srcfile}.nii.gz")))
    if not srcfiles:
        print(f"WARNING: Could not create link for output file {destfile} - source file {srcfile} not found")
    elif len(srcfiles) > 1:
        print(f"WARNING: Could not create link for output file {destfile} - multiple source files {srcfile} found")
    else:
        os.symlink(srcfiles[0], os.path.join(destdir, f"{destfile}.nii.gz"))

def main():
    options = ArgumentParser().parse_args()
    with open(options.subjids, "r") as f:
        subjids = [l.strip() for l in f.readlines()]
    if options.subjid_idx:
        subjids = [subjids[options.subjid_idx]]

    for subjid in subjids:
        subj_basedir = os.path.join(options.input, subjid)
        subj_indir = os.path.join(subj_basedir, "Abdominal_MRI")

        print(f"Running subject {subjid}")
        subj_outdir = os.path.join(options.output, subjid)
        
        preproc_outdir = os.path.join(subj_outdir, "preproc")
        if not options.skip_preproc:
            print(f"Doing r-coh preprocessing for subject {subjid}")
            os.makedirs(preproc_outdir, exist_ok=True)
            os.system(f'r-coh.py process "{subj_indir}" "{preproc_outdir}" --biobank-project=None 2>&1 >"{subj_outdir}/logfile.txt"')
            subjid_preproc = os.listdir(preproc_outdir)[0]
            os.rename(f"{subj_outdir}/logfile.txt", f"{preproc_outdir}/{subjid_preproc}/logfile.txt")
            print(f"DONE preprocessing for subject {subjid}")
        
            print(f"Doing renal preprocessing for subject {subjid}")
            renal_outdir = os.path.join(preproc_outdir, subjid_preproc, "renal")
            os.makedirs(renal_outdir, exist_ok=True)
            os.system(f'renal-preproc \
                --indir "{preproc_outdir}/{subjid_preproc}/tmp/dicom_series/" \
                --outdir "{preproc_outdir}/{subjid_preproc}/renal" \
                --t2star-matcher=_gre_ --t2star-method=loglin \
                --overwrite \
                2>"{preproc_outdir}/{subjid_preproc}/renal/err.txt" \
                >"{preproc_outdir}/{subjid_preproc}/renal/logfile.txt"')
            print(f"DONE renal preprocessing for subject {subjid}")
        else:
            subjid_preproc = os.listdir(preproc_outdir)[0]
            renal_outdir = os.path.join(preproc_outdir, subjid_preproc, "renal")

        with open(os.path.join(subj_outdir, "subjid.txt"), "w") as f:
            f.write(f"{subjid_preproc}\n")
          
        nifti_dir = os.path.join(preproc_outdir, subjid_preproc, "nifti")
        tmp_nifti_dir = os.path.join(preproc_outdir, subjid_preproc, "tmp", "nifti_series")

        seg_outdir = os.path.join(subj_outdir, "seg")
        if not options.skip_seg:
            print(f"Doing DIXON segmentation for subject {subjid}")
            knee_to_neck_model = os.path.join(options.seg_models_dir, "knee_to_neck_dixon/20200401-mpgp118-best_xe/model.ckpt-20000")
            os.system(f'infer_knee_to_neck_dixon \
                --output_folder="{seg_outdir}" \
                --reference_header_nifti="{nifti_dir}/mask.nii.gz" \
                --save_what=prob \
                --threshold_method=fg \
                --fat={nifti_dir}/fat.nii.gz \
                --water={nifti_dir}/water.nii.gz \
                --inphase={nifti_dir}/ip.nii.gz \
                --outphase={nifti_dir}/op.nii.gz \
                --mask={nifti_dir}/mask.nii.gz \
                --restore_string="{knee_to_neck_model}"')
            print(f"DONE DIXON segmentation for subject {subjid}")

            print(f"Doing pancreas T1w segmentation for subject {subjid}")
            os.makedirs(seg_outdir, exist_ok=True)
            pancreas_model = os.path.join(options.seg_models_dir, "pancreas_t1w/20200104_shape-rep-a-dice2-ep50.h5")
            os.system(f'infer_pancreas_t1w --action=infer \
                --output_folder={seg_outdir} \
                --IDS_FILE={subj_outdir}/subjid.txt \
                --model_h5_path={pancreas_model} \
                --input_nifti_subject_dir={preproc_outdir}')
            print(f"DONE pancreas T1w segmentation for subject {subjid}")

            print(f"Doing liver IDEAL segmentation for subject {subjid}")
            liver_ideal_model = os.path.join(options.seg_models_dir, "liver_ideal/20191002_withphase_low_liver_2d_ideal.h5")
            os.system(f'infer_liver_ideal_multiecho --action=infer \
                --output_folder={seg_outdir} \
                --data_modality=ideal_liver \
                --IDS_FILE={subj_outdir}/subjid.txt \
                --model_h5_path={liver_ideal_model} \
                --input_nifti_subject_dir={preproc_outdir}')
            print(f"DONE liver IDEAL segmentation for subject {subjid}")

        if not options.skip_stats:
            print(f"Linking segmentation and data sets for subject {subjid}")
            qp_data_dir = os.path.join(subj_outdir, "qpdata")
            if os.path.exists(qp_data_dir):
                shutil.rmtree(qp_data_dir)
            os.makedirs(qp_data_dir)

            # Segmentations
            link(seg_outdir, f"pancreas_t1w_sseg/{subjid_preproc}", qp_data_dir, "seg_pancreas_t1w")
            link(seg_outdir, f"ideal_liver_seg/{subjid_preproc}", qp_data_dir, "seg_liver_gradecho")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_liver", qp_data_dir, "seg_liver_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_kidney_right", qp_data_dir, "seg_kidney_right_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_kidney_left", qp_data_dir, "seg_kidney_left_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_spleen", qp_data_dir, "seg_spleen_dixon")

            # Parameter maps
            link(tmp_nifti_dir, "*_ShMOLLI_*LIVER_T1MAP", qp_data_dir, "t1_liver")
            link(tmp_nifti_dir, "*_ShMOLLI_*pancreas_T1MAP", qp_data_dir, "t1_pancreas")
            link(tmp_nifti_dir, "*_ShMOLLI_*KIDNEY_T1MAP", qp_data_dir, "t1_kidney")
            link(nifti_dir, "multiecho_pancreas_magnitude", qp_data_dir, "gradecho_pancreas")
            link(nifti_dir, "ideal_liver_magnitude", qp_data_dir, "gradecho_liver")
            link(renal_outdir, "*_gre_*_pancreas*/t2star_out/*_loglin_t2star_map", qp_data_dir, "t2star_pancreas")
            link(renal_outdir, "*_gre_*_pancreas*/t2star_out/*_loglin_r2star_map", qp_data_dir, "r2star_pancreas")
            link(renal_outdir, "*_gre_*_kidney*/t2star_out/*_loglin_t2star_map", qp_data_dir, "t2star_kidney")
            link(renal_outdir, "*_gre_*_kidney*/t2star_out/*_loglin_r2star_map", qp_data_dir, "r2star_kidney")
            link(renal_outdir, "*_gre_*_liver*/t2star_out/*_loglin_t2star_map", qp_data_dir, "t2star_liver")
            link(renal_outdir, "*_gre_*_liver*/t2star_out/*_loglin_r2star_map", qp_data_dir, "r2star_liver")
            print(f"DONE Linking segmentation and data sets for subject {subjid}")

            print(f"Extracting ROI stats for subject {subjid}")
            qp_script = os.path.join(options.output, "resample_and_stats.qp")
            subj_qp_script = os.path.join(qp_data_dir, "resample_and_stats.qp")
            if os.path.exists(subj_qp_script):
                os.remove(subj_qp_script, exist_ok=True)
            with open(qp_script, "r") as f:
                with open(subj_qp_script, "w") as of:
                    for line in f.readlines():
                        of.write(line.replace("SUBJID", subjid))
            os.system(f'quantiphyse --batch={qp_data_dir}/resample_and_stats.qp')
            print(f"DONE Extracting ROI stats for subject {subjid}")

        print(f"DONE running subject {subjid}")

if __name__ == "__main__":
    main()
