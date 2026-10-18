"""
config.py - moi duong dan va nguong de o MOT cho (sua tai day, khong sua rai rac trong code).
Chay tren Windows/Linux deu duoc vi dung pathlib.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"        # plm_elements.json, plm_meshes.npz (do bim_loader.py xuat ra)
OUT_DIR = ROOT / "results"      # ket qua demo

IFC_PATH = ROOT / "PLM.ifc"

# Nguong so sanh (met)
TOL = 0.10                      # khoang cach toi da diem-cloud <-> be mat BIM de tinh la "khop"
T_BUILT = 0.30                  # coverage >= nguong nay -> "da xay"
T_NOT = 0.10                    # coverage <= nguong nay -> "chua xay"