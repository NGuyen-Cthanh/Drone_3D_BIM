"""
schedule_loader.py
==================
Doc lich thi cong xuat tu Navisworks TimeLiner (CSV) va gan ngay ke hoach -> TANG cua mo hinh.

CACH XUAT TU NAVISWORKS
  TimeLiner > tab Tasks > bam nut Export Schedule (hoac Data Sources > Export) > CSV.
  File can co cac cot: Name, Planned Start, Planned End (va neu co: Actual Start/End, Attached).
  Neu ten cot cua ban khac, sua COLUMN_ALIASES ben duoi.

LUU Y (CHUA KIEM CHUNG VOI FILE THAT)
  Code nay duoc viet va thu voi file CSV GIA LAP theo dinh dang TimeLiner pho bien; chua thu voi CSV that
  cua nhom. Hay chay:  python schedule_loader.py lich.csv --data data
  roi doc bang 'tang -> ngay' in ra, doi chieu voi TimeLiner de chac chan truoc khi tin ket qua.

VAN DE NGAY THANG
  CSV tu may Windows tieng Anh thuong la thang/ngay/nam (vd 11/26/2026). Neu bat ky gia tri nao co
  thanh phan dau > 12 thi tu dong chuyen sang ngay/thang/nam. Truong hop toan ngay <= 12 thi mac dinh
  thang/ngay/nam - hay kiem tra lai bang mat.

FILE LICH THAT CUA NHOM (PALC Q9) - cau truc da thay
  Ten task la MA viet tat, khong co chu 'TANG':   CV2F, DS2F, ..., CV14F, DS14F, CVRF, DSRF  (theo tang)
                                                  Z1-M, Z1-DS, Z1-CV, Z1-S1, Z2-..., Z5.1-..., CKN  (theo phan khu / mong)
  Cot 'Attached' chi ghi 'Explicit Selection' => cau kien gan cho task nam trong NWD, KHONG co trong CSV.
  Quy tac mac dinh (xem ROLE_RULES): CV<n>F = cot-vach tang n; DS<n>F = dam-san tang n; CVRF/DSRF = mai.
  Cac ma con lai (Z*-*, CKN...) KHONG tu nhan dang duoc -> in ra de bao cao; co the gan tay bang --map (JSON).

GAN TANG
  Ten task / ten tap chon (cot Attached) chua 'TANG 10', 'TANG HAM', 'TUM', 'MAI', 'VIA HE'... (khong dau, khong
  phan biet hoa/thuong) duoc nhan dang, roi doi sang chi so tang (theo cao do san that, giong mesh_utils).
"""
import csv
import json
import re
import unicodedata
from datetime import datetime, timedelta
import numpy as np

COLUMN_ALIASES = {
    "name": ["name", "task name", "ten", "ten cong viec"],
    "planned_start": ["planned start", "bat dau ke hoach", "ke hoach bat dau", "start"],
    "planned_end": ["planned end", "ket thuc ke hoach", "ke hoach ket thuc", "end"],
    "actual_start": ["actual start", "bat dau thuc te", "thuc te bat dau"],
    "actual_end": ["actual end", "ket thuc thuc te", "thuc te ket thuc"],
    "attached": ["attached", "attachment", "attached sets", "gan", "tap chon"],
}
ENCODINGS = ["utf-8-sig", "utf-16", "cp1258", "cp1252", "latin-1"]


def norm(s):
    """Bo dau tieng Viet, viet hoa."""
    s = unicodedata.normalize("NFD", str(s))
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return s.replace("Đ", "D").replace("đ", "d").upper().strip()


def floor_key(text):
    """Nhan dang tang trong mot chuoi: ('T', n) | ('HAM',) | ('TUM',) | ('MAI',) | ('VIAHE',) | None."""
    n = norm(text)
    m = re.search(r"TANG\s*(\d+)", n)
    if m:
        return ("T", int(m.group(1)))
    if re.search(r"TANG\s*HAM|\bHAM\b", n):
        return ("HAM",)
    if re.search(r"\bTUM\b", n):
        return ("TUM",)
    if re.search(r"\bMAI\b|\bRF\b|TANG\s*MAI", n):
        return ("MAI",)
    if re.search(r"VIA\s*HE|COTE\s*0", n):
        return ("VIAHE",)
    return None


