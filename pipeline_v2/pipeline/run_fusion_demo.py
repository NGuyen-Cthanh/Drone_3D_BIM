"""
run_fusion_demo.py - Kiem thu: lich -> nhieu lan quet -> ray-casting -> hop nhat -> so voi dap an.

Mo phong 3 lan quet cung 1 toa nha o cac thoi diem khac nhau (tang dang do = 3, 5, 7), moi lan:
  cloud KHO (lech thi cong 2 cm, luoi che, van khuon, che khuat HPR) + sai so dinh vi rieng
  -> dang ky vao BIM -> do bang chung bang ray-casting -> cap nhat trang thai.
Cuoi cung so 3 cach voi dap an cua LAN QUET CUOI:
  (1) coverage lan cuoi (cach cu)   (2) bang chung co nhin thay, chi lan cuoi   (3) hop nhat ca 3 lan.

    python run_fusion_demo.py --data data --schedule test/lich_timeliner_gia.csv
"""
import argparse, json, time
from datetime import timedelta
from pathlib import Path
import numpy as np

import config
from mesh_utils import load_bim, slab_levels, assign_floors, sample_surface
from simulate_asbuilt import built_mask, simulate_cloud, rigid_transform, apply, make_cameras
from registration import register, transform_error
from progress_evaluator import element_coverage, classify, confusion, BUILT
from schedule_loader import (read_timeliner_csv, storey_floor_map, floor_schedule, expected_built_mask,
                             planned_top_floor, element_schedule_floor)
from visibility import evidence
from fusion import FusionState, merge_epochs, PRESENT, CONFLICT, ABSENT, UNKNOWN

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=str(config.DATA_DIR))
ap.add_argument("--schedule", required=True)
ap.add_argument("--out", default=str(config.OUT_DIR))
ap.add_argument("--floor-mode", choices=["geometry", "label"], default="geometry",
                help="cach lich nhom cau kien: theo tang hinh hoc, hoac theo nhan tang Revit (cot lech +1 tang)")
ap.add_argument("--r-present", type=float, default=0.5)
ap.add_argument("--sched-mode", default="label", choices=["label", "geometry"],
                help="cach gan task lich vao cau kien (xem schedule_loader.element_schedule_floor)")
ap.add_argument("--hpr-voxel", type=float, default=0.5, help="voxel cho che khuat HPR khi mo phong; tang len neu cham/het RAM")
ap.add_argument("--epochs", default="3,5,7", help="tang dang do o moi lan quet, cach nhau dau phay")
args = ap.parse_args()
OUT = Path(args.out); OUT.mkdir(parents=True, exist_ok=True)
t0 = time.time()
def log(m): print(f"[{time.time()-t0:6.1f}s] {m}", flush=True)

E, V, F, fe = load_bim(Path(args.data) / "plm_elements.json", Path(args.data) / "plm_meshes.npz")
types = np.array([e["ifc_type"] for e in E]); vol = np.array([e["volume_m3"] for e in E])
levels = slab_levels(E); floors = assign_floors(E, levels)
tasks, style = read_timeliner_csv(args.schedule)
kmap = storey_floor_map(E, levels)
table, skipped = floor_schedule(tasks, kmap)
sched_floors = element_schedule_floor(E, floors, kmap, args.sched_mode)
log(f"Lich: {len(table)} tang co ke hoach, kieu ngay {style}; bo qua {len(skipped)} task khong gan tang")

Pb, Nb, tri_b = sample_surface(V, F, 15.0, np.random.default_rng(1))
cams_sim = make_cameras(V, standoff=35, n_ring=12, n_levels=4)       # may bay 'that' khi mo phong
cams_eval = make_cameras(V, standoff=50, n_ring=16, n_levels=4)      # may bay gia dinh khi danh gia (khac bo tren)
center = V.mean(0)

