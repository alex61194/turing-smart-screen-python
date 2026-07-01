from PIL import Image, ImageDraw, ImageFont
import math

W, H = 320, 480
img = Image.new('RGB', (W, H), (10, 8, 18))
draw = ImageDraw.Draw(img)

# EVA-01 palette
P = (110, 13, 208)       # purple
PD = (70, 8, 130)        # purple dark
PVD = (40, 4, 75)        # purple very dark
G = (57, 255, 20)        # green neon
GD = (31, 170, 14)       # green dark
GVD = (18, 90, 10)       # green very dark
O = (248, 149, 4)        # orange
OD = (180, 100, 4)       # orange dark
R = (255, 40, 40)        # red
W_ = (238, 238, 238)     # white
BL = (10, 8, 18)         # black
GY = (45, 40, 55)        # gray
GYL = (65, 60, 80)       # gray light

# === FILL BACKGROUND with subtle gradient ===
for y in range(H):
    r = int(10 + 4 * math.sin(y / H * math.pi))
    g = int(8 + 3 * math.sin(y / H * math.pi))
    b = int(18 + 8 * math.sin(y / H * math.pi))
    draw.line([0, y, W-1, y], fill=(r, g, b))

# === HEXAGON PATTERN ===
def draw_hexagon(draw, cx, cy, r, color):
    points = []
    for i in range(6):
        angle = math.pi / 3 * i + math.pi / 6
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, outline=color)

