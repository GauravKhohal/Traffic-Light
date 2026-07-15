"""Generate simple top-down vehicle sprites (car / jeep / truck / bus) as
transparent PNGs for SUMO's vType imgFile rendering, so the GUI shows vehicle
images instead of flat coloured polygons.

The SUMO view is top-down, so these are overhead illustrations with the front
of the vehicle at the TOP of the image. To use real photos instead, drop your
own overhead PNGs (front pointing up) in this folder with the same names.

    python simulation/assets/generate_vehicle_sprites.py
"""
import os

from PIL import Image, ImageDraw

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "vehicles")
SCALE = 46  # pixels per metre

WINDOW = (40, 55, 80, 210)  # glass colour
TIRE = (25, 25, 28, 255)


def rr(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


def base(length_m, width_m):
    w, h = round(width_m * SCALE), round(length_m * SCALE)
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img), w, h


def wheels(d, w, h, inset=3, tw=6, tl=None):
    tl = tl or round(h * 0.14)
    for wy in (round(h * 0.18), round(h * 0.70)):
        d.rounded_rectangle([inset, wy, inset + tw, wy + tl], radius=2, fill=TIRE)
        d.rounded_rectangle([w - inset - tw, wy, w - inset, wy + tl], radius=2, fill=TIRE)


def car(color, length=4.6, width=2.0):
    img, d, w, h = base(length, width)
    wheels(d, w, h)
    rr(d, [5, 4, w - 5, h - 4], radius=round(w * 0.32), fill=color)
    d.polygon([(11, round(h * 0.30)), (w - 11, round(h * 0.30)),
               (w - 15, round(h * 0.14)), (15, round(h * 0.14))], fill=WINDOW)  # windshield
    rr(d, [12, round(h * 0.34), w - 12, round(h * 0.64)], radius=6,
       fill=(color[0], color[1], color[2], 255))  # roof
    d.rectangle([13, round(h * 0.68), w - 13, round(h * 0.82)], fill=WINDOW)  # rear glass
    return img


def jeep(color, length=5.2, width=2.1):
    img, d, w, h = base(length, width)
    wheels(d, w, h, tw=7, tl=round(h * 0.15))
    rr(d, [4, 4, w - 4, h - 4], radius=round(w * 0.16), fill=color)  # boxy body
    d.rectangle([10, round(h * 0.16), w - 10, round(h * 0.30)], fill=WINDOW)
    rr(d, [10, round(h * 0.34), w - 10, round(h * 0.74)], radius=4,
       fill=(color[0], color[1], color[2], 255))
    d.rectangle([10, round(h * 0.78), w - 10, round(h * 0.90)], fill=WINDOW)
    return img


def truck(cab_color=(210, 60, 50, 255), length=9.0, width=2.5):
    img, d, w, h = base(length, width)
    wheels(d, w, h, tw=8, tl=round(h * 0.08))
    # trailer (rear ~65%)
    rr(d, [4, round(h * 0.34), w - 4, h - 4], radius=6, fill=(150, 152, 158, 255))
    d.line([(round(w / 2), round(h * 0.36)), (round(w / 2), h - 8)], fill=(120, 122, 128, 255), width=2)
    # cab (front ~30%)
    rr(d, [6, 4, w - 6, round(h * 0.30)], radius=8, fill=cab_color)
    d.rectangle([11, round(h * 0.10), w - 11, round(h * 0.20)], fill=WINDOW)  # windshield
    return img


def bus(color=(60, 120, 230, 255), length=10.0, width=2.6):
    img, d, w, h = base(length, width)
    wheels(d, w, h, tw=8, tl=round(h * 0.07))
    rr(d, [4, 4, w - 4, h - 4], radius=round(w * 0.22), fill=color)
    d.rectangle([10, round(h * 0.06), w - 10, round(h * 0.13)], fill=WINDOW)  # windshield
    for i in range(4):  # side windows
        y = round(h * (0.20 + i * 0.16))
        d.rectangle([8, y, 15, y + round(h * 0.10)], fill=WINDOW)
        d.rectangle([w - 15, y, w - 8, y + round(h * 0.10)], fill=WINDOW)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    sprites = {
        "car": car((245, 205, 40, 255)),
        "jeep": jeep((60, 190, 90, 255)),
        "truck": truck(),
        "bus": bus(),
    }
    for name, img in sprites.items():
        path = os.path.join(OUT, f"{name}.png")
        img.save(path)
        print(f"wrote {path} ({img.width}x{img.height})")


if __name__ == "__main__":
    main()
