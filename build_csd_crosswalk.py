"""
Match every census subdivision, from 2001 onward, to its 2021 classification:
one of the 41 CMAs, 111 CAs, or 5 metropolitan influenced zones.

Method
------
Dissemination blocks are the finest census unit and nest inside both CSDs and
CMAs.  Each census publishes a block correspondence file linking its blocks to
the previous census's blocks, so blocks can be chained forward:

    2006 blocks -> 2011 -> 2016 -> 2021 -> 2021 CMA/CA/MIZ

Each vintage's Geographic Attribute File says which CSD its blocks belonged
to, so a CSD of any year decomposes into blocks, and those blocks carry it
forward.  Weights are that year's block population, so the answer reflects
where the people actually were.

2001 has no attribute file and is handled separately, from boundary polygons.

Outputs (output/)
    csd_to_cma2021.csv          one row per CSD-year   <- the deliverable
    csd_to_cma2021_long.csv     every CSD-year -> CMA share, for auditing
"""

from pathlib import Path
import numpy as np
import pandas as pd

from names import english

DATA, OUTPUT = Path("data"), Path("output")
OUTPUT.mkdir(exist_ok=True)
ENC = "latin1"

# CMATYPE codes.  B is a census metropolitan area, D and K are census
# agglomerations, and G/H/I/J are the metropolitan influenced zones.
GROUP = {"B": "a_CMA", "D": "b_CA", "K": "b_CA",
         "G": "c_MIZ", "H": "c_MIZ", "I": "c_MIZ", "J": "c_MIZ"}
MIZ_LABEL = {"996": "Strong MIZ", "997": "Moderate MIZ", "998": "Weak MIZ",
             "999": "No MIZ", "000": "Territories outside CAs"}


