"""
Add road travel time to the nearest core city for group (c) CSD-years.

Straight-line distance ignores lakes, mountains and the absence of roads, all
of which matter in rural Canada.  This routes on the real road network and
records driving time, then re-ranks: the nearest core city by road is not
always the nearest in a straight line.

Routing uses the public OSRM demo server.  To keep that polite the work is
batched: origins are sorted so neighbours share candidate destinations, then
each request carries up to 100 origins against the union of their candidates.
Only the few nearest candidates per origin are routed, shortlisted by
straight-line distance, rather than all 152 CMAs and CAs.

Origins that snap to a road far from the CSD centroid are flagged: those are
communities with no road connection, where a driving time is meaningless.

    python add_travel_time.py [--limit N]
"""

import argparse
import json
import time
import urllib.error
import urllib.request
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import Point

warnings.filterwarnings("ignore")
OUTPUT, DATA = Path("output"), Path("data")

OSRM = "https://router.project-osrm.org/table/v1/driving/"
CANDIDATES = 4          # nearest core cities per origin, by straight line
MAX_SOURCES = 100       # origins per request
MAX_COORDS = 150        # server limit found by probing
PAUSE = 0.4             # seconds between requests
SNAP_LIMIT_KM = 20      # further than this from a road = treat as unreachable


def core_city_points():
    from add_core_city import core_cities
    core = core_cities()
    return core[["cma", "cma_name", "csd_name", "lat", "lon"]].reset_index(drop=True)


def shortlist(origins, core):
    """The CANDIDATES nearest core cities to each origin, by straight line."""
    o = gpd.GeoDataFrame(origins.copy(),
                         geometry=[Point(xy) for xy in zip(origins.lon, origins.lat)],
                         crs=4326).to_crs(3347)
    c = gpd.GeoDataFrame(core.copy(),
                         geometry=[Point(xy) for xy in zip(core.lon, core.lat)],
                         crs=4326).to_crs(3347)
    ox = np.c_[o.geometry.x.values, o.geometry.y.values]
    cx = np.c_[c.geometry.x.values, c.geometry.y.values]
    d = np.linalg.norm(ox[:, None, :] - cx[None, :, :], axis=2)
    idx = np.argsort(d, axis=1)[:, :CANDIDATES]
    return idx


