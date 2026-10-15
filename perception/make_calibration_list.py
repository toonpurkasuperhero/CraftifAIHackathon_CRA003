#!/usr/bin/env python3
"""Pick a class-balanced INT8 calibration set from the BRA training images (for PipeGen's Compiler stage).

    python perception/make_calibration_list.py --n 400 --copy /home/$USER/wildguard_calib
Writes perception/calibration_list.txt (absolute paths). --copy also copies the images into a folder,
because PipeGen expects files under /home.
"""
import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IMG = ROOT / "training" / "archive" / "Dataset" / "images" / "train"
LBL = ROOT / "training" / "archive" / "Dataset" / "labels" / "train"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=400)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--copy", help="copy the selected images into this folder")
    a = ap.parse_args()
    by_cls = defaultdict(list)
    for img in sorted(IMG.glob("*.jpg")):
        lbl = LBL / (img.stem + ".txt")
        cls = lbl.read_text().split()[0] if lbl.exists() and lbl.read_text().strip() else "bg"
        by_cls[cls].append(img)
    rnd = random.Random(a.seed)
    per = max(1, a.n // max(1, len(by_cls)))
    pick = []
    for cls, imgs in sorted(by_cls.items()):
        rnd.shuffle(imgs)
        pick += imgs[:per]
        print(f"class {cls}: {min(per, len(imgs))} of {len(imgs)}")
    out = Path(__file__).resolve().parent / "calibration_list.txt"
    out.write_text("\n".join(str(p) for p in pick) + "\n")
    print(f"{len(pick)} images -> {out}")
    if a.copy:
        dst = Path(a.copy)
        dst.mkdir(parents=True, exist_ok=True)
        for p in pick:
            shutil.copy2(p, dst / p.name)
        print(f"copied to {dst}")


if __name__ == "__main__":
    main()
