"""
scripts/generate_icon.py
Generates the high-resolution, cropped relativistic black hole app icon
with full alpha channel transparency (zero square background box)
using the user's uploaded black hole visual reference.
"""

import os
from PIL import Image
import numpy as np

def generate_black_hole_icon(output_dir="assets"):
    os.makedirs(output_dir, exist_ok=True)
    user_img_path = r"C:\Users\hites\.gemini\antigravity\brain\e6f82116-1df8-436a-a2e2-c1555e3acffc\.user_uploaded\media_1793708446140_0352f28f.png"
    
    if os.path.exists(user_img_path):
        im = Image.open(user_img_path).convert('RGBA')
        arr = np.array(im, dtype=np.float32)
        h, w, _ = arr.shape

        bg = np.array([20.0, 24.0, 32.0], dtype=np.float32)
        rgb = arr[:, :, :3]
        diff = np.sqrt(np.sum((rgb - bg)**2, axis=2))

        cx, cy = 34.0, 15.0
        y_idx, x_idx = np.ogrid[:h, :w]
        dist_center = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)

        out = np.zeros((h, w, 4), dtype=np.uint8)

        for y in range(h):
            for x in range(w):
                d = dist_center[y, x]
                df = diff[y, x]
                c = rgb[y, x]
                
                # Central event horizon (black hole core)
                if d <= 7.0:
                    out[y, x] = [2, 2, 4, 255]
                elif d <= 8.5 and df < 25:
                    out[y, x] = [5, 5, 8, 255]
                elif df > 12.0:
                    alpha = int(min(255, max(0, (df - 12.0) / 45.0 * 255.0)))
                    r = int(min(255, max(0, c[0] - bg[0] * (1.0 - alpha/255.0))))
                    g = int(min(255, max(0, c[1] - bg[1] * (1.0 - alpha/255.0))))
                    b = int(min(255, max(0, c[2] - bg[2] * (1.0 - alpha/255.0))))
                    out[y, x] = [r, g, b, alpha]
                else:
                    out[y, x] = [0, 0, 0, 0]

        res = Image.fromarray(out, 'RGBA')
        canvas = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        scaled = res.resize((int(w * 3.8), int(h * 3.8)), Image.Resampling.LANCZOS)
        sw, sh = scaled.size
        canvas.paste(scaled, ((256 - sw)//2, (256 - sh)//2), scaled)

        png_path = os.path.join(output_dir, 'black_hole_icon.png')
        ico_path = os.path.join(output_dir, 'black_hole_icon.ico')
        canvas.save(png_path, 'PNG')
        sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
        canvas.save(ico_path, format='ICO', sizes=sizes)
        print(f"Generated {png_path} and {ico_path} successfully from reference image!")

if __name__ == '__main__':
    generate_black_hole_icon()
