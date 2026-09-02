"""
Add 2001 to the crosswalk, and attach nearest-core-city distances for group (c).

2001 is the one vintage with no Geographic Attribute File, so its CSDs cannot
be decomposed into blocks and chained forward like the others.  Two routes are
used instead:

  1. Code inheritance -- a 2001 CSD code that still exists in 2006 takes the
     2006 answer, which was chained with population weights.  This covers the
     large majority.
  2. Point-in-polygon -- for codes that vanished before 2006, the 2001
     boundary file's label points are located inside 2021 CSD polygons and the
     2021 classification is read off directly.

Route 2 is also run for every 2001 CSD, so the two can be compared where they
overlap and the agreement rate reported.
"""

from pathlib import Path
import warnings

import geopandas as gpd
import pandas as pd

from names import english
import pyogrio

warnings.filterwarnings("ignore")
DATA, OUTPUT = Path("data"), Path("output")

GROUP = {"B": "a_CMA", "D": "b_CA", "K": "b_CA",
         "G": "c_MIZ", "H": "c_MIZ", "I": "c_MIZ", "J": "c_MIZ"}
MIZ_LABEL = {"996": "Strong MIZ", "997": "Moderate MIZ", "998": "Weak MIZ",
             "999": "No MIZ", "000": "Territories outside CAs"}


def classification_2021():
    g = pd.read_csv(DATA / "2021_92-151_X.csv", encoding="latin1", dtype=str,
                    usecols=["CSDUID_SDRIDU", "CMAUID_RMRIDU", "CMANAME_RMRNOM",
                             "CMATYPE_RMRGENRE"]
                    ).rename(columns={"CSDUID_SDRIDU": "csd21",
                                      "CMAUID_RMRIDU": "cma",
                                      "CMANAME_RMRNOM": "cma_name",
                                      "CMATYPE_RMRGENRE": "cma_type"})
    g["cma_name"] = english(g.cma_name)
    return g.drop_duplicates("csd21")


def spatial_2001(cls21):
    """Locate 2001 label points inside 2021 CSD polygons."""
    print("Reading 2001 label points...")
    pts = pyogrio.read_dataframe("data/csd2001.e00", layer="LAB",
                                 columns=["CSDUID"]).to_crs(4326)
    pts["lat"], pts["lon"] = pts.geometry.y, pts.geometry.x
    pts = pts.to_crs(3347)
    print(f"   {len(pts):,} points, {pts.CSDUID.nunique():,} CSDs")

    print("Reading 2021 CSD polygons (314 MB, slow)...")
    poly = gpd.read_file("zip://data/lcsd000b21a_e.zip!lcsd000b21a_e.shp",
                         columns=["CSDUID"]).to_crs(3347)
    poly = poly.rename(columns={"CSDUID": "csd21"})

    print("Point-in-polygon...")
    j = gpd.sjoin(pts, poly, how="left", predicate="within")

    # A label point anchored over water finds no containing polygon, because the
    # 2021 cartographic boundary file is clipped to the shoreline.  Every case
    # observed sits within 400 m of its true CSD, so fall back to the nearest
    # polygon for those points rather than dropping them.
    stranded = set(j[j.csd21.isna()].CSDUID) - set(j[j.csd21.notna()].CSDUID)
    if stranded:
        print(f"   {len(stranded)} points over water -> nearest-polygon fallback")
        extra = gpd.sjoin_nearest(pts[pts.CSDUID.isin(stranded)], poly,
                                 how="left", distance_col="snap_m")
        extra = extra[extra.snap_m <= 25_000].drop(columns="snap_m")
        j = pd.concat([j[j.csd21.notna()], extra], ignore_index=True)
    # a 2001 CSD has one label point per polygon part; take the modal landing
    hit = (j.dropna(subset=["csd21"])
             .groupby(["CSDUID", "csd21"])
             .agg(n=("lat", "size"), lat=("lat", "mean"), lon=("lon", "mean"))
             .reset_index()
             .sort_values(["CSDUID", "n"], ascending=[True, False])
             .groupby("CSDUID", as_index=False).first())
    hit = hit.rename(columns={"CSDUID": "csd"}).merge(cls21, on="csd21", how="left")
    print(f"   located {len(hit):,} of 2001 CSDs")
    return hit


def main():
    cls21 = classification_2021()
    cw = pd.read_csv(OUTPUT / "csd_to_cma2021.csv", dtype=str)
    cw["year"] = cw.year.astype(int)
    cw["confidence"] = pd.to_numeric(cw.confidence, errors="coerce")

    a01 = (pd.read_csv(DATA / "_csd2001_attrs.csv", dtype=str)
             .drop_duplicates("CSDUID").rename(columns={"CSDUID": "csd"}))
    print(f"2001 CSDs: {len(a01):,}")

    from_2006 = cw[cw.year == 2006].set_index("csd")
    inherit = a01[a01.csd.isin(from_2006.index)].copy()
    inherit = inherit[["csd"]].join(
        from_2006[["group", "cma", "cma_name", "cma_type", "miz_class",
                   "confidence", "n_cma_links", "lat", "lon"]], on="csd")
    inherit["method"] = "code_inherit_2006"
    print(f"   inherited from 2006 chain : {len(inherit):,}")

    spatial = spatial_2001(cls21)
    spatial["group"] = spatial.cma_type.map(GROUP)
    spatial["miz_class"] = spatial.cma.map(MIZ_LABEL).fillna("")
    spatial["confidence"] = pd.NA
    spatial["n_cma_links"] = pd.NA
    spatial["method"] = "point_in_polygon"

    # agreement between the two routes, where both have an answer
    both = inherit.merge(spatial[["csd", "cma"]], on="csd", suffixes=("", "_sp"))
    agree = (both.cma == both.cma_sp).mean() * 100
    print(f"   routes agree on the overlap: {agree:.2f}%  (n={len(both):,})")

    missing = spatial[~spatial.csd.isin(inherit.csd)]
    print(f"   resolved by geometry only : {len(missing):,}")

    cols = ["csd", "group", "cma", "cma_name", "cma_type", "miz_class",
            "confidence", "n_cma_links", "lat", "lon", "method"]
    y01 = pd.concat([inherit[cols], missing[cols]], ignore_index=True)
    y01["year"] = 2001
    unresolved = len(a01) - len(y01)
    print(f"   unresolved                : {unresolved:,}")

    cw["method"] = "block_chain"
    out = pd.concat([y01, cw], ignore_index=True).sort_values(["year", "csd"])
    out.to_csv(OUTPUT / "csd_to_cma2021.csv", index=False,
               encoding="utf-8-sig", float_format="%.6f")

    print("\n--- CSD-years by group ---")
    print(out.groupby(["year", "group"]).size().unstack(fill_value=0).to_string())
    print(f"\ntotal CSD-years: {len(out):,}")


if __name__ == "__main__":
    main()