# QUY UOC GAN TANG CHO FILE LICH PALC Q9  (tang truc = chi so tang theo NHAN IFC, xem storey_floor_map)
#   DA XAC NHAN trong Navisworks (tang tret = tang 1):
#     CV<n>F : cot-vach nhan "TANG n", NAM TREN san tang n (CV3F tren san 3; CV2F tren DS2F; CV1F tren nen tang tret).
#              Khop IFC: cot nhan TANG 3 co chan z~8.85 m (san T3 = 8.81 m), dinh z~12.15 m.
#     DS<n>F : dam-san CHINH LA san tang n (DS3F = san tang 3, DS2F = san tang 2) => DS_SHIFT = 0.
#   DA KIEM CHUNG BANG NAVISWORKS: chon DS3F -> sang 'TANG 3- KC' > Floors va Structural Framing (133 cau kien = 100 dam
#          + 31 san nhan TANG 3 + 2 dam 200x300 gan nhan sai 'TANG 1' nhung nam o tang hinh hoc 2) => DS_SHIFT = 0.
#          Chon CV3F -> sang 'TANG 3- KC' > Structural Columns.
#   CVRF   : cot mai -> nhan TUM (nhan MAI trong IFC khong co cot nao; 126 cot nam o TUM).  DSRF -> nhan MAI.
#   Tang 1: khong co DS1F; tang 1 duoc ghep tu cac task Z*-S1 (CHUA chac chan) -> dung map_s1.json (--map).
DS_SHIFT = 0

ROLE_RULES = [  # (regex tren ten task viet hoa, vai tro, ham(m, key_to_floor, ds_shift) -> chi so tang | None)
    (r"CV(\d+)F", "CV", lambda m, k, sh: k.get(("T", int(m.group(1))))),
    (r"DS(\d+)F", "DS", lambda m, k, sh: (None if ("T", int(m.group(1))) not in k else k[("T", int(m.group(1)))] + sh)),
    (r"CVRF", "CV", lambda m, k, sh: k.get(("TUM",))),
    (r"DSRF", "DS", lambda m, k, sh: k.get(("MAI",))),
]


def parse_key(text):
    """'T-2' -> ('T', 2); 'MAI' -> ('MAI',)  (dung cho file --map)."""
    p = str(text).upper().split("-")
    return (p[0], int(p[1])) if len(p) == 2 and p[1].isdigit() else (p[0],)


def load_overrides(path):
    """JSON {ten_task: {"floor": chi_so_tang | "T-2" | "MAI", "role": "CV"|"DS"|"ALL"}}"""
    return json.load(open(path, encoding="utf-8")) if path else {}


def _read_rows(path):
    raw = open(path, "rb").read()
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    sample = text[:4000]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(text.splitlines(), dialect))
    return [r for r in rows if any(c.strip() for c in r)]


def _find_cols(header):
    h = [norm(c).lower() for c in header]
    cols = {}
    for key, aliases in COLUMN_ALIASES.items():
        for a in aliases:
            if a in h:
                cols[key] = h.index(a)
                break
    return cols


_FMT_MDY = ["%m/%d/%Y %I:%M:%S %p", "%m/%d/%Y %H:%M:%S", "%m/%d/%Y %H:%M", "%m/%d/%Y"]
_FMT_DMY = ["%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y"]
_FMT_ISO = ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]


def _parse_dates(values):
    vals = [v.strip() for v in values]
    first = [int(m.group(1)) for v in vals if (m := re.match(r"(\d{1,2})/\d{1,2}/\d{4}", v))]
    day_first = bool(first) and max(first) > 12
    fmts = _FMT_ISO + (_FMT_DMY + _FMT_MDY if day_first else _FMT_MDY + _FMT_DMY)
    out = []
    for v in vals:
        d = None
        for f in fmts:
            try:
                d = datetime.strptime(v, f)
                break
            except ValueError:
                pass
        out.append(d)
    return out, ("ngay/thang/nam" if day_first else "thang/ngay/nam")


