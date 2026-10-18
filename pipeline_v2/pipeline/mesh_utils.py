"""
mesh_utils.py  (v2)
===================
Cong cu dung chung cho registration / progress_evaluator / simulate_asbuilt:
  - load_bim()        : doc plm_elements.json + plm_meshes.npz do bim_loader xuat ra
  - slab_levels()     : tim cao do cac tang tu cao do mat san (theo HINH HOC)
  - assign_floors()   : gan moi cau kien vao 1 tang theo cao do Z that
  - fix_orientation() : dao chieu mesh bi nguoc (phap tuyen huong ra ngoai)
  - sample_surface()  : lay mau diem deu tren be mat mesh

THAY DOI SO VOI v1
  * load_bim() bo cac cau kien KHONG co hinh hoc (bbox=None) va danh lai 'index' lien tuc.
    v1 se bi TypeError o slab_levels()/assign_floors() (e["bbox"]["max"]) va o np.array([volume])
    neu chi 1 cau kien bi loi hinh hoc.
  * load_bim(fix_orient=True) tu sua chieu mesh. v1 co ham fix_orientation nhung run_demo KHONG goi,
    trong khi simulate_cloud bo mat 'huong xuong' dua vao phap tuyen -> mesh nguoc se bo nham mat tren.
  * slab_levels() canh bao khi cac cao do tang khong deu (de phat hien san chieu nghi, san ha cot...).

VI SAO GAN TANG THEO Z THAY VI DUNG NHAN TANG TRONG IFC
  Trong PLM.ifc co 21 dam nho bi gan nhan "TANG 1" nhung nam o cao do 36-48 m
  (loi gan level trong Revit). Dung nhan tang se tinh sai tien do tang 1 va tang 11-14.
"""

import json
import warnings
import numpy as np


def load_bim(json_path, npz_path, fix_orient=True):
    """
    Tra ve (E, V, F, face_elem).
      E         : list cau kien CO hinh hoc, E[i]["index"] == i
      face_elem : face_elem[k] = chi so (trong E) cua cau kien chua tam giac k
    """
    raw = json.load(open(json_path, encoding="utf-8"))["elements"]
    M = np.load(npz_path)
    V = M["verts"].astype(np.float64)
    F = M["faces"].astype(np.int64)

    # face_elem theo thu tu ghi (chi cac phan tu co hinh hoc)
    face_elem_raw = np.empty(len(F), dtype=np.int64)
    pos = 0
    for e in raw:
        if e["v_count"] > 0:
            face_elem_raw[pos:pos + e["f_count"]] = e["index"]
            pos += e["f_count"]
    assert pos == len(F), "so tam giac khong khop voi metadata (JSON va NPZ khong cung lan chay?)"

    ok = [e for e in raw if e.get("bbox") is not None and e["v_count"] > 0]
    n_bad = len(raw) - len(ok)
    if n_bad:
        warnings.warn(f"{n_bad} cau kien khong co hinh hoc -> bi bo qua khoi tinh toan")
    remap = {e["index"]: i for i, e in enumerate(ok)}
    E = []
    for i, e in enumerate(ok):
        e = dict(e)
        e["orig_index"] = e["index"]
        e["index"] = i
        E.append(e)
    face_elem = np.array([remap[x] for x in face_elem_raw], dtype=np.int32)

    if fix_orient:
        F, n_flip = fix_orientation(V, F, face_elem, len(E))
        if n_flip:
            print(f"[load_bim] da dao chieu mesh cua {n_flip}/{len(E)} cau kien (phap tuyen -> ra ngoai)")
    return E, V, F, face_elem


def fix_orientation(V, F, face_elem, n_elem):
    """
    Dam bao phap tuyen huong RA NGOAI: voi moi cau kien, neu the tich co dau am
    thi dao thu tu dinh. Can thiet vi mesh tu IfcFacetedBrep co the nguoc chieu,
    ma ta dung phap tuyen de loai bo mat huong xuong (mat duoi dam/san).
    Gioi han: chi sua duoc khi CA cau kien nguoc chieu; mesh tron lan xuoi/nguoc
    trong cung mot cau kien thi khong sua duoc o day.
    Tra ve (F_da_sua, so_cau_kien_bi_dao).
    """
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    sv = np.einsum("ij,ij->i", a, np.cross(b, c)) / 6.0
    vol = np.bincount(face_elem, weights=sv, minlength=n_elem)
    flip_elem = vol < 0
    F2 = F.copy()
    f = flip_elem[face_elem]
    F2[f] = F2[f][:, [0, 2, 1]]
    return F2, int(flip_elem.sum())


def slab_levels(E, gap=1.0, expected_storeys=None):
    """
    Cao do mat san (m): gom cum cao do z_max cua cac san, khoang cach cum > gap.
    Neu biet so tang that (vd 18 cao do trong IFC) thi truyen vao expected_storeys de duoc canh bao
    khi so cum khong khop (thuong do san chieu nghi / san ha cot bi tinh la 1 'tang').
    """
    z = np.sort([e["bbox"]["max"][2] for e in E if e["ifc_type"] == "IfcSlab"])
    groups = np.split(z, np.where(np.diff(z) > gap)[0] + 1)
    levels = np.array([g.mean() for g in groups])
    if expected_storeys is not None and len(levels) != expected_storeys:
        warnings.warn(f"slab_levels: tim thay {len(levels)} cao do, ky vong {expected_storeys}. "
                      f"Khoang cach giua cac cao do: {np.diff(levels).round(2)}")
    return levels


def assign_floors(E, levels, tol=0.5):
    """
    Chi so tang cua tung cau kien = tang dau tien co (cao do san + tol) >= z_max cua cau kien.
    Cot cua tang i co dinh o ~cao do san i; dam/san cung nam trong 'lift' do.
    """
    zmax = np.array([e["bbox"]["max"][2] for e in E])
    idx = np.searchsorted(levels + tol, zmax, side="left")
    return np.clip(idx, 0, len(levels) - 1)


def sample_surface(V, F, density, rng):
    """
    Lay mau diem deu tren be mat luoi tam giac, theo dien tich (density = diem/m2).
    Tra ve (P, normals, tri_idx): toa do, phap tuyen, chi so tam giac nguon.
    """
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    cr = np.cross(b - a, c - a)
    area2 = np.linalg.norm(cr, axis=1)
    area = 0.5 * area2
    n = cr / np.maximum(area2, 1e-12)[:, None]

    k = area * density
    cnt = np.floor(k).astype(np.int64) + (rng.random(len(F)) < (k - np.floor(k)))
    tri = np.repeat(np.arange(len(F)), cnt)

    r1 = np.sqrt(rng.random(len(tri)))
    r2 = rng.random(len(tri))
    P = ((1 - r1)[:, None] * a[tri] + (r1 * (1 - r2))[:, None] * b[tri]
         + (r1 * r2)[:, None] * c[tri])
    return P, n[tri], tri