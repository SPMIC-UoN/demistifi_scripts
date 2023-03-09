"""
Processing pipeline for DEMISTIFI using UKB data
"""
import argparse
import glob
import os
import shutil
import sys
import traceback

import nibabel as nib

class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        argparse.ArgumentParser.__init__(self, prog="demistifi-ukb-pipeline", add_help=True, **kwargs)
        self.add_argument("--input", required=True, help="Input directory containing subject dirs")
        self.add_argument("--output", required=True, help="Output directory")
        self.add_argument("--subjids", required=True, help="File containing subject IDs to process")
        self.add_argument("--subjid-idx", type=int, help="Index of individual subject ID to process (starting at 1). If not specified, process all")        
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

def get_preproc_subjid(preproc_basedir):
    """
    Get the subject ID which is only visible after preprocessing

    :return: tuple of subject ID, full preproc dir path
    """
    preproc_files = os.listdir(preproc_basedir)
    if not preproc_files:
        raise RuntimeError(f"No preprocessing files found in {preproc_basedir}")
    elif len(preproc_files) > 1:
        raise RuntimeError(f"Multiple preprocessing files found in {preproc_basedir} - cannot identify subject ID")
    else:
        return preproc_files[0], os.path.join(preproc_basedir, preproc_files[0])

def r2star_to_t2star(indir):
    """
    Calculate T2* for any R2* maps found in indir
    """
    for f in glob.glob(os.path.join(indir, "*r2star*")):
        try:
            f_r2star = os.path.join(indir, f)
            f_t2star = f_r2star.replace("r2star", "t2star")
            nii_r2star = nib.load(f_r2star)
            nii_t2star = nib.Nifti1Image(1000.0/nii_r2star.get_fdata(), None, nii_r2star.header)
            nii_t2star.to_filename(f_t2star)
        except:
            print(f"WARNING: Failed to calculate T2* for R2* file: {f_r2star}")
            traceback.print_exc()

def correct_r2star_units(indir):
    """
    Convert R2* output from ms^-1 to s^-1
    """
    for root, dirs, files in os.walk(indir):
        for f in files:
            if "r2star" in f:
                fname = os.path.join(root, f)
                nii_r2star = nib.load(fname)
                nii_r2star = nib.Nifti1Image(1000.0 * nii_r2star.get_fdata(), None, nii_r2star.header)
                nii_r2star.to_filename(fname)

def run(cmd):
    """
    Run a command and raise exception if it fails
    """
    retval = os.system(cmd)
    if retval != 0:
        print(f"WARNING: command\n{cmd}\nreturned non-zero exit state {retval}")

