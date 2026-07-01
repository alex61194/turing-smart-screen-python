from PIL import Image, ImageDraw, ImageFont
import math

W, H = 480, 320
img = Image.new('RGB', (W, H), (5, 5, 5))
draw = ImageDraw.Draw(img)

EVA_PURPLE = (110, 13, 208)
EVA_PURPLE_D = (74, 10, 140)
EVA_GREEN = (57, 255, 20)
EVA_GREEN_D = (31, 170, 14)
EVA_ORANGE = (248, 149, 4)
EVA_RED = (255, 0, 0)
EVA_WHITE = (238, 238, 238)
EVA_BLACK = (5, 5, 5)
EVA_GRAY = (77, 77, 77)

# Outer frame - purple border
border = 3
draw.rectangle([0, 0, W-1, H-1], outline=EVA_PURPLE, width=border)

# Inner accent line - green
draw.rectangle([border+2, border+2, W-border-3, H-border-3], outline=EVA_GREEN_D, width=1)

# Section dividers
# Vertical divider between CPU (left) and GPU (right)
mid_x = 240
draw.line([mid_x, 8, mid_x, H-8], fill=EVA_PURPLE, width=2)
draw.line([mid_x+1, 8, mid_x+1, H-8], fill=EVA_GREEN_D, width=1)

# Horizontal divider for bottom section (FPS/Network)
div_y = 230
draw.line([8, div_y, W-8, div_y], fill=EVA_PURPLE, width=2)
draw.line([8, div_y+1, W-8, div_y+1], fill=EVA_GREEN_D, width=1)

# Corner accents - orange diagonal cuts
corner_size = 12
for cx, cy, dx, dy in [(0, 0, 1, 1), (W-1, 0, -1, 1), (0, H-1, 1, -1), (W-1, H-1, -1, -1)]:
    for i in range(corner_size):
        draw.point([cx + dx*i, cy + dy*(corner_size-1-i)], fill=EVA_ORANGE)
        draw.point([cx + dx*i, cy + dy*(corner_size-i)], fill=EVA_ORANGE)

# Section labels (orange, small)
try:
    font_label = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 8)
    font_header = ImageFont.truetype("res/fonts/roboto/Roboto-Bold.ttf", 10)
except:
    font_label = ImageFont.load_default()
    font_header = ImageFont.load_default()

# CPU section header
draw.text((10, 6), "UNIT-01 // CPU", font=font_label, fill=EVA_ORANGE)
# GPU section header
draw.text((mid_x+6, 6), "UNIT-01 // GPU", font=font_label, fill=EVA_ORANGE)

# Bottom section header
draw.text((10, div_y+4), "TELEMETRY", font=font_label, fill=EVA_ORANGE)

# Hazard stripes on top and bottom borders (NERV style)
stripe_y_top = 16
stripe_y_bot = H - 16
for x in range(8, W-8, 8):
    for i in range(8):
        px = x + i
        if px >= W - 8:
            break
        # Diagonal hazard pattern
        if (i + x // 8) % 2 == 0:
            draw.point([px, stripe_y_top], fill=EVA_ORANGE)
            draw.point([px, stripe_y_bot], fill=EVA_ORANGE)

# Hexagon pattern in background (subtle)
def draw_hexagon(draw, cx, cy, r, color):
    points = []
    for i in range(6):
        angle = math.pi / 3 * i + math.pi / 6
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, outline=color)

hex_r = 8
for row in range(H // (hex_r * 3) + 1):
    for col in range(W // (hex_r * 2) + 1):
        hx = col * hex_r * 2 + (hex_r if row % 2 else 0)
        hy = row * hex_r * 3 // 2
        if 20 < hx < W - 20 and 20 < hy < div_y - 5:
            draw_hexagon(draw, hx, hy, hex_r - 1, (20, 20, 30))

# Radial guide circles (faint)
# CPU% radial position: (80, 80)
draw.ellipse([80-42, 80-42, 80+42, 80+42], outline=(30, 30, 40), width=1)
# GPU% radial position: (387, 80) 
draw.ellipse([387-54, 80-54, 387+54, 80+54], outline=(30, 30, 40), width=1)

# Save
img.save("res/themes/EVA01/background.png")
print("Background generated: res/themes/EVA01/background.png")
