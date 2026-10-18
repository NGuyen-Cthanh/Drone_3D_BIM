"""
registration.py  (v2)
=====================
Can chinh (register) point cloud tu drone voi he toa do cua mo hinh BIM.

QUY TRINH
  1. Giam mat do diem (voxel) de chay nhanh
  2. (tuy chon) Can tho TOAN CUC bang FPFH + RANSAC: khi chua biet vi tri ban dau
  3. Tinh chinh bang ICP point-to-plane, nhieu muc (tho -> min): 2.0 m -> 0.5 m -> 0.15 m

Ket qua T (4x4) bien doi diem tu he toa do drone  ->  he toa do BIM.

THAY DOI SO VOI v1
  * robust_k: dung ham mat mat ben vung (Tukey) de outlier / gian giao / van khuon khong keo lech ICP.
    v1 dung ICP thuan -> 1 mang gian giao co the keo lech ca bo.
  * register(...) nen duoc goi voi muc tieu CHI GOM PHAN BIM DA CHAC CHAN CO (cac tang duoi), khong phai
    ca toa nha: phan chua xay khong co diem tuong ung, chi lam nhieu.  Xem run_demo.py thi nghiem A2.
  * umeyama(): tim phep bien doi CO SCALE tu cac cap diem tuong ung (GCP <-> diem trong BIM). Ma tran
    cua register() chi la rigid (khong scale); neu anh khong co RTK thi scale co the lech -> dung ham nay.
  * Neu khong cai open3d thi tu dong dung ICP viet bang numpy/scipy (cham hon, dung de kiem thu).

LUU Y QUAN TRONG
  ICP chi hoi tu dung neu vi tri ban dau gan dung. Toa nha co cac tang LAP LAI
  (cach nhau ~3.3 m) nen neu sai so cao do ban dau ~ 1 chu ky tang, ICP de khop
  nham tang nay voi tang kia. Vi vay cao do (Z) can duoc khoa bang GPS/RTK hoac GCP.
"""

import numpy as np
from scipy.spatial import cKDTree

try:
    import open3d as o3d
except ImportError:          # chay duoc bang fallback numpy
    o3d = None


# ----------------------------------------------------------------- Open3D
def make_pcd(P, normals=None):
    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(np.asarray(P, dtype=np.float64))
    if normals is not None:
        pcd.normals = o3d.utility.Vector3dVector(np.asarray(normals, dtype=np.float64))
    return pcd


def global_register(src, tgt, voxel):
    """Can tho khong can vi tri ban dau: FPFH + RANSAC (Open3D)."""
    def prep(p):
        d = p.voxel_down_sample(voxel)
        d.estimate_normals(o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 2, max_nn=30))
        f = o3d.pipelines.registration.compute_fpfh_feature(
            d, o3d.geometry.KDTreeSearchParamHybrid(radius=voxel * 5, max_nn=100))
        return d, f

    s, fs = prep(src)
    t, ft = prep(tgt)
    dist = voxel * 1.5
    res = o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        s, t, fs, ft, True, dist,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False), 3,
        [o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(0.9),
         o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(dist)],
        o3d.pipelines.registration.RANSACConvergenceCriteria(2_000_000, 0.999))
    return res.transformation


def _p2plane(robust_k):
    reg = o3d.pipelines.registration
    if robust_k:
        try:
            return reg.TransformationEstimationPointToPlane(reg.TukeyLoss(k=robust_k))
        except Exception:    # phien ban open3d cu khong co TukeyLoss
            pass
    return reg.TransformationEstimationPointToPlane()


def icp_refine(src, tgt, init, thresholds=(2.0, 0.5, 0.15), max_iter=60, robust_k=None):
    """ICP point-to-plane da muc. Target can co phap tuyen (lay tu mesh BIM)."""
    T = np.array(init, dtype=np.float64)
    res = None
    for thr in thresholds:
        k = robust_k if (robust_k and thr <= 0.5) else None    # Tukey chi o cac muc min (da gan dung)
        res = o3d.pipelines.registration.registration_icp(
            src, tgt, thr, T, _p2plane(k),
            o3d.pipelines.registration.ICPConvergenceCriteria(max_iteration=max_iter))
        T = res.transformation
    return T, res.fitness, res.inlier_rmse


# ----------------------------------------------------------------- fallback numpy
def _voxel_down(P, N, voxel):
    key = np.floor(P / voxel).astype(np.int64)
    _, idx = np.unique(key, axis=0, return_index=True)
    return P[idx], (None if N is None else N[idx])


