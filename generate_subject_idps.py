"""
Generate subject IDPs in TSV format from output of DEMISTIFI pipeline
"""
import argparse
import csv
import logging
import os
import sys

import pandas as pd

LOG = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)

MEAN_PARAM="Interquartile mean"
#MEAN_PARAM="Mean"
STD_PARAM="Interquartile STD"
#MEAN_PARAM="Std"

class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        argparse.ArgumentParser.__init__(self, prog="demistifi-ukb-pipeline", add_help=True, **kwargs)
        self.add_argument("--input", required=True, help="Input directory containing subject dirs")
        self.add_argument("--statspath", help="Subject dir subfolder containing stats", default="stats")
        self.add_argument("--output", help="Output filename", default="demistifi_idps.csv")


# IDP definition. Mapping from:
#  - organ -> segmentation name
#  - segmentation name -> grid dataset
#  - grid dataset -> Sequence of tuples of (parameter, method)
#
# If grid dataset is empty, assumed to be same as segmentation grid
#
# Segmentation datasets follow naming convention:
#    seg_<organ>_<segmentation name>  (e.g. seg_liver_dixon)
#
# Re-gridded segmentations follow naming convention:
#    seg_<organ>_<segmentation>_regrid_<grid dataset>  (e.g. seg_liver_dixon_regrid_pancreas_gre)
#
# Parameter maps follow naming convention
#    <variable>_<grid dataset>_[<method>] (e.g. t2star_pancreas_gre_presco)
#
# Note that parameters may be derived from maps targeting a particular
# organ but can also provide data for segmentations targeting a 
# different organ
#
# FIXME add all organ volumes from dixon (7) + pancreas t1w (1)
# FIXME remove loglin fit from liver
IDPDEF = {
    "liver" : {
        "dixon" : {
            "liver_molli" : [
                ("t1", "")
            ],
            #"pancreas_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
            #    ("t2star", "loglin"),
            #    ("r2star", "loglin"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            #],
            #"kidney_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
            #    ("t2star", "loglin"),
            #    ("r2star", "loglin"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            #],
            "" : [
            ] 
        },
        "ideal" : {
            "" : [
                ("t2star", "presco"),
                ("r2star", "presco"),
                ("iron", "presco"),
                ("pdff", "presco"),
            ],
        }
    },
    "pancreas" : {
        "t1w" : {
            "pancreas_molli" : [
                ("t1", "")
            ],
            "pancreas_gre" : [
                ("t2star", "presco"),
                ("r2star", "presco"),
                #("t2star", "loglin"),
                #("r2star", "loglin"),
                ("iron", "presco"),
                ("pdff", "presco"),
            ],
            "" : [
                ("fat_fraction", ""),
            ]
        }
    },
    "spleen" : {
        "dixon" : {
            "liver_molli" :  [
                ("t1", "")
            ],
            "liver_ideal" : [
                ("t2star", "presco"),
                ("r2star", "presco"),
                ("iron", "presco"),
                ("pdff", "presco"),
            ],
            "kidney_molli" : [
                ("t1", "")
            ],
            "kidney_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
                ("t2star", "loglin"),
                ("r2star", "loglin"),
                ("t2star", "exp"),
                ("r2star", "exp"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            ],
            "" : [
                ("fat_fraction", ""),
            ]
        },
    },
    "kidney_medulla_l" : {
        "t1" : {
            "" :  [
                ("t1", "")
            ],
            "kidney_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
                ("t2star", "loglin"),
                ("r2star", "loglin"),
                ("t2star", "exp"),
                ("r2star", "exp"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            ],
        }
    },
    "kidney_cortex_l" : {
        "t1" : {
            "" :  [
                ("t1", "")
            ],
            "kidney_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
                ("t2star", "loglin"),
                ("r2star", "loglin"),
                ("t2star", "exp"),
                ("r2star", "exp"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            ],
        }
    },
    "kidney_medulla_r" : {
        "t1" : {
            "" :  [
                ("t1", "")
            ],
            "kidney_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
                ("t2star", "loglin"),
                ("r2star", "loglin"),
                ("t2star", "exp"),
                ("r2star", "exp"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            ],
        }
    },
    "kidney_cortex_r" : {
        "t1" : {
            "" :  [
                ("t1", "")
            ],
            "kidney_gre" : [
            #    ("t2star", "presco"),
            #    ("r2star", "presco"),
                ("t2star", "loglin"),
                ("r2star", "loglin"),
                ("t2star", "exp"),
                ("r2star", "exp"),
            #    ("iron", "presco"),
            #    ("pdff", "presco"),
            ],
        }
    },
    "kidney_all" : {
        "t1" : {
            "" : [
                ("fat_fraction", ""),
            ] 
        }
    },
    "lungs" : {
        "dixon" : {
            "" : []
        }
    },
#    "spleen" : {
#        "dixon" : {
#            "" : []
#        }
#    },
#    "liver" : {
#        "dixon" : {
#            "" : []
#        }
#    },
    "kidney_left" : {
        "dixon" : {
            "" : []
        }
    },
    "kidney_right" : {
        "dixon" : {
            "" : []
        }
    },
    "kidney" : {
        "dixon" : {
            "" : []
        }
    },
    "vat" : {
        "dixon" : {
            "" : [
                ("fat_fraction", ""),
            ] 
        }
    },
    "asat" : {
        "dixon" : {
            "" : [
                ("fat_fraction", ""),
            ] 
        }
    },
#    "subcutaneous_fat" : {
#        "dixon" : {
#            "" : []
#        }
#    },
}

