#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成工具箱的应用图标（icon.png / icon.ico）。

需要 Pillow：pip install Pillow
用法：python assets/make_icon.py

要点：
  1. 图标在很小的尺寸（任务栏 16~40px）要还认得出，所以**按目标尺寸分别绘制**：
     尺寸越小图形放得越大、线条越粗、箱盖缝越宽、细节（锁扣）直接省掉。
  2. ico 容器手写，不用 Pillow 的统一缩放，
     这样 16/20/24/…/256 每一档都是专门画出来的，Windows 挑到哪档都是清晰的。
"""

import os
import struct

from PIL import Image, ImageDraw

OUT_DIR = os.path.dirname(os.path.abspath(__file__))

BLUE_TOP = (86, 141, 255)
BLUE_BOTTOM = (26, 62, 173)
WHITE = (255, 255, 255, 255)
LATCH = (26, 62, 173, 255)

# ---- 底板 ----
TILE_MARGIN = 0.055
TILE_RADIUS = 0.235

# ---- 图形（归一化坐标，按 2048 设计稿折算）----
HANDLE = (856 / 2048, 580 / 2048, 1192 / 2048, 900 / 2048)
HANDLE_R = 118 / 2048
LID = (516 / 2048, 818 / 2048, 1532 / 2048, 1012 / 2048)
LID_R = 88 / 2048
BODY = (570 / 2048, 1046 / 2048, 1478 / 2048, 1566 / 2048)
BODY_R = 104 / 2048
LATCH_BOX = (984 / 2048, 968 / 2048, 1064 / 2048, 1090 / 2048)
LATCH_R = 36 / 2048

CX, CY = 0.5, 1074 / 2048       # 缩放中心

# Windows 在这几个尺寸上取图；给全了就不用它自己拉伸
ICO_SIZES = [16, 20, 24, 28, 32, 36, 40, 48, 56, 64, 96, 128, 256]


def _tier(size):
    """按目标尺寸挑绘制参数：越小越粗、越大越精致。"""
    if size >= 64:
        zoom = 1.00
    elif size >= 32:
        zoom = 1.10
    else:
        zoom = 1.24
    gap = max(0.0166, 1.2 / size)       # 箱盖与箱体之间的缝，至少 1.2px
    stroke = max(0.036, 1.5 / size)     # 提手描边，至少 1.5px
    return zoom, gap, stroke


def build(size):
    """按目标尺寸绘制一张 size x size 的图标。"""
    S = min(4096, max(1152, size * 8))      # 8 倍超采样，缩下去自带抗锯齿

    # ---- 圆角渐变底板 ----
    grad = Image.new("RGB", (1, S))
    for y in range(S):
        t = y / (S - 1)
        grad.putpixel((0, y), tuple(
            round(BLUE_TOP[i] + (BLUE_BOTTOM[i] - BLUE_TOP[i]) * t)
            for i in range(3)))
    grad = grad.resize((S, S))

    mask = Image.new("L", (S, S), 0)
    m = TILE_MARGIN * S
    ImageDraw.Draw(mask).rounded_rectangle(
        [m, m, S - m, S - m], radius=TILE_RADIUS * S, fill=255)

    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    zoom, gap, stroke = _tier(size)

    def box(b, dy=0.0):
        xs = [(CX + (b[0] - CX) * zoom) * S, (CX + (b[2] - CX) * zoom) * S]
        ys = [(CY + (b[1] + dy - CY) * zoom) * S,
              (CY + (b[3] + dy - CY) * zoom) * S]
        return [xs[0], ys[0], xs[1], ys[1]]

    def rr(b, dy, rad, **kw):
        d.rounded_rectangle(box(b, dy), radius=rad * zoom * S, **kw)

    # 提手（下半截会被箱盖压住，自然融为一体）
    rr(HANDLE, 0.0, HANDLE_R, outline=WHITE,
       width=max(2, round(stroke * S)))
    # 箱盖往上、箱体往下各让半个缝，整体重心不跑偏
    rr(LID, -gap / 2.0, LID_R, fill=WHITE)
    rr(BODY, gap / 2.0, BODY_R, fill=WHITE)
    # 锁扣：小尺寸画了也是噪点，直接不画
    if size >= 40:
        rr(LATCH_BOX, 0.0, LATCH_R, fill=LATCH)

    if size != S:
        img = img.resize((size, size), Image.LANCZOS)
    return img


# ---------------- 手写 ICO 容器 ----------------
def _dib(img):
    """把 RGBA 图编成 ico 里用的 32 位 BMP（含 AND 掩码）。"""
    w, h = img.size
    px = img.convert("RGBA").load()

    xor = bytearray()
    for y in range(h - 1, -1, -1):          # BMP 是自下而上存的
        for x in range(w):
            r, g, b, a = px[x, y]
            xor += bytes((b, g, r, a))

    stride = ((w + 31) // 32) * 4           # AND 掩码每行 4 字节对齐
    and_mask = b"\x00" * (stride * h)       # 透明交给 alpha，掩码留全 0

    header = struct.pack("<IiiHHIIiiII", 40, w, h * 2, 1, 32, 0,
                         len(xor) + len(and_mask), 0, 0, 0, 0)
    return header + bytes(xor) + and_mask


def _png(img, tmp):
    img.save(tmp, format="PNG", optimize=True)
    with open(tmp, "rb") as f:
        return f.read()


def write_ico(images, path):
    """images: [(size, Image), ...]，自己拼 ico，避免 Pillow 统一缩放的糊边。"""
    tmp = path + ".tmp"
    blobs = []
    for size, img in images:
        # 256 用 PNG（体积极小），其余用 BMP（兼容性最好）
        data = _png(img, tmp) if size >= 128 else _dib(img)
        blobs.append((size, data))

    offset = 6 + 16 * len(blobs)
    dir_entries = bytearray()
    for size, data in blobs:
        dim = 0 if size >= 256 else size
        dir_entries += struct.pack("<BBBBHHII", dim, dim, 0, 0, 1, 32,
                                   len(data), offset)
        offset += len(data)

    with open(path, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(blobs)))
        f.write(dir_entries)
        for _, data in blobs:
            f.write(data)

    if os.path.exists(tmp):
        os.remove(tmp)


def main():
    png_path = os.path.join(OUT_DIR, "icon.png")
    ico_path = os.path.join(OUT_DIR, "icon.ico")

    build(256).save(png_path, optimize=True)          # 界面 / README 用
    images = [(s, build(s)) for s in ICO_SIZES]
    write_ico(images, ico_path)

    print("已生成：%s" % png_path)
    print("已生成：%s（尺寸 %s）" % (
        ico_path, ",".join(str(s) for s in ICO_SIZES)))
    print("文件大小：png %.1f KB / ico %.1f KB" % (
        os.path.getsize(png_path) / 1024.0,
        os.path.getsize(ico_path) / 1024.0))


if __name__ == "__main__":
    main()