def _exp_se3(x):
    w, t = x[:3], x[3:]
    th = np.linalg.norm(w)
    K = np.array([[0, -w[2], w[1]], [w[2], 0, -w[0]], [-w[1], w[0], 0]])
    if th < 1e-12:
        R = np.eye(3) + K
    else:
        R = np.eye(3) + np.sin(th) / th * K + (1 - np.cos(th)) / th**2 * (K @ K)
    T = np.eye(4); T[:3, :3] = R; T[:3, 3] = t
    return T


def icp_numpy(src, tgt, tgt_n, init, thresholds=(2.0, 0.5, 0.15), max_iter=40, robust_k=None):
    """ICP point-to-plane (tuyen tinh hoa goc nho) + trong so Tukey tuy chon. Tra ve (T, fitness, rmse)."""
    tree = cKDTree(tgt)
    T = np.array(init, dtype=np.float64)
    fit, rmse = 0.0, np.inf
    for thr in thresholds:
        for _ in range(max_iter):
            p = src @ T[:3, :3].T + T[:3, 3]
            d, j = tree.query(p, distance_upper_bound=thr, workers=-1)
            m = np.isfinite(d)
            fit = float(m.mean())
            if m.sum() < 10:
                break
            pm, q, n = p[m], tgt[j[m]], tgt_n[j[m]]
            r = np.einsum("ij,ij->i", pm - q, n)
            rmse = float(np.sqrt(np.mean(d[m] ** 2)))
            w = np.ones(len(r))
            if robust_k:
                if thr <= 0.5:                                    # Tukey chi o cac muc min (da gan dung)
                    w = np.where(np.abs(r) < robust_k, (1 - (r / robust_k) ** 2) ** 2, 0.0)
            A = np.hstack([np.cross(pm, n), n])
            x = np.linalg.solve((A * w[:, None]).T @ A + 1e-9 * np.eye(6), -(A * w[:, None]).T @ r)
            T = _exp_se3(x) @ T
            if np.linalg.norm(x) < 1e-7:
                break
    return T, fit, rmse


# ----------------------------------------------------------------- API chinh
def register(asbuilt_pts, bim_pts, bim_normals, init=None, voxel=0.3,
             use_global=False, robust_k=None):
    """
    asbuilt_pts : Nx3 point cloud tu drone (he toa do drone)
    bim_pts, bim_normals : diem + phap tuyen lay mau tu mesh BIM (he toa do BIM).
                           Nen CHI gom phan BIM da chac chan co (cac tang duoi).
    init        : ma tran 4x4 uoc luong ban dau (vd tu GPS); None = don vi
    robust_k    : nguong Tukey (m), vd 0.10-0.15; None = ICP thuan
    Tra ve (T, fitness, rmse)
    """
    init = np.eye(4) if init is None else init
    if o3d is None:
        if use_global:
            raise RuntimeError("use_global can open3d")
        s, _ = _voxel_down(np.asarray(asbuilt_pts), None, voxel)
        t, tn = _voxel_down(np.asarray(bim_pts), np.asarray(bim_normals), voxel)
        return icp_numpy(s, t, tn, init, robust_k=robust_k)

    src = make_pcd(asbuilt_pts).voxel_down_sample(voxel)
    tgt = make_pcd(bim_pts, bim_normals).voxel_down_sample(voxel)
    if use_global:
        init = global_register(src, tgt, voxel * 3)
    return icp_refine(src, tgt, init, robust_k=robust_k)


def transform_error(T_est, T_true):
    """Sai so giua phep bien doi uoc luong va dung: (do lech tinh tien m, goc quay do)."""
    D = np.linalg.inv(T_true) @ T_est
    ang = np.degrees(np.arccos(np.clip((np.trace(D[:3, :3]) - 1) / 2, -1, 1)))
    return float(np.linalg.norm(D[:3, 3])), float(ang)


def umeyama(src, dst, with_scale=True):
    """
    Phep dong dang tot nhat dst ~ s*R*src + t tu cac cap diem tuong ung (>= 3 diem khong thang hang).
    Dung cho GCP: src = toa do diem khong che trong cloud, dst = toa do cung diem trong BIM / do dac.
    Tra ve (s, R, t). Ap dung: dst = s * (R @ p) + t
    """
    src, dst = np.asarray(src, float), np.asarray(dst, float)
    mu_s, mu_d = src.mean(0), dst.mean(0)
    S, D = src - mu_s, dst - mu_d
    U, sig, Vt = np.linalg.svd(D.T @ S / len(src))
    Sg = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        Sg[2, 2] = -1
    R = U @ Sg @ Vt
    s = float((sig * np.diag(Sg)).sum() / ((S ** 2).sum() / len(src))) if with_scale else 1.0
    t = mu_d - s * R @ mu_s
    return s, R, t