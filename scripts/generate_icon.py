"""
scripts/generate_icon.py
Generates the high-resolution, cropped relativistic black hole app icon
with full alpha channel transparency (zero square background box)
using the user's uploaded black hole visual reference.
Optimized for maximum visual prominence and scale in Windows Taskbar and File Explorer.
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

        bg = np.array([21.0, 24.0, 32.0], dtype=np.float32)
        rgb = arr[:, :, :3]
        diff = np.sqrt(np.sum((rgb - bg)**2, axis=2))

        # True center of the black hole event horizon
        cx, cy = 35.5, 18.5
        y_idx, x_idx = np.ogrid[:h, :w]
        dist_center = np.sqrt((x_idx - cx)**2 + (y_idx - cy)**2)

        out = np.zeros((h, w, 4), dtype=np.uint8)

        for y in range(h):
            for x in range(w):
                d = dist_center[y, x]
                df = diff[y, x]
                c = rgb[y, x]
                
                # Central event horizon: deep pitch-black singularity
                if d <= 4.2:
                    out[y, x] = [0, 0, 0, 255]
                elif d <= 5.5 and df < 40:
                    out[y, x] = [0, 0, 0, 255]
                elif df > 7.0:
                    # Smooth alpha transition for glowing accretion disk and photon ring
                    alpha = int(min(255, max(0, (df - 7.0) / 22.0 * 255.0)))
                    r = int(min(255, max(0, c[0] - bg[0] * (1.0 - alpha/255.0))))
                    g = int(min(255, max(0, c[1] - bg[1] * (1.0 - alpha/255.0))))
                    b = int(min(255, max(0, c[2] - bg[2] * (1.0 - alpha/255.0))))
                    # Boost vibrancy for dark taskbar clarity
                    out[y, x] = [min(255, int(r * 1.15)), min(255, int(g * 1.15)), min(255, int(b * 1.15)), alpha]
                else:
                    out[y, x] = [0, 0, 0, 0]

        res = Image.fromarray(out, 'RGBA')
        bbox = res.getbbox()
        cropped = res.crop(bbox)
        cw, ch = cropped.size

        # Target height: 215px (84% vertical coverage of 256px canvas to match standard apps)
        target_h = 215
        scale = target_h / float(ch)
        target_w = int(cw * scale)

        scaled = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        scaled_arr = np.array(scaled, dtype=np.float32)

        sw, sh = scaled.size
        center_x = (cx - bbox[0]) * scale

        # Smooth horizontal feathering at outer disk bounds
        max_half_width = 120.0
        for x in range(sw):
            dist_from_center = abs(x - center_x)
            if dist_from_center > (max_half_width - 25.0):
                fade = max(0.0, 1.0 - (dist_from_center - (max_half_width - 25.0)) / 25.0)
                scaled_arr[:, x, 3] *= fade

        scaled_fade = Image.fromarray(scaled_arr.astype(np.uint8), 'RGBA')

        canvas = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        pos_x = int(128.0 - center_x)
        pos_y = int((256 - target_h) // 2)
        canvas.paste(scaled_fade, (pos_x, pos_y), scaled_fade)

        png_path = os.path.join(output_dir, 'black_hole_icon.png')
        ico_path = os.path.join(output_dir, 'black_hole_icon.ico')
        canvas.save(png_path, 'PNG')

        # Generate multi-resolution ICO including all standard Windows taskbar/explorer sizes
        sizes = [(256, 256), (128, 128), (96, 96), (64, 64), (48, 48), (40, 40), (32, 32), (24, 24), (20, 20), (16, 16)]
        frames = [canvas.resize(sz, Image.Resampling.LANCZOS) for sz in sizes]
        frames[0].save(ico_path, format='ICO', sizes=sizes, append_images=frames[1:])
        print(f"Generated large prominent {png_path} and {ico_path} successfully!")

if __name__ == '__main__':
    generate_black_hole_icon()
