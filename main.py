#!/usr/bin/env python3
import os
import math
import struct
import zlib
import time

WIDTH = 1024
HEIGHT = 1024

# Palette definitions (RGB)
BG_TEAL = (39, 179, 166)
GLOW = (143, 232, 220)
FUR = (222, 116, 52)
FUR_SHADE = (200, 95, 39)
FUR_DARK = (138, 68, 22)
CREAM = (255, 241, 220)
CREAM_SHADE = (245, 223, 192)
EYE_IRIS = (138, 75, 18)
PUPIL = (36, 17, 9)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
NOSE = (110, 53, 36)
MOUTH = (122, 59, 20)
TONGUE = (255, 159, 176)
TONGUE_SHADE = (230, 130, 150)
BLUSH = (255, 158, 158)
BAMBOO_BODY = (95, 191, 107)
BAMBOO_SHADE = (62, 155, 79)
BAMBOO_LEAF = (121, 217, 127)
BAMBOO_FACE = (30, 70, 32)
SHADOW_COLOR = (20, 90, 80)

def clamp(v, low=0.0, high=1.0):
    return max(low, min(high, v))

def blend_pixel(bg, fg, alpha):
    if alpha <= 0:
        return bg
    if alpha >= 1:
        return fg
    inv = 1.0 - alpha
    return (
        int(fg[0] * alpha + bg[0] * inv + 0.5),
        int(fg[1] * alpha + bg[1] * inv + 0.5),
        int(fg[2] * alpha + bg[2] * inv + 0.5)
    )

def circle_sdf(x, y, cx, cy, r):
    return math.sqrt((x - cx)**2 + (y - cy)**2) - r

def ellipse_sdf(x, y, cx, cy, rx, ry):
    nx = (x - cx) / rx
    ny = (y - cy) / ry
    d_unit = math.sqrt(nx*nx + ny*ny) - 1.0
    return d_unit * min(rx, ry)

def capsule_sdf(x, y, x1, y1, x2, y2, r):
    ab_x = x2 - x1
    ab_y = y2 - y1
    ap_x = x - x1
    ap_y = y - y1
    ab_len_sq = ab_x*ab_x + ab_y*ab_y
    if ab_len_sq == 0:
        return math.sqrt(ap_x*ap_x + ap_y*ap_y) - r
    t = (ap_x * ab_x + ap_y * ab_y) / ab_len_sq
    t = max(0.0, min(1.0, t))
    nx = x1 + t * ab_x
    ny = y1 + t * ab_y
    dx = x - nx
    dy = y - ny
    return math.sqrt(dx*dx + dy*dy) - r

def rotated_ellipse_sdf(x, y, cx, cy, rx, ry, angle_deg):
    rad = math.radians(-angle_deg)
    cos_a = math.cos(rad)
    sin_a = math.sin(rad)
    dx = x - cx
    dy = y - cy
    rx_coord = dx * cos_a - dy * sin_a
    ry_coord = dx * sin_a + dy * cos_a
    return ellipse_sdf(0, 0, -rx_coord, -ry_coord, rx, ry)

def star4_sdf(x, y, cx, cy, r):
    d_vert = capsule_sdf(x, y, cx, cy - r, cx, cy + r, r * 0.18)
    d_horiz = capsule_sdf(x, y, cx - r, cy, cx + r, cy, r * 0.18)
    return min(d_vert, d_horiz)

def arc_bottom_sdf(x, y, cx, cy, r, thickness):
    d_circ = abs(math.sqrt((x - cx)**2 + (y - cy)**2) - r) - thickness / 2.0
    if y < cy - 1:
        return 1000.0
    return d_circ

class Canvas:
    def __init__(self, width, height, bg_color):
        self.width = width
        self.height = height
        self.pixels = [bg_color] * (width * height)

    def draw_shape(self, sdf_func, color, alpha=1.0, feather=1.5, bbox=None, clip_func=None):
        if bbox is None:
            xmin, ymin, xmax, ymax = 0, 0, self.width, self.height
        else:
            xmin, ymin, xmax, ymax = bbox
            xmin = max(0, int(xmin - feather - 2))
            ymin = max(0, int(ymin - feather - 2))
            xmax = min(self.width, int(xmax + feather + 2))
            ymax = min(self.height, int(ymax + feather + 2))

        pixels = self.pixels
        w = self.width

        for y in range(ymin, ymax):
            row_idx = y * w
            for x in range(xmin, xmax):
                if clip_func is not None and clip_func(x, y) > 0:
                    continue
                d = sdf_func(x, y)
                if d <= feather:
                    if d <= -feather:
                        cov = 1.0
                    else:
                        cov = clamp(0.5 - d / (2.0 * feather))
                    tot_alpha = alpha * cov
                    if tot_alpha > 0.001:
                        idx = row_idx + x
                        pixels[idx] = blend_pixel(pixels[idx], color, tot_alpha)