def read_timeliner_csv(path):
    """Tra ve (tasks, kieu_ngay). tasks: list dict(name, attached, planned_start, planned_end, actual_start, actual_end)."""
    rows = _read_rows(path)
    hdr_i = next(i for i, r in enumerate(rows) if "name" in [norm(c).lower() for c in r] or "ten" in [norm(c).lower() for c in r])
    cols = _find_cols(rows[hdr_i])
    for need in ("name", "planned_start", "planned_end"):
        if need not in cols:
            raise ValueError(f"Khong tim thay cot '{need}'. Cac cot co trong file: {rows[hdr_i]}")
    body = rows[hdr_i + 1:]
    get = lambda r, k: (r[cols[k]] if k in cols and cols[k] < len(r) else "")
    all_dates = [get(r, k) for r in body for k in ("planned_start", "planned_end", "actual_start", "actual_end")
                 if get(r, k).strip()]
    _, style = _parse_dates(all_dates)
    fmts = _FMT_ISO + (_FMT_DMY + _FMT_MDY if style.startswith("ngay") else _FMT_MDY + _FMT_DMY)

    def pd(v):
        v = v.strip()
        for f in fmts:
            try:
                return datetime.strptime(v, f)
            except ValueError:
                pass
        return None

    tasks = []
    for r in body:
        tasks.append({"name": get(r, "name"), "attached": get(r, "attached"),
                      "planned_start": pd(get(r, "planned_start")), "planned_end": pd(get(r, "planned_end")),
                      "actual_start": pd(get(r, "actual_start")), "actual_end": pd(get(r, "actual_end"))})
    return tasks, style


def storey_floor_map(E, levels):
    """
    {floor_key: chi so tang} tu ten tang IFC. Chi so tang suy ra tu CAO DO THAT cua cac san thuoc tang do
    (trung vi z_max), khong tin vao nhan cua dam/cot (IFC co 21 dam bi gan nhan tang sai).
    """
    by = {}
    for e in E:
        if e["storey"] is None:
            continue
        by.setdefault(e["storey"], {"slab": [], "all": []})
        z = e["bbox"]["max"][2]
        by[e["storey"]]["all"].append(z)
        if e["ifc_type"] == "IfcSlab":
            by[e["storey"]]["slab"].append(z)
    out = {}
    for name, d in by.items():
        key = floor_key(name)
        if key is None:
            continue
        z = np.median(d["slab"] if d["slab"] else d["all"])
        out[key] = int(np.argmin(np.abs(levels - z)))
    return out


def label_floors(E, floors, key_to_floor, max_dev=2):
    """
    Chi so tang theo NHAN IFC (thay cho tang hinh hoc) - dung khi lich TimeLiner nhom cau kien theo nhan tang Revit.
    Voi PLM.ifc, COT mang nhan theo cao do CHAN cot nen tang hinh hoc = tang nhan + 1 (944/995 cot).
    Cau kien lech nhan > max_dev tang (vd 21 dam bi gan nhan sai) giu nguyen tang hinh hoc.
    """
    out = np.array(floors, copy=True)
    for i, e in enumerate(E):
        k = floor_key(e["storey"]) if e["storey"] else None
        if k in key_to_floor and abs(int(floors[i]) - key_to_floor[k]) <= max_dev:
            out[i] = key_to_floor[k]
    return out


def _classify_task(t, key_to_floor, overrides, ds_shift=DS_SHIFT):
    """-> (chi so tang | None, vai tro, ly_do_bo_qua)."""
    name = (t["name"] or "").strip()
    if name in overrides:
        o = overrides[name]
        f = o["floor"] if isinstance(o["floor"], int) else key_to_floor.get(parse_key(o["floor"]))
        return f, o.get("role", "ALL"), (None if f is not None else "tang trong --map khong co trong IFC")
    up = name.upper().replace(" ", "")
    if re.fullmatch(r"Z\d(\.\d)?-(M|DS|CV|S1|DHP|VHP)|CKN", up):
        # Da kiem tra trong Navisworks (Auto Select Attached Items): cac task nay gan voi COC, DAI COC, san day / tang ham,
        # tuc la phan mong - ham. PLM.ifc hien tai KHONG co nhung cau kien nay (IFC bat dau tu z = 0.8 m, khong co TANG HAM).
        return None, "ALL", "mong/ham/san day (coc, dai coc...): khong co trong PLM.ifc hien tai"
    for pat, role, fk in ROLE_RULES:
        m = re.fullmatch(pat, up)
        if m:
            f = fk(m, key_to_floor, ds_shift)
            if f is not None and not (0 <= f <= max(key_to_floor.values())):
                f = None
            return f, role, (None if f is not None else f"tang tuong ung ({up}, DS_SHIFT={ds_shift}) khong co trong IFC")
    key = floor_key(name) or floor_key(t["attached"])
    if key is None:
        return None, "ALL", "khong nhan dang duoc tang"
    return key_to_floor.get(key), "ALL", (None if key in key_to_floor else f"tang {key} khong co trong IFC")


