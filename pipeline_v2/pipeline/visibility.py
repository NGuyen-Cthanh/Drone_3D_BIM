"""
visibility.py
=============
Do DO NHIN THAY cua tung cau kien BIM bang ray-casting (thay cho HPR xap xi trong simulate_asbuilt).

Y TUONG
  Lay mau diem tren be mat moi cau kien (kem phap tuyen). Mot diem mau la "nhin thay" neu co it nhat 1
  may bay (trong 'cams') ma (a) diem huong ve may bay do (phap tuyen . huong nhin > 0) va
  (b) tia tu diem toi may bay khong bi hinh hoc che (cac cau kien 'occluders') chan.
  Cau kien: vis = ti le diem mau nhin thay;  r = ti le diem NHIN THAY ma co diem point cloud trong 'tol'.
  => 'r' moi la bang chung dung: khong nhin thay thi khong the ket luan 'chua co'.

BACKEND
  'numpy'  : luoi voxel + buoc tia (da kiem thu). Xap xi theo kich thuoc voxel (mac dinh 0.3 m), chay duoc
             khong can thu vien ngoai.
  'open3d' : RaycastingScene tren mesh that (chinh xac, nhanh hon nhieu). CHUA kiem thu o moi truong cua
             minh (khong co open3d) - neu loi se tu dong quay ve numpy va in canh bao.
  'auto'   : open3d neu co, khong thi numpy.

GIOI HAN
  - 'occluders' la cau kien BIM duoc cho la da xay tai thoi diem do (lay tu lich hoac ket qua truoc).
    Khong co gian giao, can cau, cay, nha ben canh -> do nhin thay la CAN TREN.
  - Toa do may bay 'cams' phai o he toa do BIM. Voi bay that, lay vi tri anh tu EXIF/MRK/ODM roi
    ap phep bien doi dang ky (T) len chung.
"""
import numpy as np
from scipy.spatial import cKDTree
from mesh_utils import sample_surface

try:
    import open3d as o3d
except ImportError:
    o3d = None


def _grid(points, voxel):
    lo = points.min(0) - 2 * voxel
    ijk = np.floor((points - lo) / voxel).astype(np.int64)
    dims = ijk.max(0) + 3
    key = ijk[:, 0] + dims[0] * (ijk[:, 1] + dims[1] * ijk[:, 2])
    return {"lo": lo, "dims": dims, "voxel": voxel, "occ": np.unique(key)}


def _occupied(g, pts):
    ijk = np.floor((pts - g["lo"]) / g["voxel"]).astype(np.int64)
    inside = np.all((ijk >= 0) & (ijk < g["dims"]), axis=1)
    key = ijk[:, 0] + g["dims"][0] * (ijk[:, 1] + g["dims"][1] * ijk[:, 2])
    pos = np.searchsorted(g["occ"], key)
    pos = np.minimum(pos, len(g["occ"]) - 1)
    return inside & (g["occ"][pos] == key)


def _clear_numpy(origin, target, g):
    """True neu doan origin->target khong cat voxel co vat the."""
    d = target - origin
    dist = np.linalg.norm(d, axis=1)
    u = d / np.maximum(dist, 1e-9)[:, None]
    step = g["voxel"] * 0.8
    clear = np.ones(len(origin), dtype=bool)
    t = 0.0
    tmax = dist.max()
    while t < tmax:
        act = np.where(clear & (dist > t))[0]
        if len(act) == 0:
            break
        clear[act[_occupied(g, origin[act] + u[act] * t)]] = False
        t += step
    return clear


def _clear_open3d(origin, target, Vo, Fo):
    scene = o3d.t.geometry.RaycastingScene()
    scene.add_triangles(o3d.core.Tensor(Vo.astype(np.float32)), o3d.core.Tensor(Fo.astype(np.uint32)))
    d = target - origin
    dist = np.linalg.norm(d, axis=1)
    rays = np.hstack([origin, d / np.maximum(dist, 1e-9)[:, None]]).astype(np.float32)
    t = scene.cast_rays(o3d.core.Tensor(rays))["t_hit"].numpy()
    return t > (dist - 1e-3)


