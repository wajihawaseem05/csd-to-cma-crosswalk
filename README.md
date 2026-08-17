# CSD to 2021 CMA crosswalk

Every Canadian census subdivision, from 2001 to 2021, matched to its **2021**
classification: one of the 41 census metropolitan areas, 111 census
agglomerations, or 5 metropolitan influenced zones. For those in a MIZ, the
nearest CMA or CA is given, measured to its **core city**.

**26,594 CSD-years** across five census vintages.

The deliverable is **`output/csd_to_cma2021.csv`**, which opens directly in
Excel. Everything below explains what is in it and how each decision was made;
the code that produced it is described at the end.

```
CSD (any year)  →  2021 CMA / CA / MIZ
                        └─ if MIZ:  nearest CMA or CA, distance to its core city
```

---

## The output

`output/csd_to_cma2021.csv` — one row per CSD-year.

| Column | Meaning |
|---|---|
| `csd` | Census subdivision code, 7 digits, as recorded **in that year** |
| `year` | Census vintage the code belongs to: 2001, 2006, 2011, 2016, 2021 |
| `csd_name` | Municipality name **as recorded in that year** — see below |
| `csd_type` | Municipal status that year — see "CSD type codes"; full lookup in `output/csd_type_reference.csv` |
| `group` | `a_CMA`, `b_CA`, or `c_MIZ` — the three-way sort |
| `cma` | 2021 CMA/CA code, or 996–999 / 000 for a MIZ |
| `cma_name` | Its name |
| `cma_type` | `B` = CMA, `D`/`K` = CA, `G`/`H`/`I`/`J` = MIZ |
| `miz_class` | For group (c): Strong / Moderate / Weak / No MIZ, or Territories outside CAs. Blank otherwise. See "Where MIZ comes from" |
| `confidence` | Share of the CSD's population landing in the assigned area. 1.0 = unambiguous. Blank where it could not be computed — see below |
| `n_cma_links` | How many distinct 2021 areas the CSD touches. 1 = clean |
| `method` | How the row was derived (see below) |
| `lat`, `lon` | Population-weighted centroid of the CSD's territory |
| `nearest_cma` | **Group (c) only.** Nearest CMA or CA, straight line |
| `nearest_cma_name` | Its name |
| `nearest_cma_type` | `B` if the nearest is a CMA, `D`/`K` if a CA |
| `nearest_core_city` | The municipality used as the target point |
| `nearest_km` | Straight-line distance to that core city, km |
| `drive_minutes` | **Group (c) only.** Driving time to the nearest core city by road |
| `drive_nearest_cma` | Which CMA/CA is nearest **by road** — not always the same one |
| `drive_nearest_cma_name` | Its name |
| `drive_nearest_core_city` | The core city reached by road |
| `road_snap_km` | Distance from the CSD centroid to the nearest road |
| `no_road_access` | `True` where that snap exceeds 20 km — no roads at all |
| `implied_kmh` | Straight-line km covered per hour of driving. ~50 is a normal road route |
| `drive_slow_route` | `True` below 20 km/h — the route crosses water by ferry, or detours heavily |

Straight-line and road columns are kept side by side rather than one replacing
the other, so the two rankings can be compared and the straight-line figure
remains available where routing fails.

`output/csd_to_cma2021_long.csv` holds every CSD-to-area pair with its share,
for auditing CSDs that straddle a boundary.

`output/csd_type_reference.csv` decodes the `csd_type` abbreviations.

### Distribution

| Year | (a) CMA | (b) CA | (c) MIZ |
|---|---|---|---|
| 2001 | 661 | 509 | 4,430 |
| 2006 | 588 | 463 | 4,367 |
| 2011 | 581 | 435 | 4,237 |
| 2016 | 583 | 428 | 4,151 |
| 2021 | 579 | 428 | 4,154 |

---

## How the match was made

Dissemination blocks are the smallest census unit and nest inside both CSDs and
CMAs. Every census publishes a **block correspondence file** linking its blocks
to the previous census's, so blocks chain forward:

```
2006 blocks → 2011 → 2016 → 2021 → 2021 CMA/CA/MIZ
```