def main():
    options = ArgumentParser().parse_args()
    with open(options.subjids, "r") as f:
        subjids = [l.strip() for l in f.readlines()]
    if options.subjid_idx:
        subjids = [subjids[options.subjid_idx-1]]

    for subjid in subjids:
        subj_basedir = os.path.join(options.input, subjid)
        subj_indir = os.path.join(subj_basedir, "Abdominal_MRI")

        print(f"Running subject {subjid}")
        subj_outdir = os.path.join(options.output, subjid)
        
        preproc_basedir = os.path.join(subj_outdir, "preproc")
        if not options.skip_preproc:
            print(f"Doing r-coh preprocessing for subject {subjid}")
            os.makedirs(preproc_basedir, exist_ok=True)
            run(f'r-coh.py process \
                "{subj_indir}" \
                "{preproc_basedir}" \
                --biobank-project=None \
                >"{subj_outdir}/logfile.txt" 2>&1')
            subjid_preproc, preproc_outdir = get_preproc_subjid(preproc_basedir)
            os.rename(f"{subj_outdir}/logfile.txt", f"{preproc_outdir}/preproc_logfile.txt")
        
            r2star_to_t2star(os.path.join(preproc_outdir, "analysis"))

            print(f"DONE preprocessing for subject {subjid}")
        
            print(f"Doing renal preprocessing for subject {subjid}")
            renal_outdir = os.path.join(preproc_basedir, subjid_preproc, "renal")
            os.makedirs(renal_outdir, exist_ok=True)
            run(f'renal-preproc \
                --indir "{preproc_outdir}/tmp/dicom_series/" \
                --outdir "{preproc_outdir}/renal" \
                --t2star-matcher=_gre_ --t2star-method=loglin \
                --overwrite \
                >"{preproc_outdir}/renal_logfile.txt" 2>&1')
            correct_r2star_units(renal_outdir)
            print(f"DONE renal preprocessing for subject {subjid}")
        else:
            subjid_preproc, preproc_outdir = get_preproc_subjid(preproc_basedir)
            renal_outdir = os.path.join(preproc_outdir, "renal")

        with open(os.path.join(subj_outdir, "subjid.txt"), "w") as f:
            f.write(f"{subjid_preproc}\n")
          
        nifti_dir = os.path.join(preproc_outdir, "nifti")
        tmp_nifti_dir = os.path.join(preproc_outdir, "tmp", "nifti_series")
        analysis_dir = os.path.join(preproc_outdir, "analysis")

        seg_outdir = os.path.join(subj_outdir, "seg")
        if not options.skip_seg:
            os.makedirs(seg_outdir, exist_ok=True)
            print(f"Doing DIXON segmentation for subject {subjid}")
            knee_to_neck_model = os.path.join(options.seg_models_dir, "knee_to_neck_dixon/20200401-mpgp118-best_xe/model.ckpt-20000")
            run(f'infer_knee_to_neck_dixon \
                --output_folder="{seg_outdir}" \
                --reference_header_nifti="{nifti_dir}/mask.nii.gz" \
                --save_what=prob \
                --threshold_method=fg \
                --fat={nifti_dir}/fat.nii.gz \
                --water={nifti_dir}/water.nii.gz \
                --inphase={nifti_dir}/ip.nii.gz \
                --outphase={nifti_dir}/op.nii.gz \
                --mask={nifti_dir}/mask.nii.gz \
                --restore_string="{knee_to_neck_model}" \
                >"{seg_outdir}/dixon_logfile.txt" 2>&1')
            print(f"DONE DIXON segmentation for subject {subjid}")

            print(f"Doing pancreas T1w segmentation for subject {subjid}")
            pancreas_model = os.path.join(options.seg_models_dir, "pancreas_t1w/20200104_shape-rep-a-dice2-ep50.h5")
            run(f'infer_pancreas_t1w --action=infer \
                --output_folder={seg_outdir} \
                --IDS_FILE={subj_outdir}/subjid.txt \
                --model_h5_path={pancreas_model} \
                --input_nifti_subject_dir={preproc_basedir} \
                >"{seg_outdir}/pancreas_t1_logfile.txt" 2>&1')
            print(f"DONE pancreas T1w segmentation for subject {subjid}")

            print(f"Doing liver IDEAL segmentation for subject {subjid}")
            liver_ideal_model = os.path.join(options.seg_models_dir, "liver_ideal/20191002_withphase_low_liver_2d_ideal.h5")
            run(f'infer_liver_ideal_multiecho --action=infer \
                --output_folder={seg_outdir} \
                --data_modality=ideal_liver \
                --IDS_FILE={subj_outdir}/subjid.txt \
                --model_h5_path={liver_ideal_model} \
                --input_nifti_subject_dir={preproc_basedir} \
                >"{seg_outdir}/liver_ideal_logfile.txt" 2>&1')
            print(f"DONE liver IDEAL segmentation for subject {subjid}")

        if not options.skip_stats:
            print(f"Linking segmentation and data sets for subject {subjid}")
            qp_data_dir = os.path.join(subj_outdir, "qpdata")
            if os.path.exists(qp_data_dir):
                shutil.rmtree(qp_data_dir)
            os.makedirs(qp_data_dir)

            # Segmentations
            link(seg_outdir, f"pancreas_t1w_sseg/{subjid_preproc}", qp_data_dir, "seg_pancreas_t1w")
            link(seg_outdir, f"ideal_liver_seg/{subjid_preproc}", qp_data_dir, "seg_liver_ideal")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_liver", qp_data_dir, "seg_liver_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_kidney_right", qp_data_dir, "seg_kidney_right_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_kidney_left", qp_data_dir, "seg_kidney_left_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_spleen", qp_data_dir, "seg_spleen_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_lungs", qp_data_dir, "seg_lungs_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_body_cavity", qp_data_dir, "seg_body_cavity_dixon")
            link(seg_outdir, f"knee_to_neck_dixon_seg/otsu_prob_argmax_abdominal_cavity", qp_data_dir, "seg_abdominal_cavity_dixon")

            # Preproc outputs
            link(analysis_dir, "multiecho.pancreas_presco_t2star", qp_data_dir, "t2star_pancreas_gre_presco")
            link(analysis_dir, "multiecho.kidney_presco_t2star", qp_data_dir, "t2star_kidney_gre_presco")
            link(analysis_dir, "ideal.liver_presco_t2star", qp_data_dir, "t2star_liver_ideal_presco")
            link(analysis_dir, "multiecho.pancreas_presco_r2star", qp_data_dir, "r2star_pancreas_gre_presco")
            link(analysis_dir, "multiecho.kidney_presco_r2star", qp_data_dir, "r2star_kidney_gre_presco")
            link(analysis_dir, "ideal.liver_presco_r2star", qp_data_dir, "r2star_liver_ideal_presco")
            link(analysis_dir, "multiecho.pancreas_presco_iron", qp_data_dir, "iron_pancreas_gre_presco")
            link(analysis_dir, "multiecho.kidney_presco_iron", qp_data_dir, "iron_kidney_gre_presco")
            link(analysis_dir, "ideal.liver_presco_iron", qp_data_dir, "iron_liver_ideal_presco")
            link(analysis_dir, "multiecho.pancreas_presco_pdff", qp_data_dir, "pdff_pancreas_gre_presco")
            link(analysis_dir, "multiecho.kidney_presco_pdff", qp_data_dir, "pdff_kidney_gre_presco")
            link(analysis_dir, "ideal.liver_presco_pdff", qp_data_dir, "pdff_liver_ideal_presco")
            link(tmp_nifti_dir, "*_ShMOLLI_*LIVER_T1MAP", qp_data_dir, "t1_liver_molli")
            link(tmp_nifti_dir, "*_ShMOLLI_*pancreas_T1MAP", qp_data_dir, "t1_pancreas_molli")
            link(tmp_nifti_dir, "*_ShMOLLI_*kidney_T1MAP", qp_data_dir, "t1_kidney_molli")

            # Parameter maps
            #link(nifti_dir, "multiecho_pancreas_magnitude", qp_data_dir, "multiecho_pancreas")
            #link(nifti_dir, "ideal_liver_magnitude", qp_data_dir, "multiecho_liver")

            # Renal preproc outputs
            link(renal_outdir, "*_gre_*_pancreas*/t2star_out/*_loglin_t2star_map", qp_data_dir, "t2star_pancreas_gre_loglin")
            link(renal_outdir, "*_gre_*_pancreas*/t2star_out/*_loglin_r2star_map", qp_data_dir, "r2star_pancreas_gre_loglin")
            link(renal_outdir, "*_gre_*_kidney*/t2star_out/*_loglin_t2star_map", qp_data_dir, "t2star_kidney_gre_loglin")
            link(renal_outdir, "*_gre_*_kidney*/t2star_out/*_loglin_r2star_map", qp_data_dir, "r2star_kidney_gre_loglin")
            link(renal_outdir, "*_gre_*_liver*/t2star_out/*_loglin_t2star_map", qp_data_dir, "t2star_liver_gre_loglin")
            link(renal_outdir, "*_gre_*_liver*/t2star_out/*_loglin_r2star_map", qp_data_dir, "r2star_liver_gre_loglin")
            print(f"DONE Linking segmentation and data sets for subject {subjid}")

            print(f"Extracting ROI stats for subject {subjid}")
            qp_script = os.path.join(os.path.dirname(sys.argv[0]), "resample_and_stats.qp")
            subj_qp_script = os.path.join(qp_data_dir, "resample_and_stats.qp")
            if os.path.exists(subj_qp_script):
                os.remove(subj_qp_script, exist_ok=True)
            with open(qp_script, "r") as f:
                with open(subj_qp_script, "w") as of:
                    for line in f.readlines():
                        of.write(line.replace("SUBJID", subjid).replace("OUTDIR", options.output))
            run(f'quantiphyse \
                --batch={qp_data_dir}/resample_and_stats.qp \
                >"{qp_data_dir}/qp_logfile.txt" 2>&1')
            print(f"DONE Extracting ROI stats for subject {subjid}")

        print(f"DONE running subject {subjid}")

if __name__ == "__main__":
    main()
