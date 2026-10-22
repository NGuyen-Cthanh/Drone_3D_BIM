"""
progress_evaluator.py  (v2)
===========================
Danh gia tien do thi cong: cau kien BIM nao da duoc xay, dua tren point cloud thuc te
(da duoc dua ve he toa do BIM nho registration).

PHUONG PHAP  (huong "point cloud -> tung cau kien BIM", theo tinh than Tuttas et al. 2014)
  Voi moi cau kien: lay mau diem tren be mat cau kien trong BIM, roi do
  COVERAGE = ti le diem mau co du diem point cloud nam trong khoang 'tol'.
    coverage cao  -> cau kien da co mat o thuc te  -> "da xay"
    coverage thap -> khong co                       -> "chua xay"
  Cau kien o giua 2 nguong -> "khong chac chan" (can xem lai bang mat/anh).

THAY DOI SO VOI v1
  * element_coverage(min_pts=...): v1 chi can 1 diem bat ky trong 'tol' la tinh 'khop'. Voi du lieu that
    (outlier, gian giao, van khuon, can cau) 1 diem la qua de -> bao nham 'da xay'. Dat min_pts=3..5 khi
    mat do cloud du day (ODM o GSD ~1-2 cm). Voi cloud gia lap thua (60 diem/m2) giu min_pts=1.
  * Giai thich han che 'van khuon': van khuon dam/san nam dung cho cau kien se do -> hinh hoc KHONG
    phan biet duoc 'da do be tong' voi 'moi dung van khuon'. Chi biet bang cach dung them IFC van khuon
    (TS_FormWork) hoac phan loai mat cat/anh. Hay ghi vao bao cao.

DAU RA
  coverage_per_element, trang thai, tong hop theo tang (theo so luong VA theo the tich be tong),
  va so sanh voi lich thi cong du kien.
"""

import numpy as np
from scipy.spatial import cKDTree
from mesh_utils import sample_surface

BUILT, UNSURE, NOT_BUILT = 2, 1, 0
STATUS_NAME = {BUILT: "da xay", UNSURE: "khong chac", NOT_BUILT: "chua xay"}


def element_coverage(V, F, face_elem, n_elem, cloud, tol=0.10, density=60.0, seed=0, min_pts=1):
    """Coverage (0..1) cua tung cau kien + so diem mau dung de tinh."""
    rng = np.random.default_rng(seed)
    P, _, tri = sample_surface(V, F, density, rng)
    eid = face_elem[tri]

    tree = cKDTree(cloud)
    if min_pts <= 1:
        d, _ = tree.query(P, k=1, distance_upper_bound=tol, workers=-1)
        hit = np.isfinite(d)
    else:
        hit = tree.query_ball_point(P, r=tol, return_length=True, workers=-1) >= min_pts

    n = np.bincount(eid, minlength=n_elem)
    h = np.bincount(eid, weights=hit, minlength=n_elem)
    cov = np.divide(h, n, out=np.zeros(n_elem), where=n > 0)
    return cov, n


def classify(coverage, t_built=0.30, t_not=0.10):
    st = np.full(len(coverage), UNSURE, dtype=np.int8)
    st[coverage >= t_built] = BUILT
    st[coverage <= t_not] = NOT_BUILT
    return st


def summarize_by_floor(E, floors, levels, status, volumes):
    """Bang tong hop theo tang: so cau kien da xay / tong, % theo so luong va % theo the tich."""
    rows = []
    for i in range(len(levels)):
        m = floors == i
        if not m.any():
            continue
        built = m & (status == BUILT)
        rows.append({
            "floor": i, "level_m": round(float(levels[i]), 2),
            "total": int(m.sum()), "built": int(built.sum()),
            "unsure": int((m & (status == UNSURE)).sum()),
            "pct_count": round(100 * built.sum() / m.sum(), 1),
            "pct_volume": round(100 * volumes[built].sum() / max(volumes[m].sum(), 1e-9), 1),
        })
    return rows


def overall_progress(status, volumes):
    b = status == BUILT
    return {
        "pct_count": round(float(100 * b.sum() / len(status)), 2),
        "pct_volume": round(float(100 * volumes[b].sum() / volumes.sum()), 2),
        "volume_built_m3": round(float(volumes[b].sum()), 1),
        "volume_total_m3": round(float(volumes.sum()), 1),
    }


