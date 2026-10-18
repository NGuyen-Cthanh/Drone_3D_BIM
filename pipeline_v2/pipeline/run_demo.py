"""
run_demo.py (v2) - Chay thu toan bo luong: BIM -> point cloud gia lap -> registration -> danh gia tien do.
Muc dich: kiem chung phuong phap tren du lieu co DAP AN truoc khi co anh drone that.

Cach chay:
    python run_demo.py --data data --out results --n-top 8
  (data/ chua plm_elements.json + plm_meshes.npz do bim_loader.py tao ra)
"""
import argparse, json, time
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from mesh_utils import load_bim, slab_levels, assign_floors, sample_surface
from simulate_asbuilt import built_mask, simulate_cloud, rigid_transform, apply, make_cameras
from registration import register, transform_error, o3d
from progress_evaluator import (element_coverage, classify, confusion, overall_progress,
                                summarize_by_floor, compare_with_schedule, BUILT, UNSURE)

ap = argparse.ArgumentParser()
ap.add_argument("--data", default=str(config.DATA_DIR))
ap.add_argument("--out", default=str(config.OUT_DIR))
ap.add_argument("--n-top", type=int, default=8, help="tang dang do (gia lap)")
ap.add_argument("--skip-realistic", action="store_true", help="bo thi nghiem E (che khuat HPR, cham)")
args = ap.parse_args()

DATA, OUT = Path(args.data), Path(args.out)
OUT.mkdir(parents=True, exist_ok=True)
N_TOP = args.n_top
t0 = time.time()
def log(msg): print(f"[{time.time()-t0:6.1f}s] {msg}", flush=True)
log("ICP: open3d" if o3d is not None else "ICP: fallback numpy (khong co open3d)")

E, V, F, fe = load_bim(DATA / "plm_elements.json", DATA / "plm_meshes.npz")
types = np.array([e["ifc_type"] for e in E]); vol = np.array([e["volume_m3"] for e in E])
levels = slab_levels(E); floors = assign_floors(E, levels)
log(f"{len(E)} cau kien, {len(levels)} cao do tang: {levels.round(1)[:6]}...")
built = built_mask(types, floors, N_TOP)
log(f"Gia lap: xay den tang {N_TOP} (Z={levels[N_TOP]:.1f} m): {built.sum()}/{len(E)} cau kien da xay "
    f"({100*vol[built].sum()/vol.sum():.1f}% the tich be tong)")

rng = np.random.default_rng(42)
cloud_bim = simulate_cloud(V, F, fe, built, rng)
log(f"Point cloud gia lap (de): {len(cloud_bim):,} diem")

Pb, Nb, tri_b = sample_surface(V, F, 15.0, np.random.default_rng(1))
log(f"Target BIM cho ICP: {len(Pb):,} diem")
center = V.mean(0)

# ---- A: sai so dinh vi kieu GPS, target = CA TOA NHA ----
T_true = rigid_transform(4.0, (3.5, -2.8, 1.2), center)
cloud_drone = apply(T_true, cloud_bim)
T_est, fit, rmse = register(cloud_drone, Pb, Nb)
dt, da = transform_error(T_est, np.linalg.inv(T_true))
log(f"[A]  target=ca toa nha      : sai {dt*100:.1f} cm, {da:.3f} do | fitness={fit:.3f} rmse={rmse*100:.1f} cm")

# ---- A2: target = CHI phan BIM co the da xay (tang <= N_TOP), ICP ben vung (Tukey o muc min) ----
m_tgt = floors[fe[tri_b]] <= N_TOP
T_est2, fit2, rmse2 = register(cloud_drone, Pb[m_tgt], Nb[m_tgt], robust_k=0.15)
dt2, da2 = transform_error(T_est2, np.linalg.inv(T_true))
log(f"[A2] target=tang <= N + Tukey: sai {dt2*100:.1f} cm, {da2:.3f} do | fitness={fit2:.3f} rmse={rmse2*100:.1f} cm")

# ---- B: do nhay theo sai so CAO DO ban dau ----
sweep = []
for dz in [0.5, 1.0, 1.65, 2.5, 3.3, 4.5]:
    Tt = rigid_transform(0.0, (0, 0, dz), center)
    Te, f, r = register(apply(Tt, cloud_bim), Pb, Nb)
    e_t, _ = transform_error(Te, np.linalg.inv(Tt)); sweep.append((dz, e_t))
    log(f"[B]  sai cao do ban dau {dz:4.2f} m -> sai sau ICP {e_t:6.3f} m (fitness {f:.3f})")