def get_seg_vols(options, subjid):
    vols_tsv = os.path.join(options.input, subjid, options.statspath, "seg_volumes.tsv")
    LOG.debug(f"Looking for segmentation volumes for subject {subjid} in {vols_tsv}")
    if os.path.exists(vols_tsv):
        return pd.read_csv(vols_tsv, sep="\t", index_col=0)
    else:
        LOG.warning(f"No volumes file: {vols_tsv}")
        return pd.DataFrame()

def get_seg_vol(df, organ, seg, grid):
    col_name = f"seg_{organ}_{seg}"
    if grid:
        col_name += f"_regrid_{grid}"
    if col_name in list(df.columns):
        n, vol = df[col_name]
        if n == 0:
            return "", ""
        else:
            if organ in ("vat", "asat"):
                vol /= 1000.0
            return int(n), vol
    else:
        LOG.warning(f"No volume found for segmentation: {col_name}")
        return "", ""

def strip_repeats(col_names):
    new_col_names = []
    for idx, col_name in enumerate(col_names):
        if idx > 0 and col_names[idx-1] == col_name:
            new_col_names.append("")
        else:
            new_col_names.append(col_name)
    return new_col_names

def main():
    options = ArgumentParser().parse_args()
    subjids = [f for f in os.listdir(options.input) if os.path.isdir(os.path.join(options.input, f))]
    subjids = sorted(subjids)
    #subjids = ["1091670"]

    out_idpcols, out_idplist = ["subjid",], []
    organ_values, seg_values, grid_values, param_values, measure_values = [""], [""], [""], [""], ["subjid"]
    for subj_idx, subjid in enumerate(subjids):
        subj_idpvals = [subjid,]
        loaded_stats = {}
        seg_vols_df = get_seg_vols(options, subjid)
        LOG.info(f"Processing subject {subjid}")
        LOG.debug(f"Found segmentation volumes for {seg_vols_df.columns}")
        for organ, organdef in IDPDEF.items():
            LOG.debug(f"Organ: {organ}")
            for seg, segdef in organdef.items():
                LOG.debug(f"Segmentation: {seg} {segdef}")
                for grid, params in segdef.items():
                    LOG.debug(f"Grid: {grid}")
                    n, vol = get_seg_vol(seg_vols_df, organ, seg, grid)
                    if subj_idx == 0:
                        output_col_name = f"{organ}_{seg}_{grid}"
                        out_idpcols.append(output_col_name + "_n")
                        out_idpcols.append(output_col_name + "_vol")
                        measure_values.append("n")
                        measure_values.append("vol")
                        for i in range(2):
                            organ_values.append(organ)
                            seg_values.append(seg)
                            grid_values.append(grid)
                            param_values.append("mask")
                    subj_idpvals.append(n)
                    subj_idpvals.append(vol)
                    LOG.debug(f"N, volume: {n} {vol}")
                    for paramdef in params:
                        param, method = paramdef
                        LOG.debug(f"Parameter: {paramdef}")
                        stats_dataset = f"{organ}_{seg}_stats.tsv"
                        if stats_dataset not in loaded_stats:
                            stats_tsv = os.path.join(options.input, subjid, options.statspath, stats_dataset)
                            if os.path.exists(stats_tsv):
                                LOG.debug(f"Loading stats from: {stats_tsv}")
                                loaded_stats[stats_dataset] = pd.read_csv(stats_tsv, sep="\s*\t\s*", engine="python", index_col=0)
                            else:
                                LOG.warning(f"No stats file: {stats_tsv}")
                                loaded_stats[stats_dataset] = pd.DataFrame()
                        col_name = param
                        param_name = param
                        col_name_alt = col_name
                        if grid:
                            col_name += f"_{grid}"
                        else:
                            col_name += f"_{organ}_{seg}"
                        if method:
                            col_name += f"_{method}"
                            col_name_alt += f"_{method}"
                            param_name += f"_{method}"
                        LOG.debug(f"Looking for column: {col_name}")
                        if n and col_name in list(loaded_stats[stats_dataset].columns):
                            mean = loaded_stats[stats_dataset][col_name][MEAN_PARAM]
                            std = loaded_stats[stats_dataset][col_name][STD_PARAM]
                            median = loaded_stats[stats_dataset][col_name]["Median"]
                            mode = loaded_stats[stats_dataset][col_name]["Mode estimate"]
                            fwhm = loaded_stats[stats_dataset][col_name]["FWHM estimate"]
                        elif n and col_name_alt in list(loaded_stats[stats_dataset].columns):
                            LOG.debug(f"Using alt: {col_name_alt}")
                            mean = loaded_stats[stats_dataset][col_name_alt][MEAN_PARAM]
                            std = loaded_stats[stats_dataset][col_name_alt][STD_PARAM]
                            median = loaded_stats[stats_dataset][col_name_alt]["Median"]
                            mode = loaded_stats[stats_dataset][col_name_alt]["Mode estimate"]
                            fwhm = loaded_stats[stats_dataset][col_name_alt]["FWHM estimate"]
                        else:
                            LOG.debug(f"Not found: {col_name}")
                            mean, std, median, mode, fwhm = "", "", "", "", ""

                        if subj_idx == 0:
                            output_col_name = f"{organ}_{seg}_{col_name}"
                            out_idpcols.append(output_col_name + "_iqmean")
                            out_idpcols.append(output_col_name + "_iqstd")
                            out_idpcols.append(output_col_name + "_median")
                            measure_values.append("iqmean")
                            measure_values.append("iqstd")
                            measure_values.append("median")
                            if organ == "liver":
                                out_idpcols.append(output_col_name + "_mode")
                                out_idpcols.append(output_col_name + "_fwhm")
                                measure_values.append("mode")
                                measure_values.append("fwhm")

                            for i in range(3):
                                organ_values.append(organ)
                                seg_values.append(seg)
                                grid_values.append(grid)
                                param_values.append(param_name)
                        subj_idpvals.append(mean)
                        subj_idpvals.append(std)
                        subj_idpvals.append(median)
                        if organ == "liver":
                            subj_idpvals.append(mode)
                            subj_idpvals.append(fwhm)

        out_idplist.append(subj_idpvals)

    #df_out = pd.DataFrame(out_idplist, columns=out_idpcols)
    #df_out.set_index("subjid", inplace=True)
    #print(df_out)
    #df_out.to_csv(options.output)
    organ_values = strip_repeats(organ_values)
    seg_values = strip_repeats(seg_values)
    grid_values = strip_repeats(grid_values)
    param_values = strip_repeats(param_values)
    with open(options.output, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)
        writer.writerow(out_idpcols)
        writer.writerow(organ_values)
        writer.writerow(seg_values)
        writer.writerow(grid_values)
        writer.writerow(param_values)
        writer.writerow(measure_values)
        for subj_values in out_idplist:
            writer.writerow(subj_values)
            
if __name__ == "__main__":
    main()