def render():
    t0 = time.time()
    canvas = Canvas(WIDTH, HEIGHT, BG_TEAL)

    # 2. Glow
    canvas.draw_shape(
        lambda x, y: circle_sdf(x, y, 512, 470, 430),
        GLOW, alpha=0.30, feather=160,
        bbox=(512-430-160, 470-430-160, 512+430+160, 470+430+160)
    )

    # 3. Ground shadow
    canvas.draw_shape(
        lambda x, y: ellipse_sdf(x, y, 512, 908, 295, 40),
        SHADOW_COLOR, alpha=0.25, feather=22,
        bbox=(512-295-22, 908-40-22, 512+295+22, 908+40+22)
    )

    # 4. Tail (behind body, viewer right)
    tail_circles = [
        (688, 856, 88, FUR),
        (750, 836, 84, FUR_DARK),
        (806, 806, 78, FUR),
        (846, 750, 72, FUR_DARK),
        (872, 690, 66, CREAM)
    ]
    for cx, cy, r, col in tail_circles:
        canvas.draw_shape(
            lambda x, y, cx=cx, cy=cy, r=r: circle_sdf(x, y, cx, cy, r),
            col, alpha=1.0, feather=1.5,
            bbox=(cx-r, cy-r, cx+r, cy+r)
        )

    # 5. Body & Belly
    body_bbox = (512-238, 762-188, 512+238, 762+188)
    canvas.draw_shape(
        lambda x, y: ellipse_sdf(x, y, 512, 762, 238, 188),
        FUR, alpha=1.0, feather=2.0, bbox=body_bbox
    )
    body_sdf = lambda x, y: ellipse_sdf(x, y, 512, 762, 238, 188)
    canvas.draw_shape(
        lambda x, y: ellipse_sdf(x, y, 512, 806, 152, 118),
        CREAM, alpha=1.0, feather=2.0,
        bbox=(512-152, 806-118, 512+152, 806+118),
        clip_func=body_sdf
    )

    # 6. Feet & toe beans
    for fx in [322, 702]:
        canvas.draw_shape(
            lambda x, y, cx=fx: ellipse_sdf(x, y, cx, 908, 82, 46),
            FUR_DARK, alpha=1.0, feather=2.0,
            bbox=(fx-82, 908-46, fx+82, 908+46)
        )
        canvas.draw_shape(
            lambda x, y, cx=fx: ellipse_sdf(x, y, cx, 896, 26, 16),
            CREAM, alpha=1.0, feather=1.5,
            bbox=(fx-26, 896-16, fx+26, 896+16)
        )
        for dx in [-18, 0, 18]:
            canvas.draw_shape(
                lambda x, y, cx=fx+dx: circle_sdf(x, y, cx, 876, 10),
                CREAM, alpha=1.0, feather=1.5,
                bbox=(fx+dx-10, 876-10, fx+dx+10, 876+10)
            )

    # 7. Ears (behind head)
    for ex in [322, 702]:
        canvas.draw_shape(
            lambda x, y, cx=ex: circle_sdf(x, y, cx, 252, 82),
            CREAM, alpha=1.0, feather=2.0, bbox=(ex-82, 252-82, ex+82, 252+82)
        )
        canvas.draw_shape(
            lambda x, y, cx=ex: circle_sdf(x, y, cx, 262, 63),
            FUR, alpha=1.0, feather=2.0, bbox=(ex-63, 262-63, ex+63, 262+63)
        )
        canvas.draw_shape(
            lambda x, y, cx=ex: circle_sdf(x, y, cx, 196, 26),
            FUR_DARK, alpha=1.0, feather=1.5, bbox=(ex-26, 196-26, ex+26, 196+26)
        )

    # 8. Head & Shading
    head_bbox = (512-238, 428-238, 512+238, 428+238)
    canvas.draw_shape(
        lambda x, y: circle_sdf(x, y, 512, 428, 238),
        FUR, alpha=1.0, feather=2.0, bbox=head_bbox
    )
    head_sdf = lambda x, y: circle_sdf(x, y, 512, 428, 238)
    canvas.draw_shape(
        lambda x, y: ellipse_sdf(x, y, 600, 560, 230, 150),
        FUR_SHADE, alpha=0.25, feather=60,
        bbox=(600-230, 560-150, 600+230, 560+150),
        clip_func=head_sdf
    )

    # 9. Face mask (cream)
    mask_bbox = (512-168, 392-96, 512+168, 486+118)
    mask_shape_sdf = lambda x, y: min(
        ellipse_sdf(x, y, 512, 486, 168, 118),
        circle_sdf(x, y, 512, 392, 96)
    )
    canvas.draw_shape(
        mask_shape_sdf, CREAM, alpha=1.0, feather=2.0,
        bbox=mask_bbox, clip_func=head_sdf
    )

    # 10. Brow spots
    for bx in [452, 572]:
        canvas.draw_shape(
            lambda x, y, cx=bx: ellipse_sdf(x, y, cx, 326, 27, 16),
            CREAM_SHADE, alpha=0.9, feather=1.5,
            bbox=(bx-27, 326-16, bx+27, 326+16),
            clip_func=head_sdf
        )

    # 11. Tear marks
    canvas.draw_shape(
        lambda x, y: rotated_ellipse_sdf(x, y, 378, 508, 15, 54, 18),
        FUR_DARK, alpha=0.85, feather=3.0,
        bbox=(378-40, 508-60, 378+40, 508+60),
        clip_func=head_sdf
    )
    canvas.draw_shape(
        lambda x, y: rotated_ellipse_sdf(x, y, 646, 508, 15, 54, -18),
        FUR_DARK, alpha=0.85, feather=3.0,
        bbox=(646-40, 508-60, 646+40, 508+60),
        clip_func=head_sdf
    )

    # 12. Eyes
    for ex, ey in [(422, 438), (602, 438)]:
        canvas.draw_shape(
            lambda x, y, cx=ex, cy=ey: ellipse_sdf(x, y, cx, cy, 37, 47),
            EYE_IRIS, alpha=1.0, feather=1.5,
            bbox=(ex-37, ey-47, ex+37, ey+47)
        )
        canvas.draw_shape(
            lambda x, y, cx=ex, cy=ey: ellipse_sdf(x, y, cx, cy, 31, 41),
            PUPIL, alpha=1.0, feather=1.5,
            bbox=(ex-31, ey-41, ex+31, ey+41)
        )
        canvas.draw_shape(
            lambda x, y, cx=ex-11, cy=ey-16: circle_sdf(x, y, cx, cy, 13),
            WHITE, alpha=1.0, feather=1.0,
            bbox=(ex-11-13, ey-16-13, ex-11+13, ey-16+13)
        )
        canvas.draw_shape(
            lambda x, y, cx=ex+11, cy=ey+18: circle_sdf(x, y, cx, cy, 6),
            WHITE, alpha=0.9, feather=1.0,
            bbox=(ex+11-6, ey+18-6, ex+11+6, ey+18+6)
        )

    # 13. Nose
    canvas.draw_shape(
        lambda x, y: ellipse_sdf(x, y, 512, 522, 23, 15),
        NOSE, alpha=1.0, feather=1.5,
        bbox=(512-23, 522-15, 512+23, 522+15)
    )
    canvas.draw_shape(
        lambda x, y: circle_sdf(x, y, 504, 516, 4),
        WHITE, alpha=0.8, feather=1.0,
        bbox=(500, 512, 508, 520)
    )

    # 15. Blep (tongue)
    canvas.draw_shape(
        lambda x, y: ellipse_sdf(x, y, 512, 560, 18, 14),
        TONGUE, alpha=1.0, feather=1.5,
        bbox=(512-18, 560-14, 512+18, 560+14)
    )
    canvas.draw_shape(
        lambda x, y: capsule_sdf(x, y, 512, 550, 512, 568, 3),
        TONGUE_SHADE, alpha=0.7, feather=1.0,
        bbox=(508, 548, 516, 570)
    )

    # 14. Mouth arcs (corrected to bottom half arcs)
    for mx in [495, 529]:
        canvas.draw_shape(
            lambda x, y, cx=mx: arc_bottom_sdf(x, y, cx, 528, 16, 4.0),
            MOUTH, alpha=1.0, feather=1.0,
            bbox=(mx-16-2, 528, mx+16+2, 528+16+2)
        )

    # 16. Blush (stronger pink, smaller feather)
    for bx in [342, 682]:
        canvas.draw_shape(
            lambda x, y, cx=bx: ellipse_sdf(x, y, cx, 542, 42, 20),
            BLUSH, alpha=0.6, feather=8.0,
            bbox=(bx-42-8, 542-20-8, bx+42+8, 542+20+8)
        )

    # 18. Bamboo plush (in front of belly, hugged)
    shoot_sdf = lambda x, y: capsule_sdf(x, y, 512, 700, 512, 872, 74)
    canvas.draw_shape(
        shoot_sdf, BAMBOO_BODY, alpha=1.0, feather=2.0,
        bbox=(512-74-2, 700-2, 512+74+2, 872+2)
    )
    canvas.draw_shape(
        lambda x, y: capsule_sdf(x, y, 512+22, 700, 512+22, 872, 74),
        BAMBOO_SHADE, alpha=0.35, feather=10.0,
        bbox=(512-74, 700, 512+96, 872),
        clip_func=shoot_sdf
    )
    for sy in [762, 822]:
        canvas.draw_shape(
            lambda x, y, cy=sy: abs(capsule_sdf(x, y, 512-70, cy, 512+70, cy, 10)) - 3.0,
            BAMBOO_SHADE, alpha=0.6, feather=1.2,
            bbox=(512-75, cy-15, 512+75, cy+15),
            clip_func=shoot_sdf
        )
    for lx, ly, ang in [(446, 682, -25), (512, 660, 0), (578, 682, 25)]:
        canvas.draw_shape(
            lambda x, y, cx=lx, cy=ly, a=ang: rotated_ellipse_sdf(x, y, cx, cy, 36, 16, a),
            BAMBOO_LEAF, alpha=1.0, feather=1.5,
            bbox=(lx-45, ly-25, lx+45, ly+25)
        )
    # Plush face (proper bottom half smile arc)
    for px in [486, 538]:
        canvas.draw_shape(
            lambda x, y, cx=px: circle_sdf(x, y, cx, 772, 7.5),
            BAMBOO_FACE, alpha=1.0, feather=1.0,
            bbox=(px-8, 772-8, px+8, 772+8)
        )
    canvas.draw_shape(
        lambda x, y: arc_bottom_sdf(x, y, 512, 784, 13, 3.5),
        BAMBOO_FACE, alpha=1.0, feather=1.0,
        bbox=(512-15, 784, 512+15, 784+15)
    )
    for bx in [462, 562]:
        canvas.draw_shape(
            lambda x, y, cx=bx: circle_sdf(x, y, cx, 790, 9),
            BLUSH, alpha=0.6, feather=3.0,
            bbox=(bx-12, 790-12, bx+12, 790+12)
        )

    # 19. Arms hugging
    for ax1, ay1, ax2, ay2 in [
        (318, 742, 448, 796),
        (706, 742, 576, 796)
    ]:
        canvas.draw_shape(
            lambda x, y, x1=ax1, y1=ay1, x2=ax2, y2=ay2: capsule_sdf(x, y, x1, y1, x2, y2, 28),
            FUR, alpha=1.0, feather=2.0,
            bbox=(min(ax1, ax2)-30, min(ay1, ay2)-30, max(ax1, ax2)+30, max(ay1, ay2)+30)
        )
        canvas.draw_shape(
            lambda x, y, x1=ax1, y1=ay1+6, x2=ax2, y2=ay2+6: capsule_sdf(x, y, x1, y1, x2, y2, 24),
            FUR_SHADE, alpha=0.3, feather=8.0,
            bbox=(min(ax1, ax2)-30, min(ay1, ay2)-20, max(ax1, ax2)+30, max(ay1, ay2)+30)
        )
    for px, py in [(448, 796), (576, 796)]:
        canvas.draw_shape(
            lambda x, y, cx=px, cy=py: circle_sdf(x, y, cx, cy, 31),
            FUR, alpha=1.0, feather=2.0,
            bbox=(px-31, py-31, px+31, py+31)
        )

    # 17. Leaf on head (moved to top of head, fully visible in front of fur)
    leaf_cx, leaf_cy = 580, 192
    canvas.draw_shape(
        lambda x, y: capsule_sdf(x, y, leaf_cx, leaf_cy+15, leaf_cx-10, leaf_cy-25, 3),
        BAMBOO_SHADE, alpha=1.0, feather=1.0,
        bbox=(leaf_cx-15, leaf_cy-30, leaf_cx+5, leaf_cy+20)
    )
    canvas.draw_shape(
        lambda x, y: rotated_ellipse_sdf(x, y, leaf_cx-12, leaf_cy-10, 34, 15, -30),
        BAMBOO_LEAF, alpha=1.0, feather=1.5,
        bbox=(leaf_cx-50, leaf_cy-35, leaf_cx+20, leaf_cy+15)
    )
    canvas.draw_shape(
        lambda x, y: rotated_ellipse_sdf(x, y, leaf_cx+12, leaf_cy-5, 30, 13, 25),
        BAMBOO_BODY, alpha=1.0, feather=1.5,
        bbox=(leaf_cx-15, leaf_cy-30, leaf_cx+45, leaf_cy+20)
    )

    # 20. Sparkles (sharp 4-point stars)
    sparkles = [
        (196, 296, 27),
        (836, 352, 20),
        (776, 168, 15)
    ]
    for sx, sy, sr in sparkles:
        canvas.draw_shape(
            lambda x, y, cx=sx, cy=sy, r=sr: star4_sdf(x, y, cx, cy, r),
            WHITE, alpha=0.9, feather=1.2,
            bbox=(sx-sr, sy-sr, sx+sr, sy+sr)
        )
        canvas.draw_shape(
            lambda x, y, cx=sx+sr+8, cy=sy-6: circle_sdf(x, y, cx, cy, 4),
            WHITE, alpha=0.85, feather=1.0,
            bbox=(sx+sr+2, sy-12, sx+sr+14, sy)
        )

    print(f"Rendered in {time.time() - t0:.2f}s")
    return canvas.pixels