def load_2021():
    """2021 block -> CSD and its CMA/CA/MIZ classification."""
    g = pd.read_csv(
        DATA / "2021_92-151_X.csv", encoding=ENC, dtype=str,
        usecols=["DBUID_IDIDU", "CSDUID_SDRIDU", "CMAUID_RMRIDU",
                 "CMANAME_RMRNOM", "CMATYPE_RMRGENRE",
                 "DARPLAT_ADLAT", "DARPLONG_ADLONG"],
    ).rename(columns={"DBUID_IDIDU": "db21", "CSDUID_SDRIDU": "csd21",
                      "CMAUID_RMRIDU": "cma", "CMANAME_RMRNOM": "cma_name",
                      "CMATYPE_RMRGENRE": "cma_type",
                      "DARPLAT_ADLAT": "lat", "DARPLONG_ADLONG": "lon"})
    for c in ("lat", "lon"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g["cma_name"] = english(g.cma_name)
    return g


def load_link(path, cur, prev, header):
    """Block correspondence: current-census block -> previous-census block.

    The zipped releases also carry the reference guide as a PDF, so the data
    member has to be picked out rather than handing the archive to pandas.
    """
    path = Path(path)
    if path.suffix == ".zip":
        import zipfile
        z = zipfile.ZipFile(path)
        member = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
        src = z.open(member)
    else:
        src = path
    df = pd.read_csv(src, encoding=ENC, dtype=str,
                     header=0 if header else None, usecols=[0, 1])
    df.columns = [cur, prev]
    return df.drop_duplicates()


def load_slim(path, year):
    df = pd.read_csv(path, dtype=str)
    df.columns = [f"db{year}", "pop", "area", f"csd{year}"]
    df["pop"] = pd.to_numeric(df["pop"], errors="coerce").fillna(0)
    return df[[f"db{year}", f"csd{year}", "pop"]]


def chain(slim, year, links, g21, block_col, csd_col):
    """Carry one vintage's blocks forward to 2021 and attach the CMA."""
    df = slim
    for left, right, tbl in links:
        df = df.merge(tbl, left_on=left, right_on=left, how="left")

    # Over several hops the same source block can reach the same 2021 block by
    # more than one intermediate path -- e.g. a 2011 block split into two 2016
    # blocks that were merged back together by 2021.  Those duplicate rows must
    # collapse before weighting, or the block's population is counted twice.
    # dict.fromkeys de-duplicates: for 2021 the source block column *is* db21
    keep = [c for c in dict.fromkeys((block_col, csd_col, "pop", "db21"))
            if c in df.columns]
    df = df[keep].drop_duplicates(subset=[block_col, "db21"])

    df = df.merge(g21, left_on="db21", right_on="db21", how="left")

    # a block that lands in several 2021 blocks splits its population evenly
    n = df.groupby(block_col)["db21"].transform("nunique").clip(lower=1)
    df["w"] = df["pop"] / n

    pairs = (df.groupby([csd_col, "cma", "cma_name", "cma_type"],
                        as_index=False)["w"].sum()
               .rename(columns={csd_col: "csd"}))

    # Population-weighted centroid of the CSD's territory as it stands in 2021.
    # This is the origin point used later for nearest-core-city distance.
    d = df.dropna(subset=["lat", "lon"]).copy()
    d["ww"] = d["w"].where(d["w"] > 0, 0.0)
    grp = d.groupby(csd_col)
    cen = pd.DataFrame({
        "lat": grp.apply(lambda x: (x.lat * x.ww).sum() / x.ww.sum()
                         if x.ww.sum() > 0 else x.lat.mean()),
        "lon": grp.apply(lambda x: (x.lon * x.ww).sum() / x.ww.sum()
                         if x.ww.sum() > 0 else x.lon.mean()),
    }).reset_index().rename(columns={csd_col: "csd"})
    pairs = pairs.merge(cen, on="csd", how="left")
    pairs["year"] = year
    total = pairs.groupby("csd")["w"].transform("sum")
    share = pairs.w / total.where(total > 0)

    # Some CSDs have no population at all -- parks, unpopulated subdivisions --
    # so there is nothing to weight by.  That is not low confidence.  If such a
    # CSD maps to a single 2021 area the share is 1.0 by definition; if it
    # splits, population cannot resolve it and the share is left blank rather
    # than reported as zero, which would read as "unreliable".
    n_dest = pairs.groupby("csd")["csd"].transform("size")
    pairs["share"] = share.where(total > 0,
                                 np.where(n_dest == 1, 1.0, np.nan))
    return pairs


def main():
    print("Reading 2021 attribute file...")
    g21 = load_2021()

    print("Reading block correspondence files...")
    l21 = load_link(DATA / "2021_92-156-X_DB_ID.csv", "db21", "db2016", True)
    l16 = load_link(DATA / "2016_92-156_DB_ID_txt.zip", "db2016", "db2011", True)
    l11 = load_link(DATA / "2011_92-156_DB_ID_txt.zip", "db2011", "db2006", False)
    for nm, t in [("2021<->2016", l21), ("2016<->2011", l16), ("2011<->2006", l11)]:
        print(f"   {nm}: {len(t):,} links")

    # each vintage needs the hops between itself and 2021
    plans = {
        2021: (None, [], "db21", "csd21"),
        2016: (DATA / "_gaf2016_slim.csv", [("db2016", "db21", l21)],
               "db2016", "csd2016"),
        2011: (DATA / "_gaf2011_slim.csv", [("db2011", "db2016", l16),
                                            ("db2016", "db21", l21)],
               "db2011", "csd2011"),
        2006: (DATA / "_gaf2006_slim.csv", [("db2006", "db2011", l11),
                                            ("db2011", "db2016", l16),
                                            ("db2016", "db21", l21)],
               "db2006", "csd2006"),
    }

    out = []
    for year in (2021, 2016, 2011, 2006):
        path, links, block_col, csd_col = plans[year]
        print(f"\nChaining {year} -> 2021 ...")
        if year == 2021:
            g = pd.read_csv(DATA / "2021_92-151_X.csv", encoding=ENC, dtype=str,
                            usecols=["DBUID_IDIDU", "DBPOP2021_IDPOP2021"]
                            ).rename(columns={"DBUID_IDIDU": "db21",
                                              "DBPOP2021_IDPOP2021": "pop"})
            g["pop"] = pd.to_numeric(g["pop"], errors="coerce").fillna(0)
            slim = g
        else:
            slim = load_slim(path, year)
        pairs = chain(slim, year, links, g21, block_col, csd_col)
        print(f"   {pairs.csd.nunique():,} CSDs -> {len(pairs):,} CSD/CMA pairs")
        out.append(pairs)

    long = pd.concat(out, ignore_index=True)
    long["group"] = long.cma_type.map(GROUP)
    long["miz_class"] = long.cma.map(MIZ_LABEL).fillna("")
    long.to_csv(OUTPUT / "csd_to_cma2021_long.csv", index=False,
                encoding="utf-8-sig", float_format="%.6f")

    best = (long.sort_values(["year", "csd", "share", "cma"],
                             ascending=[True, True, False, True])
                .groupby(["year", "csd"], as_index=False).first())
    n_links = long.groupby(["year", "csd"]).size().rename("n_cma_links")
    best = best.merge(n_links, on=["year", "csd"])
    best = best.rename(columns={"share": "confidence"})

    cols = ["csd", "year", "group", "cma", "cma_name", "cma_type",
            "miz_class", "confidence", "n_cma_links", "lat", "lon"]
    best[cols].to_csv(OUTPUT / "csd_to_cma2021.csv", index=False,
                      encoding="utf-8-sig", float_format="%.6f")

    print("\n--- CSD-years by group ---")
    t = best.groupby(["year", "group"]).size().unstack(fill_value=0)
    print(t.to_string())
    print(f"\nwrote output/csd_to_cma2021.csv ({len(best):,} CSD-years)")


if __name__ == "__main__":
    main()
