"""
Attach the census subdivision's name and type to each CSD-year.

Names are taken from **that year's** source, not from 2021.  Municipalities are
renamed, amalgamated and re-typed between censuses -- 84 codes change name
between 2006 and 2016 alone -- so stamping the modern name onto an old code
would misrepresent the record.

Sources, one per vintage:
    2001  label points from the 2001 boundary file (no attribute file exists)
    2006  gcsd000b06a_e boundary file
    2011  gcsd000b11a_e boundary file
    2016  lcsd000b16a_e boundary file
    2021  lcsd000b21a_e boundary file

Only the attribute tables are read; the geometry is skipped, so this is fast.
"""

from pathlib import Path
import warnings

import pandas as pd

from names import english
import pyogrio

warnings.filterwarnings("ignore")
DATA, OUTPUT = Path("data"), Path("output")

SHAPES = {
    2006: ("zip://data/gcsd000b06a_e.zip!gcsd000b06a_e.shp", ["CSDUID", "CSDNAME", "CSDTYPE"]),
    2011: ("zip://data/gcsd000b11a_e.zip!gcsd000b11a_e.shp", ["CSDUID", "CSDNAME", "CSDTYPE"]),
    2016: ("zip://data/lcsd000b16a_e.zip!lcsd000b16a_e.shp", ["CSDUID", "CSDNAME", "CSDTYPE"]),
    2021: ("zip://data/lcsd000b21a_e.zip!lcsd000b21a_e.shp", ["CSDUID", "CSDNAME", "CSDTYPE"]),
}


def names_for_year(year):
    if year == 2001:
        d = pd.read_csv(DATA / "_csd2001_attrs.csv", dtype=str)[
            ["CSDUID", "CSDNAME", "CSDTYPE"]]
    else:
        path, cols = SHAPES[year]
        d = pyogrio.read_dataframe(path, columns=cols, read_geometry=False)
    # Rename by name, never by position: both pandas `usecols` and pyogrio
    # `columns` return the file's own column order, not the requested one.
    d = (d.dropna(subset=["CSDUID"]).drop_duplicates("CSDUID")
          .rename(columns={"CSDUID": "csd", "CSDNAME": "csd_name",
                           "CSDTYPE": "csd_type"}))
    d = d[["csd", "csd_name", "csd_type"]]
    # a few sources carry bilingual names joined by " / "
    d["csd_name"] = english(d.csd_name)
    d["year"] = year
    return d


def main():
    cw = pd.read_csv(OUTPUT / "csd_to_cma2021.csv",
                     dtype={"csd": str, "cma": str, "nearest_cma": str,
                            "drive_nearest_cma": str})
    cw = cw.drop(columns=[c for c in ("csd_name", "csd_type") if c in cw.columns])

    frames = []
    for year in (2001, 2006, 2011, 2016, 2021):
        d = names_for_year(year)
        print(f"{year}: {len(d):,} names")
        frames.append(d)
    names = pd.concat(frames, ignore_index=True)

    out = cw.merge(names, on=["csd", "year"], how="left")

    missing = out.csd_name.isna().sum()
    print(f"\nCSD-years without a name: {missing:,} of {len(out):,}")
    if missing:
        print(out[out.csd_name.isna()].groupby("year").size().to_string())

    cols = list(out.columns)
    for c in ("csd_name", "csd_type"):
        cols.remove(c)
    i = cols.index("year") + 1
    cols = cols[:i] + ["csd_name", "csd_type"] + cols[i:]
    target = OUTPUT / "csd_to_cma2021.csv"
    try:
        out[cols].to_csv(target, index=False, encoding="utf-8-sig",
                         float_format="%.6f")
    except PermissionError:
        target = OUTPUT / "csd_to_cma2021_named.csv"
        out[cols].to_csv(target, index=False, encoding="utf-8-sig",
                         float_format="%.6f")
        print("NOTE: csd_to_cma2021.csv is locked (open in Excel?)")

    print("\nsample:")
    print(out[out.csd == "3524009"][["csd", "year", "csd_name", "csd_type",
                                     "cma_name"]].to_string(index=False))
    print(f"\nwrote {target}")


if __name__ == "__main__":
    main()