def save_png(filepath, width, height, pixels):
    row_size = width * 3
    raw_data = bytearray()
    for y in range(height):
        raw_data.append(0)
        start = y * width
        end = start + width
        for px in pixels[start:end]:
            raw_data.extend(px)

    compressed = zlib.compress(raw_data, level=9)

    def chunk(tag, data):
        return struct.pack("!I", len(data)) + tag + data + struct.pack("!I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    ihdr = struct.pack("!IIBBBBB", width, height, 8, 2, 0, 0, 0)

    png = bytearray(b"\x89PNG\r\n\x1a\n")
    png.extend(chunk(b"IHDR", ihdr))
    png.extend(chunk(b"IDAT", compressed))
    png.extend(chunk(b"IEND", b""))

    with open(filepath, "wb") as f:
        f.write(png)

def generate_thumbnail(in_path, out_path, thumb_size=300):
    pixels = render()
    step = WIDTH / thumb_size
    thumb_pixels = []
    for ty in range(thumb_size):
        y0 = int(ty * step)
        y1 = int((ty + 1) * step)
        y1 = max(y0 + 1, min(WIDTH, y1))
        for tx in range(thumb_size):
            x0 = int(tx * step)
            x1 = int((tx + 1) * step)
            x1 = max(x0 + 1, min(WIDTH, x1))

            r_sum = g_sum = b_sum = count = 0
            for y in range(y0, y1):
                row_idx = y * WIDTH
                for x in range(x0, x1):
                    p = pixels[row_idx + x]
                    r_sum += p[0]
                    g_sum += p[1]
                    b_sum += p[2]
                    count += 1
            thumb_pixels.append((r_sum // count, g_sum // count, b_sum // count))

    save_png(out_path, thumb_size, thumb_size, thumb_pixels)

if __name__ == "__main__":
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "out")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "entry.png")

    pixels = render()
    save_png(out_path, WIDTH, HEIGHT, pixels)
    print(f"Saved entry to {out_path}")

    os.makedirs("/tmp/scratch", exist_ok=True)
    generate_thumbnail(out_path, "/tmp/scratch/thumb.png", 300)
    print("Saved thumbnail to /tmp/scratch/thumb.png")