def visible_samples(P, N, cams, occ_V, occ_F, occ_pts, voxel=0.3, k_cams=4, eps=None, backend="auto", chunk=40000):
    """Co mang bool: diem mau i co nhin thay tu it nhat 1 trong 'k_cams' may bay huong ve no nhat khong."""
    cams = np.atleast_2d(cams)
    eps = 1.5 * voxel if eps is None else eps
    kk = min(k_cams, cams.shape[0])
    use_o3d = backend == "open3d" or (backend == "auto" and o3d is not None)
    g = None if use_o3d else _grid(occ_pts, voxel)
    vis = np.zeros(len(P), dtype=bool)
    for s0 in range(0, len(P), chunk):                           # chia khoi de khong het RAM
        Pc, Nc = P[s0:s0 + chunk], N[s0:s0 + chunk]
        to = cams[None, :, :] - Pc[:, None, :]                   # n x M x 3
        dist = np.linalg.norm(to, axis=2)
        cos = np.einsum("nmk,nk->nm", to, Nc) / np.maximum(dist, 1e-9)
        top = np.argpartition(-cos, kk - 1, axis=1)[:, :kk]
        cand = np.take_along_axis(cos, top, 1) > 0.05            # chi may bay ma be mat huong ve
        ii, jj = np.where(cand)
        if len(ii) == 0:
            continue
        org = Pc[ii] + Nc[ii] * eps                              # day tia ra khoi be mat cua chinh no
        tgt = cams[top[ii, jj]]
        clear = None
        if use_o3d:
            try:
                clear = _clear_open3d(org, tgt, occ_V, occ_F)
            except Exception as ex:                              # noqa
                print(f"[visibility] open3d ray-casting loi ({ex}); dung numpy")
                use_o3d = False
                g = _grid(occ_pts, voxel)
        if clear is None:
            clear = _clear_numpy(org, tgt, g)
        v = np.zeros(len(Pc), dtype=bool)
        np.logical_or.at(v, ii, clear)
        vis[s0:s0 + chunk] = v
    return vis


def evidence(V, F, face_elem, n_elem, cloud, cams, occluders, tol=0.10, density=40.0, occ_density=100.0,
             voxel=0.3, k_cams=4, min_pts=1, seed=0, backend="auto"):
    """
    Bang chung cho tung cau kien tu MOT lan quet (cloud da dang ky vao he toa do BIM).
      occluders : mang bool theo cau kien - cau kien dung lam vat che (dang tin la da xay)
    Tra ve dict: vis (ti le be mat nhin thay), r (ti le diem nhin thay co trong cloud), n_vis (so diem nhin thay),
                 cov (coverage khong tinh nhin thay - so sanh voi progress_evaluator).
    """
    rng = np.random.default_rng(seed)
    P, N, tri = sample_surface(V, F, density, rng)
    eid = face_elem[tri]

    fo = occluders[face_elem]
    occ_P, _, _ = sample_surface(V, F[fo], occ_density, np.random.default_rng(seed + 1))
    vis_s = visible_samples(P, N, cams, V, F[fo], occ_P, voxel, k_cams, backend=backend)

    tree = cKDTree(cloud)
    if min_pts <= 1:
        hit = np.isfinite(tree.query(P, k=1, distance_upper_bound=tol, workers=-1)[0])
    else:
        hit = tree.query_ball_point(P, r=tol, return_length=True, workers=-1) >= min_pts

    n = np.bincount(eid, minlength=n_elem)
    nv = np.bincount(eid, weights=vis_s, minlength=n_elem)
    hv = np.bincount(eid, weights=(vis_s & hit), minlength=n_elem)
    ha = np.bincount(eid, weights=hit, minlength=n_elem)
    return {"vis": np.divide(nv, n, out=np.zeros(n_elem), where=n > 0),
            "r": np.divide(hv, nv, out=np.zeros(n_elem), where=nv > 0),
            "n_vis": nv.astype(int),
            "cov": np.divide(ha, n, out=np.zeros(n_elem), where=n > 0)}
