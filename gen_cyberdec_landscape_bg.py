from PIL import Image, ImageDraw
import math

W, H = 480, 320
img = Image.new('RGB', (W, H), (8, 10, 18))
draw = ImageDraw.Draw(img)

CYAN = (50, 216, 243)
PURPLE = (255, 200, 255)
DARK_CYAN = (20, 80, 100)

# Outer border
draw.rectangle([0, 0, W-1, H-1], outline=(30, 60, 80), width=2)

# Section dividers
# Vertical divider CPU | GPU
mid_x = 240
draw.line([mid_x, 5, mid_x, 145], fill=(30, 60, 80), width=1)
draw.line([mid_x+1, 5, mid_x+1, 145], fill=DARK_CYAN, width=1)

# Horizontal divider RAM | bottom
div_y1 = 145
draw.line([5, div_y1, W-5, div_y1], fill=(30, 60, 80), width=1)
draw.line([5, div_y1+1, W-5, div_y1+1], fill=DARK_CYAN, width=1)

# Horizontal divider bottom | FPS/date
div_y2 = 250
draw.line([5, div_y2, W-5, div_y2], fill=(30, 60, 80), width=1)
draw.line([5, div_y2+1, W-5, div_y2+1], fill=DARK_CYAN, width=1)

# Corner accents - cyan diagonal
for cx, cy, dx, dy in [(0, 0, 1, 1), (W-1, 0, -1, 1), (0, H-1, 1, -1), (W-1, H-1, -1, -1)]:
    for i in range(10):
        draw.point([cx + dx*i, cy + dy*(9-i)], fill=CYAN)

# Subtle grid pattern in background
for x in range(0, W, 20):
    draw.line([x, 0, x, H], fill=(12, 15, 25), width=1)
for y in range(0, H, 20):
    draw.line([0, y, W, y], fill=(12, 15, 25), width=1)

# Accent lines near borders
draw.line([3, 3, W-4, 3], fill=CYAN, width=1)
draw.line([3, H-4, W-4, H-4], fill=CYAN, width=1)
draw.line([3, 3, 3, H-4], fill=CYAN, width=1)
draw.line([W-4, 3, W-4, H-4], fill=CYAN, width=1)

# Faint glow accents at section corners
for px, py in [(mid_x, div_y1), (mid_x, div_y2)]:
    for r in range(5, 0, -1):
        color_val = max(0, 30 - r*5)
        draw.point([px, py], fill=(color_val, color_val+10, color_val+10))

img.save("res/themes/CyberDecimorLandscape/background.png")
print("OK")