epochs = [int(x) for x in args.epochs.split(",")]
state = FusionState(len(E))
clouds_reg, truth_by_epoch, singles = [], [], []
for k, n_top in enumerate(epochs):
    if n_top not in table:
        log(f"Bo qua tang {n_top}: khong co trong lich (co: {sorted(table)})"); continue
    truth = built_mask(types, floors, n_top)
    date = table[n_top]["planned_start"] + timedelta(days=5)            # cot da do, dam/san dang lam
    occl = expected_built_mask(types, sched_floors, table, date)              # vat che theo LICH (khong dung dap an)
    nxt = (floors == n_top) & (types != "IfcColumn")
    rng = np.random.default_rng(100 + k)
    cloud = simulate_cloud(V, F, fe, truth, rng, deviation=0.02, scaffold=0.15, formwork_elems=nxt, cams=cams_sim, vis_voxel=args.hpr_voxel)
    Tk = rigid_transform(rng.uniform(-3, 3), rng.uniform(-2.5, 2.5, 3) * [1, 1, 0.3], center)
    cloud_d = apply(Tk, cloud)
    m = floors[fe[tri_b]] <= n_top
    T, fit, rm = register(cloud_d, Pb[m], Nb[m])
    e_t, e_a = transform_error(T, np.linalg.inv(Tk))
    cl = apply(T, cloud_d); clouds_reg.append(cl)
    ev = evidence(V, F, fe, len(E), cl, cams_eval, occl, density=8, voxel=0.4, k_cams=2)
    changed = state.update(k, ev["vis"], ev["r"], r_present=args.r_present)
    truth_by_epoch.append(truth)
    # chi dung lan quet nay (khong nho gi)
    s1 = FusionState(len(E)); s1.update(0, ev["vis"], ev["r"], r_present=args.r_present); singles.append(s1)
    log(f"Lan {k} (tang {n_top}, ngay {date:%Y-%m-%d}, lich noi tang <= {planned_top_floor(table, date)} xong): "
        f"{len(cl):,} diem, dang ky sai {e_t*100:.1f} cm | nhin thay>=25%: {(ev['vis']>=0.25).sum()}/{len(E)} "
        f"| doi trang thai: {changed} | {state.counts()}")

truth = truth_by_epoch[-1]
def report(name, status):
    pred = (status == PRESENT) | (status == CONFLICT)
    cm = confusion(np.where(pred, BUILT, 0), truth)
    unk = int(((status == UNKNOWN) & truth).sum())
    log(f"{name:34s} precision {cm['precision']:.3f}  recall {cm['recall']:.3f}  accuracy {cm['accuracy']:.3f}"
        f"  (FP {cm['FP']}, FN {cm['FN']}, da xay nhung 'chua ro' {unk})")
    return cm

print()
ev_last_cov = element_coverage(V, F, fe, len(E), clouds_reg[-1])[0]
res = {"epochs": epochs}
res["coverage_last_only"] = report("(1) coverage, chi lan cuoi", np.where(classify(ev_last_cov) == BUILT, PRESENT, ABSENT))
res["evidence_last_only"] = report("(2) co nhin thay, chi lan cuoi", singles[-1].status)
res["fused"] = report("(3) hop nhat ca %d lan" % len(epochs), state.status)

# phan tich: cau kien dung nho hop nhat (lan cuoi khong thay, nhung lan truoc da thay)
only_fused = truth & (state.status == PRESENT) & (singles[-1].status != PRESENT)
log(f"Cau kien CHI nho hop nhat moi biet la 'da xay': {int(only_fused.sum())} "
    f"(lan cuoi bi che / khong ro, lan truoc da nhin ro)")
conf = np.where(state.status == CONFLICT)[0]
log(f"CONFLICT can kiem tra thu cong: {len(conf)} (dap an that: {int((~truth[conf]).sum())} la chua xay)")

# cua so thoi gian xay vs dap an
first_true = np.full(len(E), -1)
for k in range(len(epochs) - 1, -1, -1):
    first_true[truth_by_epoch[k]] = k
ok = (state.first_present >= 0) & (first_true >= 0)
exact = (state.first_present[ok] == first_true[ok]).mean() if ok.any() else float("nan")
log(f"Lan quet dau tien thay cau kien trung voi lan quet that su xay: {100*exact:.1f}% (tren {int(ok.sum())} cau kien)")

# mo hinh tong
Pm, Em, Km = merge_epochs(clouds_reg, V, F, fe, state)
log(f"Mo hinh hop nhat: {len(Pm):,} diem (tong 3 lan: {sum(len(c) for c in clouds_reg):,}); diem theo lan: "
    f"{[int((Km==k).sum()) for k in range(len(epochs))]}")
cov_m = element_coverage(V, F, fe, len(E), Pm)[0]
pm = classify(cov_m) == BUILT
cm_m = confusion(np.where(pm, BUILT, 0), truth)
log(f"Coverage cua mo hinh hop nhat vs chi lan cuoi: recall {cm_m['recall']:.3f} vs {res['coverage_last_only']['recall']:.3f}")
res["merged_cloud_coverage"] = cm_m

np.savez_compressed(OUT / "fused_cloud.npz", points=Pm.astype(np.float32), element=Em, epoch=Km)
json.dump(res, open(OUT / "fusion_results.json", "w"), indent=1)
log(f"Da luu {OUT/'fusion_results.json'} va fused_cloud.npz")