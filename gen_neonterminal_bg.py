from PIL import Image, ImageDraw, ImageFont
import math

W, H = 320, 480
img = Image.new('RGB', (W, H), (6, 5, 12))
draw = ImageDraw.Draw(img)

# EVA-01 palette
P = (110, 13, 208)
PD = (70, 8, 130)
PVD = (35, 4, 65)
G = (57, 255, 20)
GD = (31, 170, 14)
GVD = (15, 80, 8)
O = (248, 149, 4)
OD = (180, 100, 4)
W_ = (238, 238, 238)
BL = (6, 5, 12)
GY = (35, 30, 45)
GYL = (55, 50, 70)

# === BACKGROUND ===
for y in range(H):
    draw.line([0, y, W-1, y], fill=(6, 5, 12))

# === SUBTLE GRID PATTERN ===
grid_color = (10, 9, 18)
for x in range(0, W, 20):
    draw.line([x, 0, x, H], fill=grid_color, width=1)
for y in range(0, H, 20):
    draw.line([0, y, W, y], fill=grid_color, width=1)

# === OUTER FRAME ===
draw.rectangle([0, 0, W-1, H-1], outline=P, width=2)
draw.rectangle([3, 3, W-4, H-4], outline=GD, width=1)

# === SECTION DIVIDERS ===
# Top section: CPU (y 10-230)
# Middle section: GPU (y 240-460)
# Bottom: Memory (y 465-475)
draw.line([8, 234, W-8, 234], fill=P, width=2)
draw.line([8, 236, W-8, 236], fill=GD, width=1)

# === SECTION HEADERS ===
try:
    font_hdr = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 10)
    font_tiny = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 8)
    font_label = ImageFont.truetype("res/fonts/roboto/Roboto-Regular.ttf", 9)
except:
    font_hdr = ImageFont.load_default()
    font_tiny = font_hdr
    font_label = font_hdr

# CPU header
draw.text((12, 8), "PROCESSOR", font=font_hdr, fill=O)
draw.text((100, 9), "//", font=font_tiny, fill=GYL)
draw.text((115, 8), "I7-12700K", font=font_label, fill=W_)

# GPU header
draw.text((12, 240), "GRAPHICS", font=font_hdr, fill=O)
draw.text((95, 241), "//", font=font_tiny, fill=GYL)
draw.text((110, 240), "RTX 4070", font=font_label, fill=W_)

# === CPU RADIAL AREA (centered, large) ===
# CPU radial: X=85, Y=130, RADIUS=65
ccx, ccy, cr = 85, 130, 65
# Outer ring
draw.ellipse([ccx-cr-2, ccy-cr-2, ccx+cr+2, ccy+cr+2], outline=(15, 13, 25), width=1)
# Inner rings
draw.ellipse([ccx-cr+10, ccy-cr+10, ccx+cr-10, ccy+cr-10], outline=(12, 10, 20), width=1)
draw.ellipse([ccx-cr+20, ccy-cr+20, ccx+cr-20, ccy+cr-20], outline=(10, 8, 18), width=1)
# Crosshair
draw.line([ccx-8, ccy, ccx+8, ccy], fill=(14, 12, 22), width=1)
draw.line([ccx, ccy-8, ccx, ccy+8], fill=(14, 12, 22), width=1)
# Tick marks
for angle_deg in range(0, 360, 45):
    angle_rad = math.radians(angle_deg)
    x1 = ccx + int((cr-6) * math.cos(angle_rad))
    y1 = ccy + int((cr-6) * math.sin(angle_rad))
    x2 = ccx + int((cr+1) * math.cos(angle_rad))
    y2 = ccy + int((cr+1) * math.sin(angle_rad))
    draw.line([x1, y1, x2, y2], fill=GYL, width=1)

# === GPU RADIAL AREA ===
# GPU radial: X=85, Y=355, RADIUS=65
gcx, gcy, gr = 85, 355, 65
draw.ellipse([gcx-gr-2, gcy-gr-2, gcx+gr+2, gcy+gr+2], outline=(18, 8, 35), width=1)
draw.ellipse([gcx-gr+10, gcy-gr+10, gcx+gr-10, gcy+gr-10], outline=(14, 6, 28), width=1)
draw.ellipse([gcx-gr+20, gcy-gr+20, gcx+gr-20, gcy+gr-20], outline=(10, 4, 22), width=1)
draw.line([gcx-8, gcy, gcx+8, gcy], fill=(16, 6, 30), width=1)
draw.line([gcx, gcy-8, gcx, gcy+8], fill=(16, 6, 30), width=1)
for angle_deg in range(0, 360, 45):
    angle_rad = math.radians(angle_deg)
    x1 = gcx + int((gr-6) * math.cos(angle_rad))
    y1 = gcy + int((gr-6) * math.sin(angle_rad))
    x2 = gcx + int((gr+1) * math.cos(angle_rad))
    y2 = gcy + int((gr+1) * math.sin(angle_rad))
    draw.line([x1, y1, x2, y2], fill=GYL, width=1)

# === RIGHT SIDE DATA PANELS ===
# CPU data panel
draw.rectangle([165, 20, W-12, 225], fill=(10, 8, 18), outline=PVD)
# GPU data panel
draw.rectangle([165, 252, W-12, 455], fill=(10, 8, 18), outline=PVD)

# === DATA PANEL LABELS (inside panels) ===
draw.text((170, 24), "FREQ", font=font_tiny, fill=GYL)
draw.text((170, 58), "TEMP", font=font_tiny, fill=GYL)
draw.text((170, 96), "POWER", font=font_tiny, fill=GYL)
draw.text((170, 130), "FAN", font=font_tiny, fill=GYL)
draw.text((170, 164), "FPS", font=font_tiny, fill=GYL)

draw.text((170, 256), "VRAM", font=font_tiny, fill=GYL)
draw.text((170, 290), "TEMP", font=font_tiny, fill=GYL)
draw.text((170, 328), "POWER", font=font_tiny, fill=GYL)
draw.text((170, 362), "FAN", font=font_tiny, fill=GYL)
draw.text((170, 396), "LOAD", font=font_tiny, fill=GYL)

# === HORIZONTAL SEPARATOR LINES inside panels ===
for py in [52, 90, 124, 158, 198]:
    draw.line([168, py, W-15, py], fill=PVD, width=1)
for py in [284, 322, 356, 390, 430]:
    draw.line([168, py, W-15, py], fill=PVD, width=1)

# === BOTTOM BAR (memory) ===
draw.line([8, 462, W-8, 462], fill=P, width=1)
draw.rectangle([12, 465, 200, 473], fill=PVD)  # memory bar background

# === CORNER ACCENTS ===
corner_size = 10
for cx, cy, dx, dy in [(0, 0, 1, 1), (W-1, 0, -1, 1), (0, H-1, 1, -1), (W-1, H-1, -1, -1)]:
    for i in range(corner_size):
        draw.point([cx + dx*i, cy + dy*(corner_size-1-i)], fill=O)
        draw.point([cx + dx*i, cy + dy*(corner_size-i)], fill=O)

# === HAZARD STRIPES (top/bottom) ===
for x in range(15, W-15, 10):
    for i in range(5):
        px = x + i
        if px >= W - 15: break
        if (i + x // 10) % 2 == 0:
            draw.rectangle([px, 5, px+2, 8], fill=O)
            draw.rectangle([px, H-8, px+2, H-5], fill=O)

img.save("res/themes/NeonTerminal/background.png")
print("Background generated: res/themes/NeonTerminal/background.png")
