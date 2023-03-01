"""
Generate subject IDPs in TSV format from output of DEMISTIFI pipeline
"""
import argparse
import os

import pandas as pd

class ArgumentParser(argparse.ArgumentParser):
    def __init__(self, **kwargs):
        argparse.ArgumentParser.__init__(self, prog="demistifi-ukb-pipeline", add_help=True, **kwargs)
        self.add_argument("--input", required=True, help="Input directory containing subject dirs")
        self.add_argument("--output", help="Output filename", default="demistifi_idps.csv")

IDP_DEF = {
    "liver_dixon_stats" : {
        "rows" : ["Mean", "Std"],
        "prefix" : "liver_dixon_",
    },
    "seg_volumes" : {
        "rows" : {
            "Num voxels" : "n",
            "Volume (mm^3)" : "vol"
        }
    }
}

def main():
    options = ArgumentParser().parse_args()
    subjids = [f for f in os.listdir(options.input) if os.path.isdir(os.path.join(options.input, f))]
    
    # In the IDP definitions, if rows or cols is not specified for a table that means
    # 'all rows/cols'. So first we need to go through every table and get a complete
    # list of all known rows/cols
    for subjid in subjids:
        idp_def_autogen = {}
        for table, idpdef in IDP_DEF.items():
            if "rows" in idpdef and "cols" in idpdef:
                continue
            if table not in idp_def_autogen:
                idp_def_autogen[table] = {}
            tsv_fname = os.path.join(options.input, subjid, f"{table}.tsv")
            if os.path.exists(tsv_fname):
                df = pd.read_csv(tsv_fname, sep="\t", index_col=0)
                if "rows" not in idpdef:
                    cur = idp_def_autogen[table].get("rows", [])
                    new = list(set(cur + list(df.index)))
                    idp_def_autogen[table]["rows"] = new
                if "cols" not in idpdef:
                    cur = idp_def_autogen[table].get("cols", [])
                    new = list(set(cur + list(df.columns)))
                    idp_def_autogen[table]["cols"] = new
    for table, idpdef in idp_def_autogen.items():
        if "rows" not in IDP_DEF[table]:
            IDP_DEF[table]["rows"] = idp_def_autogen[table]["rows"]
        if "cols" not in IDP_DEF[table]:
            IDP_DEF[table]["cols"] = idp_def_autogen[table]["cols"]
    
    # Now we actually generate the IDPs for each subject, understanding
    # that the required cols/rows or the table itself may be missing for some subjects
    out_idpcols, out_idplist = ["subjid",], []
    for idx, subjid in enumerate(subjids):
        print(subjid)
        subj_IDP_DEF = [subjid,]
        for table, idpdef in IDP_DEF.items():
            tsv_fname = os.path.join(options.input, subjid, f"{table}.tsv")
            if os.path.exists(tsv_fname):
                df = pd.read_csv(tsv_fname, sep="\t", index_col=0)
            else:
                df = pd.DataFrame()
            rows, cols = idpdef["rows"], idpdef["cols"]
            for col in cols:
                for row in rows:
                    if col in df.columns and row in df.index:
                        subj_IDP_DEF.append(str(df[col][row]))
                    else:
                        subj_IDP_DEF.append("")
                    if idx == 0:
                        if isinstance(rows, dict):
                            out_row_name = rows[row].strip()
                        else:
                            out_row_name = row.strip()
                        idp_name = idpdef.get("prefix", "") + col.strip() + "_" + out_row_name.replace(" ", "_").lower()
                        out_idpcols.append(idp_name)
        out_idplist.append(subj_IDP_DEF)

    df_out = pd.DataFrame(out_idplist, columns=out_idpcols)
    df_out.set_index("subjid", inplace=True)
    print(df_out)
    df_out.to_csv(options.output)

if __name__ == "__main__":
    main()