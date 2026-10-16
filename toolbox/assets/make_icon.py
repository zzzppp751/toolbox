#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成工具箱的应用图标（icon.png / icon.ico）。

需要 Pillow：pip install Pillow
用法：python assets/make_icon.py

思路：在 2048x2048 画布上用几何图形绘制，再降采样到各尺寸，
以获得平滑的边缘（相当于超采样抗锯齿）。
"""

import os

from PIL import Image, ImageDraw

S = 2048                      # 工作画布尺寸（越大越平滑）
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

BLUE_TOP = (79, 140, 255)     # 渐变起始
BLUE_BOTTOM = (25, 60, 170)   # 渐变结束
WHITE = (255, 255, 255, 255)


def rounded_gradient(size, top, bottom, radius, margin):
    """圆角 + 垂直渐变的底板。"""
    grad = Image.new("RGB", (1, size))
    for y in range(size):
        t = y / (size - 1)
        grad.putpixel((0, y), tuple(
            int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    grad = grad.resize((size, size))

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius, fill=255)

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    img.paste(grad, (0, 0), mask)
    return img


def build():
    img = rounded_gradient(S, BLUE_TOP, BLUE_BOTTOM,
                           radius=int(S * 0.235), margin=int(S * 0.055))
    d = ImageDraw.Draw(img)

    # ---- 白色工具箱图形 ----
    # 提手（描边），下半部分会被箱盖盖住，自然融合
    d.rounded_rectangle([856, 580, 1192, 900], radius=118,
                        outline=WHITE, width=74)
    # 箱盖
    d.rounded_rectangle([516, 818, 1532, 1012], radius=88, fill=WHITE)
    # 箱体（与箱盖之间留出缝隙，露出蓝色底，形成开合线）
    d.rounded_rectangle([570, 1046, 1478, 1566], radius=104, fill=WHITE)
    # 中央锁扣（跨在开合线上，用底色画出，形成细节）
    d.rounded_rectangle([984, 968, 1064, 1090], radius=36,
                        fill=(25, 60, 170, 255))

    return img


def main():
    icon = build()

    png_path = os.path.join(OUT_DIR, "icon.png")
    ico_path = os.path.join(OUT_DIR, "icon.ico")

    icon.resize((256, 256), Image.LANCZOS).save(png_path)
    # 多尺寸 ico，小尺寸也保持清晰
    icon.save(ico_path, format="ICO",
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48),
                     (64, 64), (128, 128), (256, 256)])

    print("已生成：%s" % png_path)
    print("已生成：%s" % ico_path)


if __name__ == "__main__":
    main()