def floor_schedule(tasks, key_to_floor, overrides=None, ds_shift=DS_SHIFT):
    """
    Gop task theo tang: {floor: {planned_start, planned_end, actual_start, actual_end, n_tasks,
                                 roles: {'CV'|'DS'|'ALL': {'start','end'}}}}.
    CV = cot-vach, DS = dam-san (neu lich phan biet). planned_start = som nhat, planned_end = muon nhat.
    Tra ve (table, bo_qua) - bo_qua = list (ten task, ly do).
    """
    overrides = overrides or {}
    table, skipped = {}, []
    for t in tasks:
        if not (t["name"] or "").strip():
            continue                                              # dong trong
        f, role, why = _classify_task(t, key_to_floor, overrides, ds_shift)
        if f is None or t["planned_end"] is None:
            skipped.append((t["name"], why or "thieu ngay ke hoach")); continue
        r = table.setdefault(f, {"planned_start": None, "planned_end": None, "actual_start": None,
                                 "actual_end": None, "n_tasks": 0, "roles": {}})
        r["n_tasks"] += 1
        for k, fn in (("planned_start", min), ("planned_end", max), ("actual_start", min), ("actual_end", max)):
            v = t[k]
            if v is not None:
                r[k] = v if r[k] is None else fn(r[k], v)
        rr = r["roles"].setdefault(role, {"start": t["planned_start"], "end": t["planned_end"]})
        rr["start"] = min(rr["start"], t["planned_start"]); rr["end"] = max(rr["end"], t["planned_end"])
    return table, skipped


def planned_top_floor(table, date):
    """Chi so tang CAO NHAT co ngay ket thuc ke hoach <= date (dau vao cho compare_with_schedule). -1 neu chua co."""
    done = [f for f, r in table.items() if r["planned_end"] is not None and r["planned_end"] <= date]
    return max(done) if done else -1


def floor_state(table, date):
    """{floor: 'xong' | 'dang_thi_cong' | 'chua_bat_dau'} theo ke hoach tai ngay date."""
    st = {}
    for f, r in table.items():
        if r["planned_end"] <= date:
            st[f] = "xong"
        elif r["planned_start"] is not None and r["planned_start"] <= date:
            st[f] = "dang_thi_cong"
        else:
            st[f] = "chua_bat_dau"
    return st


def element_schedule_floor(E, floors, key_to_floor, mode="label", mismatch=2):
    """
    Chi so tang dung de TRA LICH cho tung cau kien (khac 'floors' hinh hoc dung de danh gia).
      mode="geometry": = tang hinh hoc (task 'TANG n' = cau kien nam duoi/tren san n theo cao do that).
      mode="label"   : = tang theo NHAN IFC (Revit gan COT theo cao do CHAN cot, nen cot nam duoi san n+1 co
                       nhan 'TANG n'). Dung khi tap chon trong NWD duoc tao theo nhan tang (vd 'X1-X15 : TANG 10- KC').
                       Dam/san co nhan lech >= 'mismatch' tang so voi cao do that (gan nhan sai) -> giu tang hinh hoc.
    MAC DINH 'label'. DA KIEM CHUNG (Navisworks, task CV3F): cot cua CV3F nam TREN san tang 3 => 'label'.
    'geometry' gan cot lech 1 tang so voi lich nay; chi giu lai de doi chieu.
    """
    out = np.array(floors, copy=True)
    if mode == "geometry":
        return out
    for i, e in enumerate(E):
        k = floor_key(e["storey"]) if e["storey"] else None
        if k not in key_to_floor:
            continue
        lab = key_to_floor[k]
        if e["ifc_type"] == "IfcColumn" or abs(int(floors[i]) - lab) < mismatch:
            out[i] = lab
    return out