hex_r = 8
for row in range(H // (hex_r * 3) + 2):
    for col in range(W // (hex_r * 2) + 2):
        hx = col * hex_r * 2 + (hex_r if row % 2 else 0)
        hy = row * hex_r * 3 // 2
        if 8 < hx < W - 8 and 8 < hy < H - 8:
            draw_hexagon(draw, hx, hy, hex_r - 1, (18, 16, 28))

# === PANEL BACKGROUNDS (darker fills with subtle border) ===
panels = [
    (10, 22, W-10, 150),   # CPU
    (10, 168, W-10, 298),  # GPU
    (10, 316, W-10, 428),  # RAM
]
for p in panels:
    draw.rectangle(p, fill=(14, 12, 24))
    # Subtle inner glow on top edge
    draw.line([p[0]+1, p[1]+1, p[2]-1, p[1]+1], fill=PVD, width=1)

# === OUTER FRAME ===
draw.rectangle([0, 0, W-1, H-1], outline=P, width=3)
draw.rectangle([4, 4, W-5, H-5], outline=GD, width=1)

# === CORNER ACCENTS - bold orange cuts ===
corner_size = 16
for cx, cy, dx, dy in [(0, 0, 1, 1), (W-1, 0, -1, 1), (0, H-1, 1, -1), (W-1, H-1, -1, -1)]:
    for i in range(corner_size):
        v = max(0, 255 - i * 12)
        c = (min(255, O[0] - i*3), min(255, O[1] - i*2), O[2])
        draw.point([cx + dx*i, cy + dy*(corner_size-1-i)], fill=O)
        draw.point([cx + dx*i, cy + dy*(corner_size-i)], fill=O)
        draw.point([cx + dx*i, cy + dy*(corner_size+1-i)], fill=OD)
        if i < 4:
            draw.point([cx + dx*i, cy + dy*(corner_size+2-i)], fill=PD)

# === SECTION DIVIDERS - purple with green accent ===
dividers = [155, 303, 432]
for dy in dividers:
    draw.line([8, dy, W-8, dy], fill=P, width=2)
    draw.line([8, dy+2, W-8, dy+2], fill=GD, width=1)
    # Small diamond accents at ends
    for dx in [10, W-12]:
        draw.rectangle([dx, dy-1, dx+3, dy+2], fill=O)

# === HAZARD STRIPES top/bottom ===
stripe_h = 4
for x in range(20, W-20, 12):
    for i in range(6):
        px = x + i
        if px >= W - 20:
            break
        if (i + x // 12) % 2 == 0:
            draw.rectangle([px, 8, px+3, 8+stripe_h], fill=O)
            draw.rectangle([px, H-12-stripe_h, px+3, H-12], fill=O)

# === VERTICAL ACCENT STRIPE left edge ===
for y in range(20, H-20, 6):
    seg = (y // 6) % 10
    if seg < 4:
        draw.line([6, y, 6, y+3], fill=P if seg < 2 else PD)

# === NERV-STYLE CORNER BRACKETS ===
bl = 22
bo = 7
# Top-left
draw.line([bo, bo+bl, bo, bo], fill=G, width=2)
draw.line([bo, bo, bo+bl, bo], fill=G, width=2)
# Top-right
draw.line([W-bo-bl, bo, W-bo, bo], fill=G, width=2)
draw.line([W-bo, bo, W-bo, bo+bl], fill=G, width=2)
# Bottom-left
draw.line([bo, H-bo-bl, bo, H-bo], fill=G, width=2)
draw.line([bo, H-bo, bo+bl, H-bo], fill=G, width=2)
# Bottom-right
draw.line([W-bo-bl, H-bo, W-bo, H-bo], fill=G, width=2)
draw.line([W-bo, H-bo-bl, W-bo, H-bo], fill=G, width=2)

# === SECTION HEADERS ===
try:
    font_label = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 10)
    font_small = ImageFont.truetype("res/fonts/roboto/Roboto-Regular.ttf", 8)
    font_tiny = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 7)
except:
    font_label = ImageFont.load_default()
    font_small = font_label
    font_tiny = font_label

# CPU section
draw.text((12, 12), "UNIT-01 // CPU", font=font_label, fill=O)
draw.text((W-60, 12), "SYS", font=font_tiny, fill=GYL)
# Green status dot
draw.ellipse([W-14, 13, W-8, 19], fill=G)

# GPU section
draw.text((12, 160), "UNIT-01 // GPU", font=font_label, fill=O)
draw.text((W-60, 160), "SYS", font=font_tiny, fill=GYL)
draw.ellipse([W-14, 161, W-8, 167], fill=G)

# RAM section
draw.text((12, 308), "UNIT-01 // MEMORY", font=font_label, fill=O)
draw.ellipse([W-14, 309, W-8, 315], fill=G)

# Bottom telemetry
draw.text((12, 436), "TELEMETRY", font=font_label, fill=O)

# === RADIAL GUIDE CIRCLES (faint decoration) ===
# CPU radial area
ccx, ccy = 75, 88
draw.ellipse([ccx-42, ccy-42, ccx+42, ccy+42], outline=(22, 20, 35), width=1)
draw.ellipse([ccx-38, ccy-38, ccx+38, ccy+38], outline=(18, 16, 30), width=1)
# Small crosshair
draw.line([ccx-5, ccy, ccx+5, ccy], fill=(25, 23, 38), width=1)
draw.line([ccx, ccy-5, ccx, ccy+5], fill=(25, 23, 38), width=1)

# GPU radial area
gcx, gcy = 75, 240
draw.ellipse([gcx-46, gcy-46, gcx+46, gcy+46], outline=(22, 20, 35), width=1)
draw.ellipse([gcx-42, gcy-42, gcx+42, gcy+42], outline=(18, 16, 30), width=1)
draw.line([gcx-5, gcy, gcx+5, gcy], fill=(25, 23, 38), width=1)
draw.line([gcx, gcy-5, gcx, gcy+5], fill=(25, 23, 38), width=1)

# === DECORATIVE DATA DOTS (right side of panels) ===
import random
random.seed(42)
for panel in panels:
    x_start = W - 55
    x_end = W - 18
    y_start = panel[1] + 12
    y_end = panel[3] - 12
    for _ in range(25):
        dx = random.randint(x_start, x_end)
        dy = random.randint(y_start, y_end)
        v = random.choice([GVD, PVD, (20, 18, 32)])
        draw.point([dx, dy], fill=v)
        draw.point([dx+1, dy], fill=v)

# === SMALL LABELS near radials ===
draw.text((130, 130), "FAN", font=font_tiny, fill=GYL)
draw.text((130, 282), "FAN", font=font_tiny, fill=GYL)

# === BOTTOM BAR ACCENTS ===
# Small purple bar under FPS area
draw.rectangle([10, 470, 95, 472], fill=P)
# Small green accent
draw.rectangle([100, 470, 210, 472], fill=GD)
# Network area accent
draw.rectangle([215, 470, 310, 472], fill=PVD)

# === SAVE ===
img.save("res/themes/CyberEVA01/background.png")
print("Background generated: res/themes/CyberEVA01/background.png")
print(f"Size: {W}x{H}")
