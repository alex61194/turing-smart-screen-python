from PIL import Image, ImageDraw, ImageFont
import math

W, H = 320, 480
img = Image.new('RGB', (W, H), (8, 6, 14))
draw = ImageDraw.Draw(img)

# EVA-01 palette
P = (110, 13, 208)
PD = (70, 8, 130)
PVD = (40, 4, 75)
G = (57, 255, 20)
GD = (31, 170, 14)
GVD = (18, 90, 10)
O = (248, 149, 4)
OD = (180, 100, 4)
W_ = (238, 238, 238)
BL = (8, 6, 14)
GY = (40, 35, 50)
GYL = (60, 55, 75)

# === BACKGROUND gradient ===
for y in range(H):
    r = int(8 + 2 * math.sin(y / H * math.pi))
    g = int(6 + 2 * math.sin(y / H * math.pi))
    b = int(14 + 5 * math.sin(y / H * math.pi))
    draw.line([0, y, W-1, y], fill=(r, g, b))

# === HEXAGON pattern ===
def draw_hexagon(draw, cx, cy, r, color):
    points = []
    for i in range(6):
        angle = math.pi / 3 * i + math.pi / 6
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, outline=color)

hex_r = 7
for row in range(H // (hex_r * 3) + 2):
    for col in range(W // (hex_r * 2) + 2):
        hx = col * hex_r * 2 + (hex_r if row % 2 else 0)
        hy = row * hex_r * 3 // 2
        if 8 < hx < W - 8 and 8 < hy < H - 8:
            draw_hexagon(draw, hx, hy, hex_r - 1, (14, 12, 22))

# === PANELS ===
panels = [
    (8, 18, W-8, 195),    # CPU
    (8, 208, W-8, 385),   # GPU
    (8, 398, W-8, 468),   # Memory + Bottom
]
for p in panels:
    draw.rectangle(p, fill=(12, 10, 20))
    draw.line([p[0]+1, p[1]+1, p[2]-1, p[1]+1], fill=PVD, width=1)

# === OUTER FRAME ===
draw.rectangle([0, 0, W-1, H-1], outline=P, width=3)
draw.rectangle([4, 4, W-5, H-5], outline=GD, width=1)

# === CORNER ACCENTS ===
corner_size = 14
for cx, cy, dx, dy in [(0, 0, 1, 1), (W-1, 0, -1, 1), (0, H-1, 1, -1), (W-1, H-1, -1, -1)]:
    for i in range(corner_size):
        draw.point([cx + dx*i, cy + dy*(corner_size-1-i)], fill=O)
        draw.point([cx + dx*i, cy + dy*(corner_size-i)], fill=O)
        draw.point([cx + dx*i, cy + dy*(corner_size+1-i)], fill=OD)

# === SECTION DIVIDERS ===
dividers = [200, 392]
for dy in dividers:
    draw.line([8, dy, W-8, dy], fill=P, width=2)
    draw.line([8, dy+2, W-8, dy+2], fill=GD, width=1)
    for dx in [10, W-13]:
        draw.rectangle([dx, dy-1, dx+4, dy+2], fill=O)

# === HAZARD STRIPES ===
for x in range(20, W-20, 12):
    for i in range(6):
        px = x + i
        if px >= W - 20: break
        if (i + x // 12) % 2 == 0:
            draw.rectangle([px, 8, px+3, 12], fill=O)
            draw.rectangle([px, H-12, px+3, H-8], fill=O)

# === VERTICAL ACCENT left edge ===
for y in range(20, H-20, 6):
    seg = (y // 6) % 10
    if seg < 3:
        draw.line([6, y, 6, y+2], fill=P if seg < 2 else PD)

# === NERV CORNER BRACKETS ===
bl, bo = 18, 7
draw.line([bo, bo+bl, bo, bo], fill=G, width=2)
draw.line([bo, bo, bo+bl, bo], fill=G, width=2)
draw.line([W-bo-bl, bo, W-bo, bo], fill=G, width=2)
draw.line([W-bo, bo, W-bo, bo+bl], fill=G, width=2)
draw.line([bo, H-bo-bl, bo, H-bo], fill=G, width=2)
draw.line([bo, H-bo, bo+bl, H-bo], fill=G, width=2)
draw.line([W-bo-bl, H-bo, W-bo, H-bo], fill=G, width=2)
draw.line([W-bo, H-bo-bl, W-bo, H-bo], fill=G, width=2)

# === FONTS ===
try:
    font_hdr = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 9)
except:
    font_hdr = ImageFont.load_default()

# === SECTION HEADERS ===
draw.text((12, 10), "UNIT-01 // CPU", font=font_hdr, fill=O)
draw.ellipse([W-14, 11, W-8, 17], fill=G)

draw.text((12, 200), "UNIT-01 // GPU", font=font_hdr, fill=O)
draw.ellipse([W-14, 201, W-8, 207], fill=G)

draw.text((12, 392), "UNIT-01 // MEMORY", font=font_hdr, fill=O)

# === CPU RADIAL GUIDE (X=120, Y=108, RADIUS=72) ===
ccx, ccy, cr = 120, 108, 72
draw.ellipse([ccx-cr-2, ccy-cr-2, ccx+cr+2, ccy+cr+2], outline=(20, 18, 32), width=1)
draw.ellipse([ccx-cr+8, ccy-cr+8, ccx+cr-8, ccy+cr-8], outline=(16, 14, 28), width=1)
# Crosshair
draw.line([ccx-6, ccy, ccx+6, ccy], fill=(18, 16, 30), width=1)
draw.line([ccx, ccy-6, ccx, ccy+6], fill=(18, 16, 30), width=1)
# Tick marks
for angle_deg in [0, 90, 180, 270]:
    angle_rad = math.radians(angle_deg)
    x1 = ccx + int((cr-4) * math.cos(angle_rad))
    y1 = ccy + int((cr-4) * math.sin(angle_rad))
    x2 = ccx + int((cr+1) * math.cos(angle_rad))
    y2 = ccy + int((cr+1) * math.sin(angle_rad))
    draw.line([x1, y1, x2, y2], fill=GYL, width=1)

# === GPU RADIAL GUIDE (X=120, Y=298, RADIUS=72) ===
gcx, gcy, gr = 120, 298, 72
draw.ellipse([gcx-gr-2, gcy-gr-2, gcx+gr+2, gcy+gr+2], outline=(22, 10, 45), width=1)
draw.ellipse([gcx-gr+8, gcy-gr+8, gcx+gr-8, gcy+gr-8], outline=(16, 12, 30), width=1)
draw.line([gcx-6, gcy, gcx+6, gcy], fill=(18, 14, 32), width=1)
draw.line([gcx, gcy-6, gcx, gcy+6], fill=(18, 14, 32), width=1)
for angle_deg in [0, 90, 180, 270]:
    angle_rad = math.radians(angle_deg)
    x1 = gcx + int((gr-4) * math.cos(angle_rad))
    y1 = gcy + int((gr-4) * math.sin(angle_rad))
    x2 = gcx + int((gr+1) * math.cos(angle_rad))
    y2 = gcy + int((gr+1) * math.sin(angle_rad))
    draw.line([x1, y1, x2, y2], fill=GYL, width=1)

# === RIGHT SIDE DATA PANELS ===
# CPU data panel (x=230 to W-12)
draw.rectangle([230, 24, W-12, 188], fill=(14, 11, 24), outline=PVD)
# GPU data panel
draw.rectangle([230, 214, W-12, 378], fill=(14, 11, 24), outline=PVD)

# === FAN labels near small radials ===
# CPU fan at X=120, Y=178
draw.text((140, 175), "FAN", font=font_hdr, fill=GYL)
# GPU fan at X=120, Y=368
draw.text((140, 365), "FAN", font=font_hdr, fill=GYL)

# === MEMORY section internal divider ===
draw.line([10, 428, W-10, 428], fill=PVD, width=1)

# === BOTTOM BAR dividers ===
draw.line([105, 398, 105, 468], fill=PVD, width=1)
draw.line([210, 398, 210, 468], fill=PVD, width=1)

img.save("res/themes/CyberEVA01/background.png")
print("Background generated: res/themes/CyberEVA01/background.png")