def confusion(status, truth_built):
    """Doi chieu voi ground truth (chi co khi du lieu mo phong). 'khong chac' tinh la KHONG xay."""
    pred = status == BUILT
    tp = int((pred & truth_built).sum()); fp = int((pred & ~truth_built).sum())
    fn = int((~pred & truth_built).sum()); tn = int((~pred & ~truth_built).sum())
    return {"TP": tp, "FP": fp, "FN": fn, "TN": tn,
            "precision": round(tp / max(tp + fp, 1), 4),
            "recall": round(tp / max(tp + fn, 1), 4),
            "accuracy": round((tp + tn) / len(status), 4)}


def compare_with_schedule(status, floors, planned_floor_of_date, min_frac=0.8):
    """
    So voi tien do DU KIEN. 'planned_floor_of_date' = chi so tang cao nhat lich yeu cau da xong
    tai ngay bao cao (doc tu TimeLiner/Navisworks, xem README). Tra ve ket luan + danh sach tre.
    """
    expected = floors <= planned_floor_of_date
    built = status == BUILT
    delayed = expected & ~built
    ahead = built & ~expected
    # "tang hien tai" = tang cao nhat co it nhat min_frac cau kien da xay (tranh tinh tang chi moi do cot)
    actual_top = -1
    for f in np.unique(floors):
        m = floors == f
        if built[m].mean() >= min_frac:
            actual_top = max(actual_top, int(f))
    return {
        "planned_top_floor": int(planned_floor_of_date),
        "actual_top_floor": actual_top,
        "floors_behind": int(planned_floor_of_date - actual_top),
        "n_expected": int(expected.sum()),
        "n_delayed": int(delayed.sum()),
        "n_ahead": int(ahead.sum()),
        "delayed_idx": np.where(delayed)[0],
    }

def compare_with_plan(is_built, expected, sched_floors, scheduled=None, unknown=None):
    """
    So ket qua do duoc voi KE HOACH tai ngay bao cao (thay cho compare_with_schedule khi da co lich that).
      is_built  : bool/cau kien - ket luan 'da xay' (vd status == BUILT, hoac PRESENT|CONFLICT tu fusion)
      expected  : bool/cau kien - schedule_loader.expected_built_mask(...) tai ngay bao cao
      sched_floors : chi so tang theo NHAN (schedule_loader.element_schedule_floor)
      scheduled : bool/cau kien - cau kien co thuoc task nao trong lich; cau kien ngoai lich bi loai khoi so sanh
      unknown   : bool/cau kien - drone KHONG kiem chung duoc (bi che, fusion.UNKNOWN). Khong bao la tre: day la
                  'chua kiem chung', khong phai 'chua xay'. Drone chi thay mat ngoai nen nhom nay thuong rat lon.
    Tra ve dict: tre (ke hoach da xong, da nhin du ro ma KHONG thay), chua_kiem_chung (ke hoach da xong nhung bi che),
                 vuot (thay roi ma ke hoach chua toi), theo tang.
    """
    ok = np.ones(len(is_built), dtype=bool) if scheduled is None else np.asarray(scheduled, dtype=bool)
    exp, blt = np.asarray(expected) & ok, np.asarray(is_built) & ok
    unk = np.zeros(len(exp), dtype=bool) if unknown is None else np.asarray(unknown, dtype=bool)
    delayed, ahead = exp & ~blt & ~unk, blt & ~np.asarray(expected)
    unverified = exp & ~blt & unk
    by = {}
    for f in np.unique(sched_floors[ok]):
        m = (sched_floors == f) & ok
        by[int(f)] = {"n": int(m.sum()), "expected": int(exp[m].sum()), "built": int(blt[m].sum()),
                      "delayed": int(delayed[m].sum()), "unverified": int(unverified[m].sum()), "ahead": int(ahead[m & blt].sum())}
    return {"n_in_schedule": int(ok.sum()), "n_expected": int(exp.sum()), "n_built": int(blt.sum()),
            "n_delayed": int(delayed.sum()), "n_unverified": int(unverified.sum()), "n_ahead": int(ahead.sum()),
            "pct_of_plan_confirmed": round(100 * (exp & blt).sum() / max(exp.sum(), 1), 1),
            "delayed_idx": np.where(delayed)[0], "by_floor": by}