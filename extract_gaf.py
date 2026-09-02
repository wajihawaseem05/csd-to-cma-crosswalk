"""
Pull a slim table out of a Geographic Attribute File (.xlsx): one row per
dissemination block with its population, land area and census subdivision.

The 2011 and 2006 files have no header row and their column order differs
from 2016, so the columns are identified by content rather than by position:
the block UID is the long numeric key, and the CSD column is found by testing
which candidate column's values overlap a known list of CSD codes.  Guessing
positions is what silently mislabels these files.

    python extract_gaf.py <xlsx> <out.csv> [known_csd_list.txt]
"""

import csv
import re
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
CELL = re.compile(rb'<c r="([A-Z]+)\d+"([^>]*)>(?:<v>([^<]*)</v>)?')


def load_strings(z):
    out = []
    if "xl/sharedStrings.xml" not in z.namelist():
        return out
    with z.open("xl/sharedStrings.xml") as f:
        for _, el in ET.iterparse(f, events=("end",)):
            if el.tag == NS + "si":
                out.append("".join(t.text or "" for t in el.iter(NS + "t")))
                el.clear()
    return out


def rows(z, sheet, sst, limit=None):
    def value(attrs, v):
        if v is None:
            return None
        s = v.decode()
        if b't="s"' in attrs and s.isdigit():
            i = int(s)
            return sst[i] if i < len(sst) else None
        return s

    n = 0
    with z.open(sheet) as f:
        tail = b""
        while True:
            chunk = f.read(1 << 22)
            if not chunk:
                break
            parts = (tail + chunk).split(b"</row>")
            tail = parts.pop()
            for p in parts:
                yield {c.decode(): value(a, v) for c, a, v in CELL.findall(p)}
                n += 1
                if limit and n >= limit:
                    return


def main(path, out_path, known_path=None):
    z = zipfile.ZipFile(path)
    sst = load_strings(z)
    sheet = sorted(n for n in z.namelist()
                   if re.match(r"xl/worksheets/sheet\d+\.xml$", n))[0]

    sample = list(rows(z, sheet, sst, limit=200))
    first = sample[0]
    has_header = any(v and "uid" in str(v).lower() for v in first.values())
    body = sample[1:] if has_header else sample

    if has_header:
        hdr = {c: (v or "").upper() for c, v in first.items()}
        pick = lambda pre: next((c for c, v in hdr.items() if v.startswith(pre)), None)
        cols = {"db": pick("DBUID"), "pop": pick("DBPOP"),
                "area": pick("DBAREA"), "csd": pick("CSDUID")}
    else:
        # block UID is the longest all-digit key; area is the small decimal
        cols = {"db": None, "pop": None, "area": None, "csd": None}
        cand = {c: [r.get(c) for r in body if r.get(c)] for c in body[0]}
        for c, vals in cand.items():
            if all(v.isdigit() for v in vals[:50]) and len(vals[0]) >= 10:
                cols["db"] = cols["db"] or c
        letters = sorted(cand, key=lambda s: (len(s), s))
        order = {c: i for i, c in enumerate(letters)}
        db_i = order[cols["db"]]
        cols["pop"] = letters[db_i + 1]
        cols["area"] = letters[db_i + 4]
        known = set(open(known_path).read().split()) if known_path else set()
        best, score = None, 0
        for c, vals in cand.items():
            v7 = [v for v in vals if len(v) == 7 and v.isdigit()]
            if not v7:
                continue
            s = len(set(v7) & known) / len(set(v7)) if known else 0
            if s > score:
                best, score = c, s
        cols["csd"] = best
        print(f"  no header; detected columns {cols} (CSD match score {score:.2f})")

    print(f"  columns: {cols}")
    missing = [k for k, v in cols.items() if not v]
    if missing:
        sys.exit(f"could not identify columns: {missing}")

    with open(out_path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["db", "pop", "area", "csd"])
        n = 0
        for i, r in enumerate(rows(z, sheet, sst)):
            if i == 0 and has_header:
                continue
            row = [r.get(cols["db"]), r.get(cols["pop"]),
                   r.get(cols["area"]), r.get(cols["csd"])]
            if row[0]:
                w.writerow(row)
                n += 1
    print(f"  wrote {out_path}: {n:,} blocks")


if __name__ == "__main__":
    main(*sys.argv[1:])
