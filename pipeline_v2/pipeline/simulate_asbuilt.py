"""
simulate_asbuilt.py  (v2)
=========================
Sinh point cloud "nhu drone chup" cho 1 toa nha dang thi cong den tang N, TU CHINH
MO HINH BIM, de kiem thu registration + progress_evaluator khi chua co anh that.
Vi biet chinh xac cau kien nao da xay (ground truth) nen do duoc do chinh xac.

v1 chi co: bo mat huong xuong + roi ngau nhien + nhieu Gauss + outlier  -> qua DE (ket qua 100%).
v2 them cac yeu to khien bai toan KHO GIONG THUC TE (deu la tuy chon, mac dinh tat):
  deviation     : moi cau kien lech rieng 1 doan ~N(0, deviation) so voi BIM (sai lech thi cong, as-built != thiet ke)
  scaffold      : 'luoi che / gian giao' dang tam cach mat ngoai 25-60 cm (ti le so voi mat do cloud)
  formwork_elems: van khuon cua cau kien CHUA do: diem tren mat ben cau kien do -> de gay bao nham 'da xay'
  cams          : toa do may bay; chi giu diem NHIN THAY tu cac may bay nay (che khuat bang HPR, xem ben duoi)

GIOI HAN CAN NOI RO TRONG BAO CAO
  - HPR (Katz 2007) la xap xi, khong bang ray-casting that. Cau kien mong/thua co the bi danh gia sai.
  - Van chua mo phong: day cap cau, can cau, nguoi/xe, anh sang/bong do, loi dung anh cua ODM (lo, mat do khong deu).
  - BIM dung 2 lan (tao cloud va lam muc tieu) -> van la 'tu thi cua minh'. Ket qua thuc te se XAU hon.
"""

import numpy as np
from scipy.spatial import ConvexHull
from mesh_utils import sample_surface


def built_mask(types, floors, n_top):
    """Cau kien da xay: moi cau kien o tang < n_top, cong COT cua tang n_top (tang dang do)."""
    return (floors < n_top) | ((floors == n_top) & (types == "IfcColumn"))


def hpr_visible(P, cams, voxel=0.25):
    """
    Hidden Point Removal (Katz et al. 2007) cho tung may bay, hop ket qua.
    De nhanh: gom diem vao voxel, chay HPR tren tam voxel, diem nao thuoc voxel thay duoc thi giu.
    """
    key = np.floor(P / voxel).astype(np.int64)
    uk, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.ravel()
    C = (uk + 0.5) * voxel
    vis = np.zeros(len(C), dtype=bool)
    for cam in np.atleast_2d(cams):
        p = C - cam
        d = np.maximum(np.linalg.norm(p, axis=1), 1e-9)
        R = d.max() * 100.0
        q = p + 2.0 * (R - d)[:, None] * p / d[:, None]          # spherical flipping
        hull = ConvexHull(np.vstack([q, np.zeros((1, 3))]))
        v = hull.vertices
        vis[v[v < len(C)]] = True
    return vis[inv]


def make_cameras(V, standoff=35.0, n_ring=12, n_levels=4, top_extra=20.0):
    """Vi tri may bay gia dinh: vai vong quanh toa nha o cac do cao khac nhau + 1 diem tren cao."""
    lo, hi = V.min(0), V.max(0)
    c = (lo + hi) / 2
    rad = 0.5 * np.hypot(hi[0] - lo[0], hi[1] - lo[1]) + standoff
    cams = []
    for z in np.linspace(lo[2] + 5, hi[2] + top_extra, n_levels):
        for a in np.linspace(0, 2 * np.pi, n_ring, endpoint=False):
            cams.append([c[0] + rad * np.cos(a), c[1] + rad * np.sin(a), z])
    cams.append([c[0], c[1], hi[2] + 3 * top_extra])
    return np.array(cams)


def simulate_cloud(V, F, face_elem, built, rng, density=60.0, noise=0.03,
                   drop=0.30, outlier_frac=0.005, under_cut=-0.3,
                   deviation=0.0, scaffold=0.0, formwork_elems=None,
                   cams=None, vis_voxel=0.25):
    face_built = built[face_elem]
    P, nrm, tri = sample_surface(V, F[face_built], density, rng)
    eid = face_elem[face_built][tri]

    keep = (nrm[:, 2] > under_cut) & (rng.random(len(P)) > drop)   # bo mat duoi + roi ngau nhien
    P, nrm, eid = P[keep], nrm[keep], eid[keep]

    if cams is not None:                                            # che khuat (xap xi)
        vis = hpr_visible(P, cams, vis_voxel)
        P, nrm, eid = P[vis], nrm[vis], eid[vis]

    if deviation > 0:                                               # lech thi cong tung cau kien
        P = P + rng.normal(0, deviation, (len(built), 3))[eid]

    P = P + rng.normal(0, noise, P.shape)                           # nhieu do
    parts = [P]

    if scaffold > 0:                                                # tam che/gian giao cach mat ngoai
        side = np.where(np.abs(nrm[:, 2]) < 0.3)[0]
        sel = side[rng.random(len(side)) < scaffold]
        d = rng.uniform(0.25, 0.60, len(sel))
        parts.append(P[sel] + nrm[sel] * d[:, None])

    if formwork_elems is not None:                                  # van khuon cua cau kien chua do
        fm = formwork_elems & ~built
        Pf, nf, _ = sample_surface(V, F[fm[face_elem]], density * 0.5, rng)
        Pf = Pf[np.abs(nf[:, 2]) < 0.3]
        parts.append(Pf + rng.normal(0, noise, Pf.shape))

    P = np.vstack(parts)
    n_out = int(outlier_frac * len(P))                              # outlier trong hop bao
    lo, hi = P.min(0) - 3, P.max(0) + 3
    return np.vstack([P, rng.uniform(lo, hi, (n_out, 3))])


def rigid_transform(yaw_deg, translation, pivot):
    """Ma tran 4x4: quay quanh truc Z (yaw) tai diem 'pivot' roi tinh tien."""
    th = np.radians(yaw_deg)
    R = np.array([[np.cos(th), -np.sin(th), 0], [np.sin(th), np.cos(th), 0], [0, 0, 1]])
    T = np.eye(4)
    T[:3, :3] = R
    T[:3, 3] = np.asarray(pivot) - R @ np.asarray(pivot) + np.asarray(translation)
    return T


def apply(T, P):
    return (T[:3, :3] @ P.T).T + T[:3, 3]