def unscheduled_elements(types, sched_floors, table):
    """Cau kien khong thuoc task nao cua lich (vai tro CV/DS cua tang do khong co task). Tra ve mask bool."""
    col = types == "IfcColumn"
    m = np.zeros(len(types), dtype=bool)
    for f in np.unique(sched_floors):
        roles = table.get(int(f), {}).get("roles", {})
        sel = sched_floors == f
        has_cv, has_ds = "CV" in roles or "ALL" in roles, "DS" in roles or "ALL" in roles
        m |= sel & ((col if not has_cv else False) | (~col if not has_ds else False))
    return m


def expected_built_mask(types, floors, table, date):
    """
    Cau kien 'ke hoach cho rang da xay' tai ngay date.
      - Lich co phan biet CV (cot-vach) / DS (dam-san): cot xay xong khi qua ngay ket thuc CV cua tang do;
        dam + san xay xong khi qua ngay ket thuc DS.
      - Lich khong phan biet (vai tro ALL): tang 'xong' -> moi cau kien; 'dang thi cong' -> chi COT.
    """
    st = floor_state(table, date)
    m = np.zeros(len(floors), dtype=bool)
    col, bs = types == "IfcColumn", types != "IfcColumn"
    for f, r in table.items():
        roles = r["roles"]
        if "CV" in roles or "DS" in roles:
            if "CV" in roles and roles["CV"]["end"] <= date:
                m |= (floors == f) & col
            if "DS" in roles and roles["DS"]["end"] <= date:
                m |= (floors == f) & bs
        elif st[f] == "xong":
            m |= floors == f
        elif st[f] == "dang_thi_cong":
            m |= (floors == f) & col
    return m


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    import config
    from mesh_utils import load_bim, slab_levels

    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--data", default=str(config.DATA_DIR))
    ap.add_argument("--date", default=None, help="ngay bao cao (YYYY-MM-DD), mac dinh hom nay")
    ap.add_argument("--ds-shift", type=int, default=DS_SHIFT, help="DS<n>F = dam-san nhan TANG n+shift (xem DS_SHIFT)")
    ap.add_argument("--map", default=None, help="JSON gan tay task -> tang/vai tro (xem docstring)")
    ap.add_argument("--write-template", default=None, help="ghi danh sach task chua gan ra file JSON de dien")
    a = ap.parse_args()

    E, V, F, fe = load_bim(Path(a.data) / "plm_elements.json", Path(a.data) / "plm_meshes.npz")
    levels = slab_levels(E)
    km = storey_floor_map(E, levels)
    print("Tang IFC -> chi so tang:", {("-".join(map(str, k))): v for k, v in sorted(km.items(), key=lambda kv: kv[1])})
    tasks, style = read_timeliner_csv(a.csv)
    named = [t for t in tasks if (t["name"] or "").strip()]
    print(f"Doc {len(named)} task co ten (bo {len(tasks)-len(named)} dong trong), kieu ngay: {style}")
    table, skipped = floor_schedule(tasks, km, load_overrides(a.map), a.ds_shift)
    fmt = lambda r: f"{r['start']:%m-%d}..{r['end']:%m-%d}" if r else "-"
    print("\n tang  Z(m)   cot-vach (CV)      dam-san (DS)       KH bat dau   KH ket thuc  #task")
    for f in sorted(table):
        r = table[f]; ro = r["roles"]
        print(f" {f:3d} {levels[f]:6.2f}   {fmt(ro.get('CV')):17s}  {fmt(ro.get('DS')):17s}  "
              f"{r['planned_start']:%Y-%m-%d}   {r['planned_end']:%Y-%m-%d}   {r['n_tasks']}")
    if skipped:
        print(f"\nChua gan duoc {len(skipped)} task (ly do ben canh):")
        for n, why in skipped:
            print(f"   {n:14s} {why}")
        if a.write_template:
            json.dump({n: {"floor": None, "role": "ALL"} for n, _ in skipped},
                      open(a.write_template, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
            print(f"-> Da ghi mau {a.write_template}: dien 'floor' (chi so tang hoac 'T-2'/'MAI') va 'role' (CV/DS/ALL) roi chay lai voi --map")
    d = datetime.strptime(a.date, "%Y-%m-%d") if a.date else datetime.now()
    print(f"\nTai {d:%Y-%m-%d}: tang cao nhat KH da xong = {planned_top_floor(table, d)}")