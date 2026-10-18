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


def floor_schedule(tasks, key_to_floor):
    """
    Gop task theo tang: {floor: {planned_start, planned_end, actual_start, actual_end, n_tasks}}.
    planned_start = som nhat, planned_end = muon nhat cua cac task thuoc tang do.
    Tra ve (table, bo_qua) - bo_qua = ten task khong nhan dang duoc tang / tang khong co trong IFC.
    """
    table, skipped = {}, []
    for t in tasks:
        key = floor_key(t["name"]) or floor_key(t["attached"])
        if key is None or t["planned_end"] is None:
            skipped.append(t["name"]); continue
        if key not in key_to_floor:
            skipped.append(f'{t["name"]} (tang {key} khong co trong IFC)'); continue
        f = key_to_floor[key]
        r = table.setdefault(f, {"planned_start": None, "planned_end": None, "actual_start": None,
                                 "actual_end": None, "n_tasks": 0})
        r["n_tasks"] += 1
        for k, fn in (("planned_start", min), ("planned_end", max), ("actual_start", min), ("actual_end", max)):
            v = t[k]
            if v is not None:
                r[k] = v if r[k] is None else fn(r[k], v)
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
    Mac dinh 'label' vi ten tap chon trong NWD cua nhom theo nhan tang; hay KIEM TRA bang cach mo mo phong
    TimeLiner o giua 1 task va xem cot nao duoc to mau.
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


def expected_built_mask(types, floors, table, date, in_progress="columns"):
    """
    Cau kien 'ke hoach cho rang da xay' tai ngay date: moi cau kien cua tang 'xong'.
    Tang 'dang_thi_cong': in_progress="columns" -> chi tinh COT (cot do truoc dam/san, giong built_mask
    trong simulate_asbuilt); "none" -> khong tinh gi (an toan hon khi chua biet thu tu thi cong trong 1 task).
    'floors' o day phai la chi so tang THEO LICH (xem element_schedule_floor).
    """
    st = floor_state(table, date)
    m = np.zeros(len(floors), dtype=bool)
    for f, s in st.items():
        if s == "xong":
            m |= floors == f
        elif s == "dang_thi_cong" and in_progress == "columns":
            m |= (floors == f) & (types == "IfcColumn")
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
    a = ap.parse_args()

    E, V, F, fe = load_bim(Path(a.data) / "plm_elements.json", Path(a.data) / "plm_meshes.npz")
    levels = slab_levels(E)
    km = storey_floor_map(E, levels)
    print("Tang IFC -> chi so tang:", {("-".join(map(str, k))): v for k, v in sorted(km.items(), key=lambda kv: kv[1])})
    tasks, style = read_timeliner_csv(a.csv)
    print(f"Doc {len(tasks)} task, kieu ngay: {style}")
    table, skipped = floor_schedule(tasks, km)
    print("\n tang  Z(m)   bat dau KH   ket thuc KH   so task")
    for f in sorted(table):
        r = table[f]
        print(f" {f:3d} {levels[f]:6.2f}   {r['planned_start']:%Y-%m-%d}   {r['planned_end']:%Y-%m-%d}   {r['n_tasks']}")
    if skipped:
        print(f"\nBo qua {len(skipped)} task (khong nhan dang duoc tang), vi du: {skipped[:5]}")
    d = datetime.strptime(a.date, "%Y-%m-%d") if a.date else datetime.now()
    print(f"\nTai {d:%Y-%m-%d}: tang cao nhat KH da xong = {planned_top_floor(table, d)}")