# ---- C: danh gia tien do tren cloud DE (can tren) ----
cloud_reg = apply(T_est, cloud_drone)
cov, ns = element_coverage(V, F, fe, len(E), cloud_reg)
st = classify(cov, config.T_BUILT, config.T_NOT)
cm = confusion(st, built); log(f"[C]  cloud de: {cm}")
prog = overall_progress(st, vol)
log(f"[C]  tien do uoc luong: {prog}  | that: {100*vol[built].sum()/vol.sum():.2f}% the tich")
cm0 = confusion(classify(element_coverage(V, F, fe, len(E), cloud_drone)[0]), built)
log(f"[C'] neu BO QUA registration: {cm0}")

# ---- E: cloud KHO (lech thi cong + gian giao + van khuon + che khuat) ----
cm_hard = None
if not args.skip_realistic:
    nxt = (floors == N_TOP) & (types != "IfcColumn")            # dam/san tang dang do: da dung van khuon, chua do
    cams = make_cameras(V)
    cloud_h = simulate_cloud(V, F, fe, built, np.random.default_rng(7), deviation=0.02, scaffold=0.15,
                             formwork_elems=nxt, cams=cams)
    Th = rigid_transform(3.0, (2.0, -1.5, 0.8), center)
    cloud_h_d = apply(Th, cloud_h)
    Te, fh, rh = register(cloud_h_d, Pb[m_tgt], Nb[m_tgt], robust_k=0.15)
    eh = transform_error(Te, np.linalg.inv(Th))
    log(f"[E]  cloud kho {len(cloud_h):,} diem; registration sai {eh[0]*100:.1f} cm, {eh[1]:.2f} do")
    covh, _ = element_coverage(V, F, fe, len(E), apply(Te, cloud_h_d))
    sth = classify(covh, config.T_BUILT, config.T_NOT)
    cm_hard = confusion(sth, built)
    fp_form = int(((sth == BUILT) & nxt).sum())
    log(f"[E]  doi chieu: {cm_hard}")
    log(f"[E]  trong {cm_hard['FP']} bao nham, {fp_form}/{int(nxt.sum())} "
        f"la cau kien dang dung van khuon (hinh hoc khong phan biet duoc)")

rows = summarize_by_floor(E, floors, levels, st, vol)
print("\n tang  Z(m)   da_xay/tong  %SL    %TheTich")
for r in rows: print(f" {r['floor']:3d} {r['level_m']:6.2f}  {r['built']:4d}/{r['total']:<4d}  {r['pct_count']:5.1f}  {r['pct_volume']:6.1f}")

sc = compare_with_schedule(st, floors, N_TOP + 1)
sc_print = {k: v for k, v in sc.items() if k != "delayed_idx"}
log(f"[D]  so voi lich (gia su lich yeu cau xong den tang {N_TOP+1}): {sc_print}")

json.dump({"truth_top_floor": N_TOP,
           "registration_A": {"err_cm": dt*100, "err_deg": da, "fitness": fit, "rmse_cm": rmse*100},
           "registration_A2": {"err_cm": dt2*100, "err_deg": da2, "fitness": fit2},
           "z_sweep": sweep, "confusion_easy": cm, "confusion_no_registration": cm0,
           "confusion_hard": cm_hard, "overall": prog, "by_floor": rows, "schedule_compare": sc_print},
          open(OUT / "demo_results.json", "w"), indent=1, ensure_ascii=False)

C = np.array([e["centroid"] for e in E])
fig, ax = plt.subplots(1, 3, figsize=(17, 6.2), sharey=True)
def panel(a, col, title): a.scatter(C[:, 1], C[:, 2], s=4, c=col); a.set_title(title); a.set_xlabel("Y (m)")
panel(ax[0], np.where(built, "#2ca02c", "#cccccc"), "Thuc te gia lap (xanh = da xay)")
panel(ax[1], np.where(st == BUILT, "#2ca02c", np.where(st == UNSURE, "#ff7f0e", "#cccccc")), "Danh gia (cam = khong chac)")
panel(ax[2], np.where((st == BUILT) & ~built, "#d62728", np.where((st != BUILT) & built, "#1f77b4", "#e8e8e8")),
      "Sai: do = bao nham, xanh duong = bo sot")
ax[0].set_ylabel("Z (m)"); plt.tight_layout(); plt.savefig(OUT / "demo_progress.png", dpi=110)
log(f"Xong. Da luu {OUT/'demo_results.json'} , demo_progress.png")