Each vintage's **Geographic Attribute File** records which CSD its blocks
belonged to, so a CSD of any year decomposes into blocks, and those blocks carry
it forward. Weights are **that year's block population**, so the answer reflects
where people actually lived, not how land was divided.

### CSD names and types are contemporaneous

`csd_name` and `csd_type` are read from **that year's own source**, not from
2021: the 2001 boundary file's label points for 2001, and each vintage's own
boundary file thereafter.

This matters because municipalities are renamed, amalgamated and re-typed
between censuses. 84 codes carry a different name in 2016 than in 2006. CSD
1007039 is "Savage Cove-Sandy Cove" in 2001 through 2011 and "Sandy Cove" from
2016 on; Vancouver's type changes from `C` in 2001 to `CY` later. Stamping the
modern name or type onto an older code would misrepresent the record and break
any join against period sources.

Every one of the 26,594 CSD-years resolves to a name — none are missing.

#### Decoding `csd_type`

`csd_type` uses Statistics Canada's census subdivision type abbreviations —
`CY` city, `T` town, `VL` village, `IRI` Indian reserve, `SNO` subdivision of
unorganized, and so on. **71 distinct codes appear across the five vintages.**

The authoritative table is **Table 1.5 of the Census Dictionary**. It is
reproduced in full on the [2016 Dictionary CSD
page](https://www12.statcan.gc.ca/census-recensement/2016/ref/dict/geo012-eng.cfm);
the 2021 Dictionary references the same table but publishes it only in the
[Standard Geographical Classification, Volume I (12-571-X)](https://www.statcan.gc.ca/en/subjects/standard/sgc/2021/introduction).

For convenience, **`output/csd_type_reference.csv`** lists every code that
actually occurs in this crosswalk, with its meaning, the source of that meaning,
how many CSD-years use it, and which vintages it appears in. 61 of the 71 codes
are documented from a published table.

**Ten rare codes remain unresolved** — `CM`, `FD`, `NVL`, `RG`, `MRM`, `GR`,
`CÉ`, `RMU`, `TAL`, `TWL` — together 110 CSD-years, 0.4% of the file. They are
marked `NOT FOUND` in the reference rather than guessed at.

#### 2001 uses a different type vocabulary

This is the sharpest case of the contemporaneity point above, and the one most
likely to bite. **`csd_type` is not directly comparable between 2001 and later
years.** Eight codes appear only in 2001 and were replaced by differently-named
equivalents from 2006 onward:

| 2001 | 2006 onward | Meaning | Confirmed? |
|---|---|---|---|
| `R` | `IRI` | Indian reserve | ✅ |
| `S-E` | `S-É` | Indian settlement | ✅ |
| `TR` | `TC` / `TK` | Terres réservées (Cree and Naskapi lands, Quebec) | ✅ |
| `RC` | `RCR` | Rural community, New Brunswick | ✅ |
| `SUN` | `SNO` | Subdivision of unorganized | inferred |
| `UNO` | `NO` | Unorganized | inferred |
| `PAR` | `P` | Parish | inferred |
| `SCM` | `SC` | Subdivision of county municipality | inferred |

The four marked ✅ are confirmed from the 2001 Dictionary text. The other four
are **inferred from the naming pattern, not confirmed** — the 2001 type table is
published only as an image, so those meanings could not be read from a
machine-readable source. They are flagged as unconfirmed in the reference file
too. The 2001 SGC or the Dictionary's Table 6 image would settle them.

Only 38 codes are shared between 2001 and the later vintages, and `R` alone
covers 1,052 CSDs in 2001. Anyone grouping by `csd_type` across the whole panel
should map the legacy codes first, or restrict to 2006 onward — otherwise
reserves appear to vanish in 2006 and a new `IRI` category appears from nowhere.

### What a blank `confidence` means

`confidence` is a population share, so it needs population to compute. It is
left **blank** — not zero — in two situations, 450 rows in total:

- **376 rows in 2001** resolved spatially, where no block populations exist for
  that vintage.
- **74 CSDs with no residents at all** — parks, unpopulated subdivisions — that
  also split across more than one 2021 area. With no population there is nothing
  to weight by, and the split cannot be resolved.

A further 1,667 unpopulated CSDs map to a **single** 2021 area. Those are
recorded as confidence 1.0, which is correct by definition: if everything goes
to one place, the share is one. An earlier version reported these as 0.000,
which read as "unreliable" when the assignment was in fact unambiguous.

### Where MIZ comes from

All five metropolitan influenced zone classes are read from the **2021
Geographic Attribute File** (`2021_92-151_X.csv`, catalogue 92-151-X) — the same
file supplying the CMA and CA codes. No separate source is involved.

When a CSD is in no CMA and no CA, StatCan puts a reserved code in the
`CMAUID_RMRIDU` column rather than leaving it blank, and spells it out in
`CMANAME_RMRNOM`:

| `CMAUID` | Meaning | `SACTYPE` | 2021 CSDs |
|---|---|---|---|
| 996 | Strong metropolitan influenced zone | 4 | 729 |
| 997 | Moderate MIZ | 5 | 1,340 |
| 998 | Weak MIZ | 6 | 712 |
| 999 | No MIZ | 7 | 1,274 |
| 000 | Territories outside CAs | 8 | 99 |

**The same file also carries `SACTYPE_CSSGENRE`**, the Statistical Area
Classification, which is StatCan's canonical field for this distinction. The two
were cross-checked and agree **exactly, one-to-one, with no exceptions** across
all 5,161 CSDs — and on the other side SACTYPE 1/2/3 line up with the 579 CSDs
in CMAs and 428 in CAs. Either field reproduces the output identically; this
crosswalk reads `CMAUID` because it also supplies the CMA and CA codes in the
same pass.

Note that MIZ is itself **commuting-based**: StatCan assigns it from the share
of a CSD's employed residents commuting to any CMA or CA — 30% or more is
strong, 5–30% moderate, under 5% weak, essentially none is "no MIZ". This is why
`miz_class` and `drive_minutes` complement rather than duplicate one another.
MIZ says how strongly a place is attached to metropolitan Canada; the routing
says which city, and how far. Two moderate-MIZ CSDs, one 40 minutes from
Kamloops and one 40 minutes from Yorkton, share a class but belong to very
different labour markets.

### 2001 is different

2001 is the only vintage with no Geographic Attribute File — Statistics Canada's
attribute files begin at 2006. Its CSDs therefore cannot be decomposed into
blocks. Two routes are used instead:

| Method | Rows | What it does |
|---|---|---|
| `block_chain` | 20,994 | 2006–2021, as above |
| `code_inherit_2006` | 5,224 | A 2001 CSD code still present in 2006 takes the 2006 answer |
| `point_in_polygon` | 368 | Codes retired before 2006: the 2001 boundary file's label points are located inside 2021 CSD polygons |
| `point_in_polygon_nearest` | 8 | Points anchored over water: matched to the nearest polygon instead |

All 5,600 of the 2001 CSDs are resolved.

The last row is worth explaining. Eight 2001 CSDs initially failed both routes.
Their codes had vanished by 2006, so there was nothing to inherit, and their
label points sit a few metres offshore — outside every polygon, because the 2021
cartographic boundary file is clipped to the shoreline. All eight are waterfront:
Rigolet, Makkovik, Hopedale and Postville on the Labrador coast, and
Sainte-Croix, Notre-Dame-de-Pierreville, Beaconsfield and Maple Grove on the St
Lawrence, Lake Saint-Pierre and Lake Saint-Louis. The four Quebec municipalities
were abolished in the 2002 municipal mergers, which is why their codes do not
survive into 2006.

Falling back to the nearest polygon resolves all eight, at snap distances of
**18 m to 392 m** — small enough that the match is unambiguous. Beaconsfield's
2001 code `2466105` maps to `2466107`, the code it received after demerging in
2006. Two of the eight are Montreal-CMA municipalities, not obscure cases, so
their absence would have been noticed.

#### How 2001 was validated

2006 through 2021 are validated by population conservation: each vintage's block
populations are chained forward independently and must still sum to that
census's published national count. **That check is impossible for 2001**, because
there is no 2001 attribute file and therefore no 2001 block populations. Some
other evidence was needed.

The approach was to answer the same question twice, by two methods sharing
almost no machinery, and see whether they agree:

| | Method A — code inheritance | Method B — point-in-polygon |
|---|---|---|
| How it works | Look the 2001 code up in 2006, carry back that year's answer | Locate the CSD's label point inside a 2021 polygon, read the classification off directly |
| Based on | Block chaining, weighted by population | Geometry only |
| Uses population? | Yes | No |
| Uses 2006 data? | Yes | No |

Method B was run over **all 5,600** 2001 CSDs, not just the ones that needed it,
purely so the two could be compared. They both have an answer for **5,224** CSDs:

| Agreement | Result |
|---|---|
| On the exact CMA / CA / MIZ code | 5,117 of 5,224 — **97.95%** |
| On the group, (a) CMA / (b) CA / (c) MIZ | 5,218 of 5,224 — **99.89%** |

The second row is the one that matters for this project, since the deliverable
sorts CSDs into those three groups. **Only six CSDs disagree at group level.**

Of the 107 code-level disagreements, **101 are two methods placing the same CSD
in different MIZ classes** — strong versus moderate influence, say — while
agreeing it is rural. That is a disagreement about degree, not about kind.

The six genuine group-level disagreements all take the same form: method A says
CMA or CA, method B says MIZ. Examples include Tyendinaga in the Belleville–
Quinte West CMA and Beresford near Bathurst. This is the **known weakness of
method B**: it represents an entire CSD by a single label point, so for a large
municipality straddling a metropolitan edge, the point can land in the rural
part while most of the territory and population sit inside the CMA. Method A,
being population-weighted over the whole territory, is the more reliable of the
two here — and method A is what those 5,224 rows actually use.

**What this does not establish.** Both methods ultimately read the same 2021
classification, so a fault there would not surface. And the **376 CSDs placed by
method B alone** — codes that had vanished by 2006, leaving method A nothing to
inherit — have no cross-check at all, and rest on the weaker of the two methods.
Those rows carry `method = point_in_polygon` or `point_in_polygon_nearest` and a
blank `confidence`, so they can be identified and excluded if needed.

Full output in `output/validation_2001.txt`.

---

## Why core city, and not the boundary

The professor's instruction was to measure distance to the **core city**. This
section records why, since the alternatives give materially different answers.

Three definitions were tested against all 4,154 group (c) CSDs:

| Definition | Median distance | Mean |
|---|---|---|
| Nearest **edge** of the CMA polygon | 35.6 km | 78.2 km |
| CMA polygon **centroid** | 67.5 km | 108.6 km |
| **Core city** — population-weighted centre of the CMA's largest CSD | 67.3 km | 108.8 km |

They do not merely differ in magnitude — they **name different destinations**:

| Comparison | Pick a different CMA/CA |
|---|---|
| Edge vs centroid | 18.80% |
| **Edge vs core city** | **19.67%** |
| Centroid vs core city | 8.18% |
| All three agree | 77.06% |

The decisive cases are large, sparsely populated CMAs whose boundary reaches far
beyond their only settlement:

| CSD | By nearest edge | By core city |
|---|---|---|
| Beauval, SK | Wood Buffalo, 155 km | **Prince Albert, 245 km** |
| Canoe Lake 165, SK | Wood Buffalo, 122 km | **Lloydminster, 235 km** |
| Flin Flon (Part), MB | Prince Albert, 252 km | **Thompson, 272 km** |

Wood Buffalo's *edge* is close to northern Saskatchewan; Fort McMurray, its only
city, is not. Edge-based assignment attaches these communities to Fort McMurray
on a technicality.

**Core city was chosen because:**

1. It is the only definition tied to where employment actually is, which is what
   a commuting-based measure is meant to capture.
2. It is stable under boundary change — a CMA can expand its edge without its
   core moving, so the variable does not shift for administrative reasons.
3. It matches the ordinary-language meaning of "commute time to the CMA."

Across group (c), the core city is a median **25.4 km** further than the edge,
59 km at the 90th percentile, and up to **314 km** in the worst case.

**Core city is operationalised** as the most populous 2021 CSD inside each CMA/CA,
located at its population-weighted centroid. This resolves sensibly — Toronto CMA
to Toronto, Montréal to Montréal, Ottawa–Gatineau to Ottawa.

### Other decisions

**Population weights, not land area.** Land weighting lets a large empty tract
outvote a small populated one. Where both were computed on the earlier
DA-level work, they disagreed on the CMA for a small but real fraction of areas.

**Nearest includes CAs, not just CMAs.** There are only 41 CMAs. Restricting to
them would assign northern communities to cities many hundreds of kilometres
away. Including the 111 CAs gives a meaningful nearest destination.

**MIZ class is a 2021 classification, inherited.** It is read from the 2021
attribute file (see "Where MIZ comes from"). A 2001 CSD's `miz_class`
describes the metropolitan influence of its territory *in 2021*, not its status
in 2001. This follows from the brief — everything is expressed on 2021
boundaries — but it should not be read as a historical statement.

**Both straight-line distance and road travel time are provided.** Straight-line
distance is computed in Statistics Canada Lambert (EPSG:3347), so units are true
metres. Road travel time is described below.

---

## Road travel time

Straight-line distance ignores lakes, mountains and the absence of roads, all of
which matter in rural Canada. A community can sit 50 km from a city across a
lake and be a two-hour drive away. So driving time is computed as well, and it
can pick a **different** nearest city than the straight-line measure.

**Engine.** OSRM routing on OpenStreetMap road data, via the public OSRM demo
server. Free-flow speeds — no traffic, no time-of-day effects. That is
deterministic and reproducible, which is what a published crosswalk needs, but
it is not rush-hour reality. A self-hosted OSRM instance returns identical
results; it is the same engine on the same data.

**Shortlisting.** Only the four nearest core cities by straight line are routed
for each origin, rather than all 152. Road distance can reorder near neighbours
but will not promote a city lying tenth in line.

**Batching.** Origins are sorted so that neighbours share candidate
destinations, then up to 100 origins are sent per request against the union of
their candidates. This keeps the load on a free public service to roughly a
hundred requests instead of tens of thousands.

**Origins are deduplicated.** The 21,339 group (c) CSD-years reduce to 10,316
distinct centroids, since a CSD's centroid moves only slightly between censuses.

### Communities with no road

Some CSDs — largely in Nunavut, northern Quebec and coastal Labrador — have no
road connection to the rest of Canada. A router will still return a number for
them: it snaps the origin to whatever road it can find, possibly hundreds of
kilometres away, and reports a plausible-looking driving time that is entirely
fictional.

This is detected rather than assumed. `road_snap_km` records how far the CSD
centroid sits from the nearest road; where that exceeds 20 km the CSD is flagged
`no_road_access = True` and `drive_minutes` is left null. **A missing value is
the correct answer here, and better than a fabricated drive.** The straight-line
columns remain populated for these CSDs, so they are not lost.

The threshold is a judgement call. It was set from the data rather than from
latitude, because some southern CSDs are also effectively roadless and some
northern ones are not.

**The snap test alone proved insufficient**, and this is worth stating plainly.
It catches only places with no roads whatsoever. Northern Labrador communities
such as Nain and Natuashish have local streets — they snap to a road within
1 km and pass the test — but no road connection to the rest of the province.
OpenStreetMap treats ferry links as routable, so OSRM happily returned **46.5
hours** to Corner Brook. That is a real route in the data and a meaningless
commute.

A second discriminator was added: `implied_kmh`, the straight-line distance
covered per hour of driving. A normal road route runs near 50 km/h by this
measure. Ferry crossings and long detours around water fall far below it, and
`drive_slow_route` flags anything under 20 km/h — **499 CSD-years across 129
distinct CSDs**, concentrated in coastal British Columbia (48 CSDs, largely the
Gulf Islands) and Quebec's Lower North Shore.

Note these are *flagged, not deleted*. For a Gulf Islands resident a
ferry-inclusive 138-minute trip to Vancouver is the genuine travel time, and
should be kept. For Nain, 46.5 hours is not a commute in any sense. The flag
lets that judgement be made downstream rather than being hard-coded here.

### Results

| | |
|---|---|
| Group (c) CSD-years | 21,339 |
| With a drive time | 20,694 |
| Flagged `no_road_access` | 598 |
| Flagged `drive_slow_route` | 499 |
| Over six hours' drive | 980 |

Drive time to the nearest core city, restricted to clean routes — not ferry,
under six hours, 19,377 CSD-years or **93.7%** of those routed:

| Percentile | Drive time |
|---|---|
| 25th | 47.6 min |
| 50th | **75.9 min** |
| 75th | 119.4 min |
| 90th | 190.6 min |

**Road routing picks a different nearest CMA/CA than straight-line distance for
3,501 of 20,694 CSD-years — 16.92%.** That is the number justifying the exercise:
for roughly one rural CSD-year in six, the closest city as the crow flies is not
the closest city to drive to.

---

## Validation

| Check | Result |
|---|---|
| Population conserved, 2021 | 36,991,981 — exact match to published count |
| Population conserved, 2016 | 35,151,728 — exact |
| Population conserved, 2011 | 33,476,688 — exact |
| Population conserved, 2006 | 31,612,897 — exact |
| CSD counts vs boundary files | 2016: 5,162 ✅ 2011: 5,253 ✅ 2006: 5,418 ✅ |
| 2001 dual-method agreement, group level | 99.89% (n = 5,224) |
| 2001 dual-method agreement, exact code | 97.95% (n = 5,224) |
| CSD-years with confidence = 1.0 | 24,987 (93.96%) |
| CSD-years with confidence ≥ 0.95 | 25,611 (96.30%) |

The population checks are the strongest evidence. Each vintage's block
populations are chained forward independently and must still sum to that
census's published national count. They do, exactly, for all four chained
vintages.

That check earned its place: an earlier version inflated 2011 by 1.25% and 2006
by 4.27%, because over multiple hops a block can reach the same 2021 block by
two different intermediate paths and was being counted once per path. The
duplicate collapse in `chain()` fixes it, and the conservation test is what
exposed it.

---

## Limitations

**1,367 CSD-years touch more than one 2021 area**, and 188 have confidence
below 0.75. For these the single assigned area is a majority verdict, not a
clean fact. Use `confidence` and `n_cma_links` to filter, or the long file to
apportion fractionally.

**2001 is weaker than the other vintages.** No attribute file means no
population weighting for that year, and `confidence` is blank for the 368 rows
resolved by point-in-polygon.

**Blocks straddling two source CSDs are split evenly.** The files do not record
how such a block divides. This affects a small number of blocks per hop.

**Small-area populations are rounded.** Block counts below about 16 are reported
only as 0, 5, 10 or 15, so weights resting on a handful of small blocks are
noisier than their decimal places suggest.

---

## Reproducing it

```bash
.venv/Scripts/python.exe build_csd_crosswalk.py   # 2006, 2011, 2016, 2021
.venv/Scripts/python.exe add_2001.py              # adds 2001
.venv/Scripts/python.exe add_core_city.py         # nearest core city, straight line
.venv/Scripts/python.exe add_travel_time.py       # road driving time
.venv/Scripts/python.exe add_csd_names.py         # CSD name and type per vintage
```

`add_travel_time.py` calls an external routing service and takes roughly half an
hour; pass `--limit N` to test on a sample first. The other three run offline.

Needs `pandas`, `geopandas`, `pyogrio`, `shapely`. The offline steps take about
20 minutes, most of it reading the 299 MB attribute file and the 314 MB boundary
shapefile; routing adds roughly another half hour.

`extract_gaf.py` is run once per vintage to pull the slim block tables out of
the `.xlsx` attribute files; its outputs are cached in `data/_gaf*_slim.csv`.

---

## Sources

All inputs are free and public from Statistics Canada.

- Geographic Attribute Files (92-151-X), 2006 / 2011 / 2016 / 2021 — source of
  the CSD-to-block mapping, block populations, CMA/CA codes, and the MIZ classes
  (fields `CMAUID_RMRIDU` and `SACTYPE_CSSGENRE`)
- Dissemination block correspondence files (92-156-X), 2006 / 2011 / 2016 / 2021
- Census subdivision boundary files, 2001 / 2006 / 2011 / 2016 / 2021
  (`gcsd000b01a_e`, `gcsd000b06a_e`, `gcsd000b11a_e`, `lcsd000b16a_e`,
  `lcsd000b21a_e`) — geometry for 2001, and the CSD names and types per vintage
- Census metropolitan area boundary file, 2021 (`lcma000b21a_e`)
- Road network: OpenStreetMap, routed with OSRM

Reference guide: [Correspondence Files, 92-156-G](https://www150.statcan.gc.ca/n1/pub/92-156-g/92-156-g2021001-eng.htm)
