"""
bim_loader.py  (v2.2)
===================
Doc file IFC va trich xuat cac cau kien ket cau VINH VIEN (Beam/Column/Slab)
voi hinh hoc 3D theo don vi MET, o he toa do cua mo hinh.

SUA LOI SO VOI v1
-----------------
v1 chi tinh duoc hinh hoc cho 145/1413 dam (47% tong so cau kien bi null).
Nguyen nhan: 1268 dam co 2 representation la 'Axis' (duong truc 2D, khong co
the tich) va 'Body' (thanh dam 3D dang IfcFacetedBrep). Khi goi create_shape()
tren cau kien, thu vien chon nham representation 'Axis' roi bao loi.

Cach sua: lay thang representation 'Body' roi tu ap ma tran placement cua cau
kien. Hai luu y da kiem chung bang so lieu:
  1. Khi truyen representation (thay vi cau kien), thu vien KHONG ap
     ObjectPlacement  -> phai tu nhan ma tran placement.
  2. Ma tran placement o don vi cua file (mm) con hinh hoc tra ve don vi met
     -> phai nhan phan tinh tien voi unit_scale (0.001).
Da doi chieu voi cach goc tren 437 cau kien (145 dam, 995 cot... co the tinh
bang ca 2 cach): sai lech lon nhat = 0.0 m.

DAU RA
------
  plm_elements.json : metadata + bbox + trong tam (met) tung cau kien
  plm_meshes.npz    : mesh tat ca cau kien (verts, faces, offset theo cau kien)
"""

import json
import sys
import numpy as np
import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.element as element_util
import ifcopenshell.util.placement as placement
import ifcopenshell.util.unit as unit_util

# Mac dinh BO QUA IfcBuildingElementProxy (TS_FormWork = van khuon, cau truc tam).
INCLUDED_TYPES = ["IfcBeam", "IfcColumn", "IfcSlab"]


def _verts_faces(shape):
    g = shape.geometry if hasattr(shape, "geometry") else shape
    v = np.array(g.verts, dtype=np.float64).reshape(-1, 3)
    f = np.array(g.faces, dtype=np.int64).reshape(-1, 3)
    return v, f


def get_mesh(element, settings, unit_scale):
    """
    Tra ve (verts, faces, phuong_phap) theo met, o he toa do mo hinh.
    Thu cach 1 (nhanh, chuan); neu that bai, lay representation 'Body' va tu ap placement.
    """
    try:
        v, f = _verts_faces(ifcopenshell.geom.create_shape(settings, element))
        return v, f, "product"
    except Exception:
        pass

    if element.Representation is None:
        return None, None, "no_representation"

    body = [r for r in element.Representation.Representations
            if r.RepresentationIdentifier == "Body"]
    if not body:
        return None, None, "no_body"

    try:
        v, f = _verts_faces(ifcopenshell.geom.create_shape(settings, body[0]))
    except Exception:
        return None, None, "body_failed"

    M = placement.get_local_placement(element.ObjectPlacement).copy()
    M[:3, 3] *= unit_scale                      # mm -> m cho phan tinh tien
    v = (M[:3, :3] @ v.T).T + M[:3, 3]
    return v, f, "body+placement"


def get_storey_name(element):
    c = element_util.get_container(element)
    return c.Name if c is not None else None


def get_section_ref(element):
    """Ten tiet dien (vd '300x600'). Luu y: Pset_QuantityTakeOff trong file nay
    CHI chua 'Reference', KHONG co the tich/dien tich -> the tich tu tinh tu mesh."""
    try:
        q = element_util.get_psets(element).get("Pset_QuantityTakeOff") or {}
        return q.get("Reference")
    except Exception:
        return None


def mesh_volume(v, f):
    """The tich (m3) cua luoi dong bang tong the tich co dau cac tu dien (divergence theorem)."""
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0))


