"""
Generate a report on data availability in processed data
"""
import os
import glob

import pandas as pd

BODY_SEG_DIR = "/share/ukbiobank/body_seg"

data_ids = {
    "pancreas_molli" : "shmolli_pancreas",
    "kidney_molli" : "shmolli_liver",
    "liver_molli" : "shmolli_liver",
    "pancreas_t2star" : "t2star_pancreas",
    "kidney_t2star" :  "t2star_kidney",
    "liver_t2star" : "t2star_liver", 
    "seg_pancreas" : "seg_pancreas_t1w", 
    "seg_liver" : "seg_liver_dixon",
    "seg_kidney" : "seg_kidney_left_dixon",
    "seg_spleen" : "seg_spleen_dixon",
    "liver_ideal" : "ideal_liver",
    #"pancreas_vibe" : "",
}

subjrows = []
totals = {d : 0 for d in data_ids.keys()}

for subjdir in glob.glob(os.path.join(BODY_SEG_DIR, "1*")):
    subjid = os.path.basename(subjdir)
    qpdir = os.path.join(subjdir, "qpdata")
    subjrow = {"subjid" : subjid}
    num_found = 0
    for data_id, qpfile in data_ids.items():
        try:
            fname = os.path.join(qpdir, f"{qpfile}.nii.gz")
            os.stat(fname)
            subjrow[data_id] = 1
            totals[data_id] += 1
            num_found += 1
        except OSError:
            subjrow[data_id] = 0
            #print(f"{subjid} missing {data_id}")
    subjrow["num_found"] = num_found
    subjrow["%"] = 100 * float(num_found) / len(data_ids)
    subjrows.append(subjrow)

subjrows.append(totals)
df = pd.DataFrame(subjrows)
df.to_csv("ukb_body_seg_report.csv")


