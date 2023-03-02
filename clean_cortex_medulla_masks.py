"""
Clean cortex and medulla masks generated from Zhendi DL methods

EFC December 2022
"""
import skimage
import numpy as np
import nibabel as nib

t1 = '900041794_KIDNEY_T1Map_LongT1_MoCo_20211110150850_31.nii'
#cortex_new = 'corN_900041794_KIDNEY_T1Map_LongT1_MoCo_20211110150850_31.nii.gz'
#cortex = 'cortex_900041794_KIDNEY_T1Map_LongT1_MoCo_20211110150850_31.nii.gz'
#medulla_new = 'medN_900041794_KIDNEY_T1Map_LongT1_MoCo_20211110150850_31.nii.gz'
#medulla = 'medulla_900041794_KIDNEY_T1Map_LongT1_MoCo_20211110150850_31.nii.gz'
cortex = "cortex_rot.nii.gz"
medulla = "medulla_rot.nii.gz"

# get maps
nii_t1 = nib.load(t1)
img_data = nii_t1.get_fdata()

# get masks
nii_cortex = nib.load(cortex)
mask_img_cor = nii_cortex.get_fdata().astype(int)
mask_img_cor[mask_img_cor<0] = 0
mask_img_cor[mask_img_cor>0] = 1

nii_medulla = nib.load(medulla)
mask_img_med = nii_medulla.get_fdata().astype(int)
mask_img_med[mask_img_med<0] = 0
mask_img_med[mask_img_med>0] = 1

if mask_img_cor.ndim < 3:
    mask_img_cor = mask_img_cor[..., np.newaxis]
if mask_img_med.ndim < 3:
    mask_img_med = mask_img_med[..., np.newaxis]
kid_mask = np.logical_or(mask_img_cor, mask_img_med)
kid_mask_all = np.sum(kid_mask, axis=2)

labelled = skimage.measure.label(kid_mask_all)
props = skimage.measure.regionprops(labelled)

# remove any small blobs
smallblob_thresh = round((kid_mask_all.shape[0]/20)**2)
for region in props:
    if np.sum(kid_mask_all[labelled == region.label]) < smallblob_thresh:
        kid_mask_all[labelled == region.label] = 0

# remove any central blobs
for region in props:
    if region.centroid[0] < kid_mask_all.shape[0]*7/12 and region.centroid[0] > kid_mask_all.shape[0]*5/12:
        kid_mask_all[labelled == region.label] = 0

# remove any blobs around the edge
for region in props:
    if (region.centroid[1] < kid_mask_all.shape[0]/4 or
        region.centroid[1] > kid_mask_all.shape[0]*3/4 or
        region.centroid[0] < kid_mask_all.shape[1]/6 or
        region.centroid[0] > kid_mask_all.shape[1]*5/6):
        kid_mask_all[labelled == region.label] = 0

# apply new mask to oroginal mask to exclude extra blobs    
kid_mask_all = kid_mask_all[..., np.newaxis]
mask_img_cor_new = mask_img_cor * kid_mask_all
mask_img_med_new = mask_img_med * kid_mask_all

# save cleaned masks
nii_cortex_new = nib.Nifti1Image(mask_img_cor_new, None, nii_cortex.header)
nii_cortex_new.to_filename("cortex_new_py.nii.gz")

nii_med_new = nib.Nifti1Image(mask_img_med_new, None, nii_medulla.header)
nii_med_new.to_filename("medulla_new_py.nii.gz")