def extract_elements(ifc_path, included_types=INCLUDED_TYPES):
    model = ifcopenshell.open(ifc_path)
    unit_scale = unit_util.calculate_unit_scale(model)

    settings = ifcopenshell.geom.settings()
    settings.set("use-world-coords", True)

    records, all_verts, all_faces = [], [], []
    v_offset = 0
    method_count, failed = {}, []

    for ifc_type in included_types:
        for elem in model.by_type(ifc_type):
            v, f, method = get_mesh(elem, settings, unit_scale)
            method_count[method] = method_count.get(method, 0) + 1

            rec = {
                "index": len(records),
                "global_id": elem.GlobalId,
                "ifc_type": ifc_type,
                "name": elem.Name,
                "storey": get_storey_name(elem),
                "section": get_section_ref(elem),
                "mesh_method": method,
            }
            if v is None or len(v) == 0:
                rec.update(bbox=None, centroid=None, volume_m3=None, v_start=None, v_count=0, f_count=0)
                failed.append(rec["global_id"])
            else:
                rec.update(
                    bbox={"min": v.min(0).round(4).tolist(), "max": v.max(0).round(4).tolist()},
                    centroid=v.mean(0).round(4).tolist(), volume_m3=round(mesh_volume(v, f), 5),
                    v_start=v_offset, v_count=len(v), f_count=len(f),
                )
                all_verts.append(v)
                all_faces.append(f + v_offset)
                v_offset += len(v)
            records.append(rec)

    meshes = {
        "verts": np.vstack(all_verts).astype(np.float32),
        "faces": np.vstack(all_faces).astype(np.int32),
    }
    return records, meshes, method_count, failed, unit_scale


def storey_table(records):
    """Do cao Z (min/max, met) va so luong tung loai cau kien theo tang."""
    table = {}
    for r in records:
        if r["bbox"] is None:
            continue
        name = r["storey"] or "(khong xac dinh)"
        t = table.setdefault(name, {"z_min": 1e9, "z_max": -1e9, "counts": {}})
        t["z_min"] = min(t["z_min"], r["bbox"]["min"][2])
        t["z_max"] = max(t["z_max"], r["bbox"]["max"][2])
        t["counts"][r["ifc_type"]] = t["counts"].get(r["ifc_type"], 0) + 1
    return table


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    import config

    ap = argparse.ArgumentParser()
    ap.add_argument("ifc", nargs="?", default=str(config.IFC_PATH))
    ap.add_argument("--out", default=str(config.DATA_DIR))
    a = ap.parse_args()
    ifc_path, out_dir = a.ifc, Path(a.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Dang doc: {ifc_path}")
    records, meshes, method_count, failed, unit_scale = extract_elements(ifc_path)

    ok = sum(1 for r in records if r["bbox"] is not None)
    print(f"Don vi file: x{unit_scale} -> met")
    print(f"Tong cau kien: {len(records)} | co hinh hoc: {ok} | loi: {len(failed)}")
    print(f"Phuong phap lay hinh hoc: {method_count}")
    if failed:
        print(f"  CANH BAO: {len(failed)} cau kien khong co hinh hoc, vi du GlobalId: {failed[:5]}")

    allv = meshes["verts"]
    print(f"Mesh gop: {len(allv):,} dinh, {len(meshes['faces']):,} tam giac")
    print(f"Kich thuoc toa nha (bbox, m): {allv.min(0).round(1)} -> {allv.max(0).round(1)}")

    print("\n--- Theo tang (sap theo cao do Z) ---")
    tbl = storey_table(records)
    for name, t in sorted(tbl.items(), key=lambda kv: kv[1]["z_min"]):
        c = t["counts"]
        print(f"  {name:28s} Z {t['z_min']:7.2f} -> {t['z_max']:7.2f} m | "
              f"dam {c.get('IfcBeam',0):4d}  cot {c.get('IfcColumn',0):4d}  san {c.get('IfcSlab',0):3d}")

    with open(out_dir / "plm_elements.json", "w", encoding="utf-8") as f:
        json.dump({"unit": "m", "storeys": tbl, "elements": records}, f, ensure_ascii=False)
    np.savez_compressed(out_dir / "plm_meshes.npz", **meshes)
    print(f"\nDa luu: {out_dir / 'plm_elements.json'} , plm_meshes.npz")