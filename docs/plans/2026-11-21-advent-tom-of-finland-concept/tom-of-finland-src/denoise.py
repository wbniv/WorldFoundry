"""Denoise a plain Cycles render.

  WF_CONTAINER_IMAGE=blender scripts/in-linux-container.sh python3 -I denoise.py in.png out.png

Ubuntu's Blender is built without OpenImageDenoise, so Cycles cannot denoise itself.
The `wf-blender` container therefore carries Intel's standalone `oidnDenoise`; this
script converts the PNG to PPM, runs it (LDR mode, colour only: no albedo or normal
passes), and converts back. Without `oidnDenoise` on PATH it falls back to an
edge-preserving 7x7 bilateral filter (spatial sigma 2 px, range sigma 0.07), which
smooths grain less well but keeps numerals, frames and silhouettes.
"""
import os
import shutil
import subprocess
import sys
import tempfile

import numpy as np
from PIL import Image


def bilateral(img):
    H, W, _ = img.shape
    R, SS, SR = 3, 2.0, 0.07
    pad = np.pad(img, ((R, R), (R, R), (0, 0)), mode="edge")
    acc = np.zeros_like(img)
    wsum = np.zeros((H, W, 1), dtype=np.float32)
    for dy in range(-R, R + 1):
        for dx in range(-R, R + 1):
            nb = pad[R + dy:R + dy + H, R + dx:R + dx + W]
            w = np.exp(-(dx * dx + dy * dy) / (2 * SS * SS)) * np.exp(-((nb - img) ** 2).sum(axis=2, keepdims=True) / (2 * SR * SR))
            acc += nb * w
            wsum += w
    return acc / wsum


def write_pfm(path, arr):
    H, W, _ = arr.shape
    with open(path, "wb") as f:
        f.write(f"PF\n{W} {H}\n-1.0\n".encode())
        f.write(np.ascontiguousarray(arr[::-1], dtype="<f4").tobytes())     # rows run bottom to top


def read_pfm(path):
    with open(path, "rb") as f:
        assert f.readline().strip() == b"PF"
        W, H = map(int, f.readline().split())
        scale = float(f.readline())
        data = np.frombuffer(f.read(), dtype="<f4" if scale < 0 else ">f4")
    return data.reshape(H, W, 3)[::-1].astype(np.float32)


def main(src, dst):
    exe = shutil.which("oidnDenoise")
    if exe:
        img = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255.0
        with tempfile.TemporaryDirectory() as td:
            a, b = os.path.join(td, "in.pfm"), os.path.join(td, "out.pfm")
            write_pfm(a, img)
            subprocess.run([exe, "--ldr", a, "--srgb", "-o", b], check=True)
            out = read_pfm(b)
        Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst, optimize=True)
        print("wrote", dst, "(oidnDenoise)")
        return
    img = np.asarray(Image.open(src).convert("RGB"), dtype=np.float32) / 255.0
    out = bilateral(img)
    Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)).save(dst, optimize=True)
    print("wrote", dst, "(bilateral fallback)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
