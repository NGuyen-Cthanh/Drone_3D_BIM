"""
check_levels.py - Kiem tra cach gan tang truoc khi chay run_demo / fusion.
    python pipeline\\check_levels.py            (doc data\\plm_elements.json, plm_meshes.npz)
In ra:
  1. Cac cao do tang tim duoc tu mat san (so luong, khoang cach, so san moi cao do)
  2. So cau kien theo tung loai o moi tang HINH HOC
  3. So sanh NHAN TANG trong IFC voi tang hinh hoc, theo tung loai (phat hien lech 1 tang cua COT,
     va cac cau kien gan nhan sai tang)
"""
import argparse
from collections import Counter
from pathlib import Path
import numpy as np
import config
from mesh_utils import load_bim, slab_levels, assign_floors
from schedule_loader import storey_floor_map, floor_key

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=str(config.DATA_DIR))
a = ap.parse_args()
E, V, F, fe = load_bim(Path(a.data) / "plm_elements.json", Path(a.data) / "plm_meshes.npz")
types = np.array([e["ifc_type"] for e in E])
levels = slab_levels(E)
floors = assign_floors(E, levels)

print(f"\n=== 1. {len(levels)} cao do tang tu mat san ===")
zs = np.array([e["bbox"]["max"][2] for e in E if e["ifc_type"] == "IfcSlab"])
for i, z in enumerate(levels):
    n = int(np.sum(np.argmin(np.abs(zs[:, None] - levels[None]), 1) == i))
    gap = "" if i == 0 else f"  (cach tang duoi {levels[i]-levels[i-1]:.2f} m)"
    print(f"  tang {i:2d}: Z = {z:6.2f} m | {n:3d} san{gap}")
print("  -> Ky vong: khoang cach ~3.3 m (tang 1-2 co the 4.6 m). Khoang cach la (<2 m) la dau hieu tach nham.")

print("\n=== 2. So cau kien theo tang hinh hoc ===")
print("  tang  Z(m)    dam  cot  san")
for i in range(len(levels)):
    m = floors == i
    print(f"  {i:3d} {levels[i]:6.2f}  {int((m&(types=='IfcBeam')).sum()):4d} {int((m&(types=='IfcColumn')).sum()):4d} {int((m&(types=='IfcSlab')).sum()):4d}")

print("\n=== 3. Nhan tang IFC so voi tang hinh hoc ===")
km = storey_floor_map(E, levels)
print("  nhan IFC -> chi so tang (theo trung vi cao do san cua nhan do):")
labels = sorted({e["storey"] for e in E if e["storey"]}, key=lambda s: km.get(floor_key(s), 999))
for s in labels:
    k = floor_key(s)
    print(f"    {s:28s} -> {km.get(k, 'khong co san de suy ra')}")
print("\n  chenh lech (tang hinh hoc - tang theo nhan), theo loai:")
for t in ("IfcBeam", "IfcColumn", "IfcSlab"):
    c = Counter()
    for e, f in zip(E, floors):
        if e["ifc_type"] != t or e["storey"] is None:
            continue
        k = floor_key(e["storey"])
        if k in km:
            c[int(f) - km[k]] += 1
    print(f"    {t:10s}: " + ", ".join(f"{d:+d}: {n}" for d, n in sorted(c.items())))
print("  -> Cot thuong lech +1 neu Revit gan cot theo cao do CHAN cot; dam/san nen = 0.")
print("     Neu cot lech +1 thi 'cot TANG n' trong lich co the la cot nam TREN san n (tang hinh hoc n+1).")

bad = []
for e, f in zip(E, floors):
    k = floor_key(e["storey"]) if e["storey"] else None
    if k in km and abs(int(f) - km[k]) >= 3:
        bad.append((e["global_id"], e["ifc_type"], e["storey"], km[k], int(f), round(e["bbox"]["max"][2], 1)))
print(f"\n  Cau kien lech >= 3 tang so voi nhan ({len(bad)}), 15 dong dau (GlobalId, loai, nhan, tang nhan, tang hinh hoc, z_max):")
for b in bad[:15]:
    print("   ", b)
