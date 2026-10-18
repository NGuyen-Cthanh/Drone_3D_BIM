"""
fusion.py
=========
Hop nhat NHIEU LAN QUET thanh MOT mo hinh thong nhat, theo trang thai tung cau kien BIM.

NGUYEN TAC
  Xay dung la qua trinh MOT CHIEU: cot da do thi khong tu mat. Vi vay moi cau kien nho mot trang thai qua cac lan quet:
      UNKNOWN  : chua tung quan sat du ro
      ABSENT   : da nhin ro (vis du lon) ma khong thay -> chua xay
      PRESENT  : da nhin ro va thay -> da xay (GIU MAI, ke ca khi lan sau bi tang tren che)
      CONFLICT : tung PRESENT nhung lan sau nhin ro lai khong thay -> can kiem tra thu cong
  Cau kien bi che (vis thap) o lan quet nay -> KHONG doi trang thai. Day la cho "khong bi lung".

  Moi cau kien con luu: lan quet dau tien thay (first_present) va lan quet cuoi cung con thay no vang (last_absent)
  => cua so thoi gian xay: (last_absent, first_present]. Doi chieu duoc voi lich.

HOP NHAT DAM MAY DIEM
  merge_epochs(): moi cau kien lay diem tu lan quet co bang chung tot nhat (best_epoch), nen phan da duoc
  nhin ro o lan truoc van con trong mo hinh tong du lan sau bi che.
  Chi giu diem trong 'tol' quanh be mat BIM (loai gian giao, outlier) va bo cac cau kien da ket luan ABSENT
  (diem gan do thuong la van khuon/gian giao).
"""
import numpy as np
from scipy.spatial import cKDTree
from mesh_utils import sample_surface

UNKNOWN, ABSENT, PRESENT, CONFLICT = 0, 1, 2, 3
NAMES = {UNKNOWN: "chua ro", ABSENT: "chua xay", PRESENT: "da xay", CONFLICT: "mau thuan"}


class FusionState:
    def __init__(self, n_elem):
        self.n = n_elem
        self.status = np.full(n_elem, UNKNOWN, dtype=np.int8)
        self.first_present = np.full(n_elem, -1, dtype=np.int32)
        self.last_absent = np.full(n_elem, -1, dtype=np.int32)
        self.best_epoch = np.full(n_elem, -1, dtype=np.int32)
        self.best_score = np.zeros(n_elem)
        self.n_epochs = 0

    def update(self, epoch, vis, r, v_min=0.25, r_present=0.5, r_absent=0.1, v_conflict=0.5):
        """
        epoch : chi so lan quet (0,1,2,... theo thoi gian)
        vis, r: tu visibility.evidence()
        v_min : phai nhin thay it nhat ti le nay be mat moi duoc ket luan
        v_conflict : de bao CONFLICT (da thay roi nay lai khong thay) phai nhin thay it nhat ti le nay (chat hon v_min,
                     de bot bao dong gia do lech dang ky)
        Tra ve so cau kien doi trang thai.
        """
        before = self.status.copy()
        seen = vis >= v_min
        pres = seen & (r >= r_present)
        absn = seen & (r <= r_absent)

        a = absn & (vis >= v_conflict) & ((self.status == PRESENT) | (self.status == CONFLICT))
        self.status[a] = CONFLICT
        b = absn & ~a & (self.status != PRESENT) & (self.status != CONFLICT)
        self.status[b] = ABSENT
        self.last_absent[b | a] = epoch

        self.status[pres] = PRESENT
        newly = pres & (self.first_present < 0)
        self.first_present[newly] = epoch

        score = vis * r                       # lan quet co bang chung tot nhat (ke ca cau kien chua ket luan duoc)
        better = (score > self.best_score) & (r > 0)
        self.best_score[better] = score[better]
        self.best_epoch[better] = epoch
        self.n_epochs = max(self.n_epochs, epoch + 1)
        return int((self.status != before).sum())

    def counts(self):
        return {NAMES[s]: int((self.status == s).sum()) for s in (UNKNOWN, ABSENT, PRESENT, CONFLICT)}


def merge_epochs(clouds, V, F, face_elem, state, tol=0.10, density=60.0, seed=0):
    """
    clouds : list point cloud (da dang ky vao he toa do BIM), theo thu tu lan quet.
    Tra ve (P_merged, element_id, epoch_id): moi diem kem cau kien va lan quet nguon.
    """
    rng = np.random.default_rng(seed)
    S, _, tri = sample_surface(V, F, density, rng)
    sid = face_elem[tri]
    tree = cKDTree(S)
    outP, outE, outK = [], [], []
    for k, c in enumerate(clouds):
        d, j = tree.query(c, k=1, distance_upper_bound=tol, workers=-1)
        ok = np.isfinite(d)
        e = np.full(len(c), -1, dtype=np.int64)
        e[ok] = sid[j[ok]]
        be = np.maximum(e, 0)
        keep = ok & (state.best_epoch[be] == k) & (state.status[be] != ABSENT)
        outP.append(c[keep]); outE.append(e[keep]); outK.append(np.full(keep.sum(), k))
    return np.vstack(outP), np.concatenate(outE), np.concatenate(outK)
