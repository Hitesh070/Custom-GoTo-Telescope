"""
scripts/generate_icon.py
Generates the high-resolution, cropped relativistic black hole app icon
with full alpha channel transparency (zero square background box).
"""

import os
import math
from PIL import Image

def generate_black_hole_icon(output_dir="assets"):
    os.makedirs(output_dir, exist_ok=True)
    size = 512
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    cx, cy = size / 2.0, size / 2.0
    r_event = 68.0    # Event horizon radius
    r_photon = 74.0   # Photon ring radius
    r_disk_inner = 76.0
    r_disk_outer = 220.0

    pixels = img.load()

    for y in range(size):
        for x in range(size):
            dx = x - cx
            dy = y - cy
            dist = math.hypot(dx, dy)
            
            # Outer boundary transparency
            if dist > 240:
                continue
                
            # 1. Pitch black central event horizon
            if dist < r_event:
                pixels[x, y] = (5, 5, 8, 255)
                continue
                
            intensity = 0.0
            
            # 2. Photon sphere ring (razor-thin bright circular ring)
            if abs(dist - r_photon) < 3.5:
                p_factor = math.exp(-0.5 * ((dist - r_photon) / 1.5) ** 2)
                intensity += p_factor * 2.2
                
            # 3. Main tilted equatorial accretion disk
            inclination_tilt = 0.28
            y_disk = (dy - dx * 0.12) / inclination_tilt
            dist_disk = math.hypot(dx, y_disk)
            
            if r_disk_inner <= dist_disk <= r_disk_outer:
                peak_r = 105.0
                width_r = 45.0 if dist_disk < peak_r else 70.0
                d_prof = math.exp(-0.5 * ((dist_disk - peak_r) / width_r) ** 2)
                doppler = 1.0 - 0.45 * (dx / r_disk_outer)
                v_falloff = math.exp(-0.5 * (abs(dy - dx * 0.12) / (7.0 + 0.05 * dist_disk)) ** 2)
                intensity += d_prof * doppler * v_falloff * 2.5

            # 4. Relativistic Gravitational Lensing Arcs (upper and lower halo arcs over the shadow)
            lens_dist_top = math.hypot(dx * 1.15, (dy + 25) * 1.35)
            if 65 < lens_dist_top < 130:
                lens_prof = math.exp(-0.5 * ((lens_dist_top - 90) / 18.0) ** 2)
                doppler_lens = 1.0 - 0.35 * (dx / 100.0)
                intensity += lens_prof * doppler_lens * 1.4

            lens_dist_bot = math.hypot(dx * 1.25, (dy - 20) * 1.5)
            if 65 < lens_dist_bot < 120:
                lens_prof_b = math.exp(-0.5 * ((lens_dist_bot - 82) / 16.0) ** 2)
                doppler_lens_b = 1.0 - 0.35 * (dx / 100.0)
                intensity += lens_prof_b * doppler_lens_b * 1.0

            # Overall ambient corona glow falloff
            corona = math.exp(-dist / 80.0) * 0.35
            intensity += corona
            
            if dist < r_event + 1.5:
                intensity = 0.0
                pixels[x, y] = (5, 5, 8, 255)
                continue

            if intensity <= 0.01:
                continue

            # Color mapping
            intensity = min(3.0, intensity)
            if intensity > 1.8:
                t = (intensity - 1.8) / 1.2
                r = int(255)
                g = int(220 + 35 * t)
                b = int(140 + 115 * t)
            elif intensity > 0.8:
                t = (intensity - 0.8) / 1.0
                r = int(255)
                g = int(140 + 80 * t)
                b = int(30 + 110 * t)
            else:
                t = intensity / 0.8
                r = int(180 + 75 * t)
                g = int(50 + 90 * t)
                b = int(10 + 20 * t)

            # Smooth outer transparency falloff (cropped to black hole glow)
            outer_fade = 1.0 if dist < 180 else max(0.0, 1.0 - (dist - 180) / 60.0)
            alpha = int(min(255, max(0, intensity * 190.0 * outer_fade)))
            
            if alpha > 0:
                pixels[x, y] = (r, g, b, alpha)

    png_path = os.path.join(output_dir, 'black_hole_icon.png')
    ico_path = os.path.join(output_dir, 'black_hole_icon.ico')
    img.save(png_path, 'PNG')
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]
    img.save(ico_path, format='ICO', sizes=sizes)
    print(f'Successfully generated {png_path} and {ico_path}')

if __name__ == '__main__':
    generate_black_hole_icon()
