# Script to combine PNG output of renal preproc into a more convenient format for review
#
# Usage: img_summarise <indir> <outdir>
import glob
import os
import shutil
import sys

def collate_pngs(subjid, subjdir, outdir):
    for root, dirs, files in os.walk(subjdir):
        for f in files:
            if f.endswith(".png"):
                fpath = os.path.join(root, f)
                to_fname = subjid + "_" + f
                print(outdir, fpath, to_fname)
                shutil.copyfile(fpath, os.path.join(outdir, to_fname))

    #for fname in glob.glob(os.path.join(subjdir, "*/*.png")):
    #    basename = os.path.basename(fname)
    #    outname = os.path.join(outdir, f"{subjid}_{basename}")
    #    shutil.copyfile(fname, outname)

indir = sys.argv[1]
outdir = sys.argv[2]
if len(sys.argv) == 4:
    renalpath = sys.argv[3]
else:
    renalpath = ""

os.makedirs(outdir, exist_ok=True)

subjids = os.listdir(indir)
print(f"Found {len(subjids)} in {indir}")

for subjid in subjids:
    subjdir = os.path.join(indir, subjid, renalpath)
    if not os.path.isdir(subjdir):
        continue
    print(f" - Subject {subjid}")
    if not os.path.exists(os.path.join(subjdir, "nifti")):
        print(" - Looks like this one has multiple sessions")
        sessions = os.listdir(subjdir)
        for session in sessions:
            print(f"   - Session {session}")
            sessdir = os.path.join(subjdir, session)
            collate_pngs(f"{subjid}_{session}", sessdir, outdir)
    else:
        collate_pngs(subjid, subjdir, outdir)