def call_table(src, dst):
    """One OSRM table request. Returns durations matrix and source snap distances."""
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in src + dst)
    s = ";".join(str(i) for i in range(len(src)))
    t = ";".join(str(i + len(src)) for i in range(len(dst)))
    url = f"{OSRM}{coords}?sources={s}&destinations={t}&annotations=duration"
    req = urllib.request.Request(url, headers={"User-Agent": "csd-crosswalk/1.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=120) as r:
                j = json.load(r)
            if j.get("code") != "Ok":
                return None, None
            snap = [w.get("distance") for w in j.get("sources", [])]
            return j["durations"], snap
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            time.sleep(2 * (attempt + 1))
    return None, None


def add_speed_columns(out, core):
    """Straight-line distance to the routed city, and the speed it implies.

    This must measure to the city that was **actually routed to**, not to the
    straight-line-nearest one.  Those differ wherever road routing re-ranks the
    destination -- about one rural CSD-year in six -- and dividing the distance
    to one city by the driving time to another gives a meaningless figure.
    """
    idx = core.set_index("cma")[["lat", "lon"]].rename(
        columns={"lat": "tlat", "lon": "tlon"})
    o = out.join(idx, on="drive_nearest_cma")
    m = o.drive_minutes.notna() & o.tlat.notna()

    src = gpd.GeoSeries([Point(xy) for xy in zip(o.loc[m, "lon"], o.loc[m, "lat"])],
                        crs=4326).to_crs(3347)
    dst = gpd.GeoSeries([Point(xy) for xy in zip(o.loc[m, "tlon"], o.loc[m, "tlat"])],
                        crs=4326).to_crs(3347)
    out.loc[m, "drive_target_km"] = (src.distance(dst, align=False).values / 1000).round(2)
    out["implied_kmh"] = (out.drive_target_km /
                          (pd.to_numeric(out.drive_minutes, errors="coerce") / 60)).round(1)
    out["drive_slow_route"] = out.implied_kmh < 20
    out.loc[out.implied_kmh.isna(), "drive_slow_route"] = pd.NA
    return out


def main(limit=None):
    cw = pd.read_csv(OUTPUT / "csd_to_cma2021.csv",
                     dtype={"csd": str, "cma": str, "nearest_cma": str})
    for c in ("lat", "lon"):
        cw[c] = pd.to_numeric(cw[c], errors="coerce")

    gc = cw[(cw.group == "c_MIZ") & cw.lat.notna()].copy()
    gc["key"] = gc.lat.round(5).astype(str) + "," + gc.lon.round(5).astype(str)
    origins = gc.drop_duplicates("key")[["key", "lat", "lon"]].reset_index(drop=True)
    if limit:
        origins = origins.head(limit)
    print(f"group (c) CSD-years {len(gc):,} -> {len(origins):,} distinct origins")

    core = core_city_points()
    idx = shortlist(origins, core)

    # sort so that neighbouring origins share candidates, keeping batches small
    origins["grp"] = idx[:, 0]
    order = origins.sort_values(["grp", "lat", "lon"]).index.to_numpy()

    results = {}
    batch, batch_cands, sent = [], set(), 0
    t0 = time.time()

    def flush(batch, cands):
        nonlocal sent
        if not batch:
            return
        cl = sorted(cands)
        pos = {c: i for i, c in enumerate(cl)}
        src = [(origins.at[i, "lat"], origins.at[i, "lon"]) for i in batch]
        dst = [(core.at[c, "lat"], core.at[c, "lon"]) for c in cl]
        dur, snap = call_table(src, dst)
        sent += 1
        if dur is None:
            return
        for row, i in enumerate(batch):
            cands_i = idx[i]
            best, best_c = None, None
            for c in cands_i:
                v = dur[row][pos[c]]
                if v is not None and (best is None or v < best):
                    best, best_c = v, c
            snap_km = (snap[row] or 0) / 1000 if snap else None
            results[origins.at[i, "key"]] = (best, best_c, snap_km)
        time.sleep(PAUSE)

    for i in order:
        cands = set(idx[i].tolist())
        if batch and (len(batch) >= MAX_SOURCES
                      or len(batch) + 1 + len(batch_cands | cands) > MAX_COORDS):
            flush(batch, batch_cands)
            batch, batch_cands = [], set()
        batch.append(i)
        batch_cands |= cands
    flush(batch, batch_cands)
    print(f"{sent} requests in {time.time()-t0:.0f}s, {len(results):,} origins resolved")

    rows = []
    for key, (dur, ci, snap_km) in results.items():
        unreachable = snap_km is not None and snap_km > SNAP_LIMIT_KM
        rows.append({
            "key": key,
            "drive_minutes": None if dur is None or unreachable else round(dur / 60, 1),
            "drive_nearest_cma": None if ci is None or unreachable else core.at[ci, "cma"],
            "drive_nearest_cma_name": None if ci is None or unreachable else core.at[ci, "cma_name"],
            "drive_nearest_core_city": None if ci is None or unreachable else core.at[ci, "csd_name"],
            "road_snap_km": None if snap_km is None else round(snap_km, 1),
            "no_road_access": bool(unreachable),
        })
    res = pd.DataFrame(rows)

    gc2 = gc[["csd", "year", "key"]].merge(res, on="key", how="left")
    out = cw.merge(gc2.drop(columns="key"), on=["csd", "year"], how="left")
    out = add_speed_columns(out, core)

    target = OUTPUT / "csd_to_cma2021.csv"
    try:
        out.to_csv(target, index=False, encoding="utf-8-sig", float_format="%.6f")
    except PermissionError:
        # the file is open in another program; don't lose the routing work
        target = OUTPUT / "csd_to_cma2021_with_traveltime.csv"
        out.to_csv(target, index=False, encoding="utf-8-sig", float_format="%.6f")
        print(f"\nNOTE: csd_to_cma2021.csv is locked (open in Excel?).")
    print(f"wrote {target}")

    # implied_kmh must compare the drive time with the straight-line distance to
    # the SAME city that was routed to.  Using nearest_km here would divide the
    # distance to the straight-line-nearest city by the time to the road-nearest
    # one -- two different destinations whenever routing re-ranks.
    ok = out[out.drive_minutes.notna()]
    print(f"\ntravel time attached to {len(ok):,} CSD-years")
    print(f"no road access flagged  : {int(out.no_road_access.fillna(False).sum()):,}")
    if len(ok):
        print("\ndrive time to nearest core city (minutes):")
        for q in (0.25, 0.5, 0.75, 0.9):
            print(f"   {int(q*100):>2}th pct {ok.drive_minutes.quantile(q):7.1f}")
        print(f"   max      {ok.drive_minutes.max():7.1f}")
        diff = ok[ok.drive_nearest_cma != ok.nearest_cma]
        print(f"\nroad routing picks a DIFFERENT nearest area than straight line: "
              f"{len(diff):,} of {len(ok):,} ({len(diff)/len(ok)*100:.2f}%)")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int)
    main(**vars(p.parse_args()))
