"""
For CSD-years in group (c) -- those in a metropolitan influenced zone rather
than a CMA or CA -- find the nearest CMA or CA and record the distance.

Distance is measured to the *core city*: the population-weighted centre of the
most populous census subdivision inside each CMA/CA.  See README for why this
was chosen over the CMA boundary or its geometric centroid.

Distances are straight-line, computed in Statistics Canada Lambert (EPSG:3347)
so the units are true metres.  Road travel time is a later addition.
"""

from pathlib import Path
import warnings

import geopandas as gpd
import pandas as pd

from names import english
from shapely.geometry import Point

warnings.filterwarnings("ignore")
DATA, OUTPUT = Path("data"), Path("output")


def core_cities():
    """Population-weighted centre of the largest CSD in each CMA/CA."""
    g = pd.read_csv(DATA / "2021_92-151_X.csv", encoding="latin1", dtype=str,
                    usecols=["CSDUID_SDRIDU", "CSDNAME_SDRNOM", "CMAUID_RMRIDU",
                             "CMANAME_RMRNOM", "CMATYPE_RMRGENRE",
                             "DBPOP2021_IDPOP2021", "DARPLAT_ADLAT",
                             "DARPLONG_ADLONG"]
                    ).rename(columns={"CSDUID_SDRIDU": "csd",
                                      "CSDNAME_SDRNOM": "csd_name",
                                      "CMAUID_RMRIDU": "cma",
                                      "CMANAME_RMRNOM": "cma_name",
                                      "CMATYPE_RMRGENRE": "cma_type",
                                      "DBPOP2021_IDPOP2021": "pop",
                                      "DARPLAT_ADLAT": "lat",
                                      "DARPLONG_ADLONG": "lon"})
    for c in ("pop", "lat", "lon"):
        g[c] = pd.to_numeric(g[c], errors="coerce")
    g = g.dropna(subset=["lat", "lon"])
    g = g[g.cma_type.isin(["B", "D", "K"])]          # CMAs and CAs only

    g["plat"], g["plon"] = g.lat * g["pop"], g.lon * g["pop"]
    by_csd = g.groupby(["cma", "cma_name", "cma_type", "csd", "csd_name"],
                       as_index=False).agg(pop=("pop", "sum"),
                                           plat=("plat", "sum"),
                                           plon=("plon", "sum"),
                                           mlat=("lat", "mean"),
                                           mlon=("lon", "mean"))
    by_csd["lat"] = (by_csd.plat / by_csd["pop"]).fillna(by_csd.mlat)
    by_csd["lon"] = (by_csd.plon / by_csd["pop"]).fillna(by_csd.mlon)

    core = (by_csd.sort_values(["cma", "pop"], ascending=[True, False])
                  .groupby("cma", as_index=False).first())
    core["cma_name"] = english(core.cma_name)
    core["csd_name"] = english(core.csd_name)
    return core


def main():
    core = core_cities()
    print(f"core cities identified: {len(core)}")
    print(core.nlargest(4, "pop")[["cma", "cma_name", "csd_name", "pop"]]
              .to_string(index=False))

    cw = pd.read_csv(OUTPUT / "csd_to_cma2021.csv", dtype={"csd": str, "cma": str})
    for c in ("lat", "lon"):
        cw[c] = pd.to_numeric(cw[c], errors="coerce")

    gc = cw[(cw.group == "c_MIZ") & cw.lat.notna()].copy()
    print(f"\ngroup (c) CSD-years to place: {len(gc):,} "
          f"(missing coordinates: {(cw.group == 'c_MIZ').sum() - len(gc):,})")

    src = gpd.GeoDataFrame(gc[["csd", "year"]],
                           geometry=[Point(xy) for xy in zip(gc.lon, gc.lat)],
                           crs=4326).to_crs(3347)
    dst = gpd.GeoDataFrame(core[["cma", "cma_name", "cma_type", "csd_name"]],
                           geometry=[Point(xy) for xy in zip(core.lon, core.lat)],
                           crs=4326).to_crs(3347)

    near = gpd.sjoin_nearest(src, dst, how="left", distance_col="metres")
    near = near.drop_duplicates(subset=["csd", "year"])
    near["nearest_km"] = (near.metres / 1000).round(2)

    add = near[["csd", "year", "cma", "cma_name", "cma_type", "csd_name",
                "nearest_km"]].rename(columns={
        "cma": "nearest_cma", "cma_name": "nearest_cma_name",
        "cma_type": "nearest_cma_type", "csd_name": "nearest_core_city"})

    out = cw.merge(add, on=["csd", "year"], how="left")
    cols = ["csd", "year", "group", "cma", "cma_name", "cma_type", "miz_class",
            "confidence", "n_cma_links", "method", "lat", "lon",
            "nearest_cma", "nearest_cma_name", "nearest_cma_type",
            "nearest_core_city", "nearest_km"]
    out[cols].to_csv(OUTPUT / "csd_to_cma2021.csv", index=False,
                     encoding="utf-8-sig", float_format="%.6f")

    print(f"\ndistance to nearest core city, group (c):")
    d = out.loc[out.group == "c_MIZ", "nearest_km"]
    for q in (0.25, 0.5, 0.75, 0.9, 0.99):
        print(f"   {int(q*100):>2}th percentile {d.quantile(q):8.1f} km")
    print(f"   max            {d.max():8.1f} km")
    print(f"\nwrote output/csd_to_cma2021.csv ({len(out):,} CSD-years)")


if __name__ == "__main__":
    main()
