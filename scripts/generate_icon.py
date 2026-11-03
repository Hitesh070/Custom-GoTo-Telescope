"""
scripts/generate_icon.py
Generates the high-resolution, cropped relativistic black hole app icon
with full alpha channel transparency (zero square background box)
using the user's uploaded black hole visual reference.
Optimized for maximum visual prominence and scale across Windows Taskbar,
Desktop Shortcuts, and File Explorer folder views.
"""

import os
import struct
from io import BytesIO
from PIL import Image
import numpy as np

def write_ico_descending(frames_with_sizes, output_path):
    """
    Writes a Windows .ico binary with icons ordered from largest (256x256)
    down to smallest (16x16). This ensures Windows Explorer and shell extractors
    read the highest-resolution icon as Entry 0 rather than downscaled low-res icons.
    """
    count = len(frames_with_sizes)
    header = struct.pack('<HHH', 0, 1, count)
    
    entries = []
    blobs = []
    offset = 6 + count * 16
    
    for (w, h), img in frames_with_sizes:
        bio = BytesIO()
        img.save(bio, format='PNG')
        blob = bio.getvalue()
        blobs.append(blob)
        
        bw = 0 if w >= 256 else w
        bh = 0 if h >= 256 else h
        # BYTE bWidth, BYTE bHeight, BYTE bColorCount, BYTE bReserved, WORD wPlanes, WORD wBitCount, DWORD dwBytesInRes, DWORD dwImageOffset
        entry = struct.pack('<BBBBHHII', bw, bh, 0, 0, 1, 32, len(blob), offset)
        entries.append(entry)
        offset += len(blob)
        
    with open(output_path, 'wb') as f:
        f.write(header)
        for e in entries:
            f.write(e)
        for b in blobs:
            f.write(b)

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
                
                # Central event horizon: deep circular pitch-black singularity
                if d <= 4.2:
                    out[y, x] = [0, 0, 0, 255]
                elif d <= 5.4 and df < 40:
                    out[y, x] = [0, 0, 0, 255]
                elif df > 7.0:
                    # Smooth alpha transition for glowing accretion disk and photon ring
                    alpha = int(min(255, max(0, (df - 7.0) / 20.0 * 255.0)))
                    r = int(min(255, max(0, c[0] - bg[0] * (1.0 - alpha/255.0))))
                    g = int(min(255, max(0, c[1] - bg[1] * (1.0 - alpha/255.0))))
                    b = int(min(255, max(0, c[2] - bg[2] * (1.0 - alpha/255.0))))
                    # Boost vibrancy and warmth for standout visibility on desktop & taskbar
                    out[y, x] = [min(255, int(r * 1.25)), min(255, int(g * 1.25)), min(255, int(b * 1.25)), alpha]
                else:
                    out[y, x] = [0, 0, 0, 0]

        res = Image.fromarray(out, 'RGBA')
        bbox = res.getbbox()
        cropped = res.crop(bbox)
        cw, ch = cropped.size

        # Maximum scale: fill 252px out of 256px canvas (98.4% vertical coverage)
        target_h = 252
        scale = target_h / float(ch)
        target_w = int(cw * scale)

        scaled = cropped.resize((target_w, target_h), Image.Resampling.LANCZOS)
        scaled_arr = np.array(scaled, dtype=np.float32)

        sw, sh = scaled.size
        center_x = (cx - bbox[0]) * scale

        # Smooth horizontal feathering at outer disk bounds (maximum breadth of 248px)
        max_half_width = 125.0
        for x in range(sw):
            dist_from_center = abs(x - center_x)
            if dist_from_center > (max_half_width - 18.0):
                fade = max(0.0, 1.0 - (dist_from_center - (max_half_width - 18.0)) / 18.0)
                scaled_arr[:, x, 3] *= fade

        scaled_fade = Image.fromarray(scaled_arr.astype(np.uint8), 'RGBA')

        canvas = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        pos_x = int(128.0 - center_x)
        pos_y = int((256 - target_h) // 2)
        canvas.paste(scaled_fade, (pos_x, pos_y), scaled_fade)

        png_path = os.path.join(output_dir, 'black_hole_icon.png')
        ico_path = os.path.join(output_dir, 'black_hole_icon.ico')
        canvas.save(png_path, 'PNG')

        # Generate multi-resolution frames ordered largest to smallest
        sizes = [(256, 256), (128, 128), (96, 96), (64, 64), (48, 48), (40, 40), (32, 32), (24, 24), (20, 20), (16, 16)]
        frames_with_sizes = [((sz[0], sz[1]), canvas.resize(sz, Image.Resampling.LANCZOS)) for sz in sizes]
        write_ico_descending(frames_with_sizes, ico_path)
        print(f"Generated large prominent {png_path} and descending {ico_path} successfully!")

if __name__ == '__main__':
    generate_black_hole_icon()
