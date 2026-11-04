"""
astrometry.py
High-precision astronomical coordinate transformations, ephemeris calculations,
and formatting utilities for the Custom GoTo Telescope Mount.
"""

from __future__ import annotations
import math
from typing import Tuple


def deg_to_dms(d: float, signed: bool = True, decimals: int = 1) -> str:
    """Formats degrees to +/-DD° MM' SS.S\" string with exact fractional precision."""
    s = '-' if d < 0 else ('+' if signed else '')
    d_abs = abs(d)
    deg = int(d_abs)
    rem = (d_abs - deg) * 60.0
    m = int(rem)
    sec = (rem - m) * 60.0
    if decimals == 1:
        return f"{s}{deg:02d}° {m:02d}' {sec:04.1f}\""
    elif decimals == 2:
        return f"{s}{deg:02d}° {m:02d}' {sec:05.2f}\""
    else:
        return f"{s}{deg:02d}° {m:02d}' {int(sec):02d}\""


def deg_to_hms(d: float, decimals: int = 2) -> str:
    """Formats degrees (0..360) to HHh MMm SS.SSs string matching Stellarium."""
    h = (d % 360.0) / 15.0
    hh = int(h)
    rem = (h - hh) * 60.0
    mm = int(rem)
    sec = (rem - mm) * 60.0
    if decimals == 2:
        return f"{hh:02d}h {mm:02d}m {sec:05.2f}s"
    elif decimals == 1:
        return f"{hh:02d}h {mm:02d}m {sec:04.1f}s"
    else:
        return f"{hh:02d}h {mm:02d}m {int(sec):02d}s"


def hours_to_hms(h: float, decimals: int = 2) -> str:
    """Formats hours (0..24) to HHh MMm SS.SSs string matching Stellarium."""
    h_norm = h % 24.0
    hh = int(h_norm)
    rem = (h_norm - hh) * 60.0
    mm = int(rem)
    sec = (rem - mm) * 60.0
    if decimals == 2:
        return f"{hh:02d}h {mm:02d}m {sec:05.2f}s"
    elif decimals == 1:
        return f"{hh:02d}h {mm:02d}m {sec:04.1f}s"
    else:
        return f"{hh:02d}h {mm:02d}m {int(sec):02d}s"


def radec_to_galactic(ra_deg: float, dec_deg: float) -> Tuple[float, float]:
    """Converts J2000 RA/Dec to Galactic coordinates (l, b) in degrees."""
    ra_rad = math.radians(ra_deg)
    dec_rad = math.radians(dec_deg)
    ra_gp = math.radians(192.85948)
    dec_gp = math.radians(27.12825)
    l_omega = math.radians(32.93192)

    sin_b = math.sin(dec_rad) * math.sin(dec_gp) + math.cos(dec_rad) * math.cos(dec_gp) * math.cos(ra_rad - ra_gp)
    b_rad = math.asin(max(-1.0, min(1.0, sin_b)))
    cos_b = math.cos(b_rad)

    if abs(cos_b) < 1e-7:
        l_rad = 0.0
    else:
        y = math.cos(dec_rad) * math.sin(ra_rad - ra_gp)
        x = math.sin(dec_rad) * math.cos(dec_gp) - math.cos(dec_rad) * math.sin(dec_gp) * math.cos(ra_rad - ra_gp)
        l_rad = (math.atan2(y, x) + l_omega) % (2.0 * math.pi)

    return math.degrees(l_rad), math.degrees(b_rad)


def radec_to_ecliptic(ra_deg: float, dec_deg: float) -> Tuple[float, float]:
    """Converts J2000 RA/Dec to Ecliptic coordinates (lambda, beta) in degrees."""
    eps = math.radians(23.4392911)
    alpha = math.radians(ra_deg)
    delta = math.radians(dec_deg)
    sin_beta = math.sin(delta) * math.cos(eps) - math.cos(delta) * math.sin(eps) * math.sin(alpha)
    beta = math.asin(max(-1.0, min(1.0, sin_beta)))
    y = math.sin(delta) * math.sin(eps) + math.cos(delta) * math.cos(eps) * math.sin(alpha)
    x = math.cos(delta) * math.cos(alpha)
    lam = math.atan2(y, x) % (2.0 * math.pi)
    return math.degrees(lam), math.degrees(beta)


def calculate_parallactic_angle(ha_hours: float, dec_deg: float, lat_deg: float) -> float:
    """Calculates parallactic angle q in degrees."""
    ha_rad = math.radians(ha_hours * 15.0)
    dec_rad = math.radians(dec_deg)
    lat_rad = math.radians(lat_deg)
    y = math.sin(ha_rad)
    x = math.tan(lat_rad) * math.cos(dec_rad) - math.sin(dec_rad) * math.cos(ha_rad)
    if abs(x) < 1e-9 and abs(y) < 1e-9:
        return 0.0
    return math.degrees(math.atan2(y, x))


def calculate_ephemeris(ra_deg: float, dec_deg: float, lat_deg: float) -> Tuple[str, str, str]:
    """Calculates approximate Rise, Transit, and Set LST times."""
    phi = math.radians(lat_deg)
    delta = math.radians(dec_deg)
    h0 = math.radians(-0.5667)

    denom = math.cos(phi) * math.cos(delta)
    if abs(denom) < 1e-9:
        return "--:--", "--:--", "--:--"
    cos_H0 = (math.sin(h0) - math.sin(phi) * math.sin(delta)) / denom

    if cos_H0 < -1.0:
        return "Circumpolar", "Visible", "Never Sets"
    elif cos_H0 > 1.0:
        return "Never Rises", "Below Horizon", "Never Rises"

    H0_deg = math.degrees(math.acos(cos_H0))

    def fmt_lst(lst_val: float) -> str:
        h = (lst_val % 360.0) / 15.0
        hh = int(h)
        mm = int((h - hh) * 60)
        return f"{hh:02d}h {mm:02d}m"

    transit = fmt_lst(ra_deg)
    rise = fmt_lst(ra_deg - H0_deg)
    setting = fmt_lst(ra_deg + H0_deg)
    return rise, transit, setting


def get_constellation(ra_deg: float, dec_deg: float) -> str:
    """IAU constellation designation lookup."""
    ra_h = (ra_deg % 360.0) / 15.0
    d = dec_deg

    if d > 60:
        if 0 <= ra_h < 4: return "Cas (Cassiopeia)"
        if 4 <= ra_h < 8: return "Cam (Camelopardalis)"
        if 8 <= ra_h < 15: return "UMa (Ursa Major)"
        if 15 <= ra_h < 18: return "Dra (Draco)"
        if 18 <= ra_h < 24: return "Cep (Cepheus)"
        return "UMi (Ursa Minor)"
    elif d < -50:
        if 0 <= ra_h < 3: return "Hyi (Hydrus)"
        if 3 <= ra_h < 6: return "Dor (Dorado)"
        if 6 <= ra_h < 12: return "Car (Carina)"
        if 12 <= ra_h < 14: return "Cru (Crux)"
        if 14 <= ra_h < 18: return "Cen (Centaurus)"
        if 18 <= ra_h < 22: return "Pav (Pavo)"
        return "Tuc (Tucana)"
    else:
        if -10 <= d <= 30:
            if 0 <= ra_h < 2.5: return "Cet (Cetus)" if d < 10 else "Psc (Pisces)"
            if 2.5 <= ra_h < 4.5: return "Tau (Taurus)" if d > 5 else "Eri (Eridanus)"
            if 4.5 <= ra_h < 6.5: return "Ori (Orion)"
            if 6.5 <= ra_h < 8.5: return "Gem (Gemini)" if d > 10 else "CMi (Canis Minor)"
            if 8.5 <= ra_h < 10: return "Cnc (Cancer)"
            if 10 <= ra_h < 12.5: return "Leo (Leo)"
            if 12.5 <= ra_h < 15.5: return "Vir (Virgo)"
            if 15.5 <= ra_h < 17: return "Lib (Libra)" if d < 0 else "Ser (Serpens)"
            if 17 <= ra_h < 19: return "Oph (Ophiuchus)"
            if 19 <= ra_h < 21: return "Aql (Aquila)"
            if 21 <= ra_h < 23: return "Aqr (Aquarius)"
            return "Peg (Pegasus)"
        elif d > 30:
            if 0 <= ra_h < 3: return "And (Andromeda)"
            if 3 <= ra_h < 5: return "Per (Perseus)"
            if 5 <= ra_h < 7.5: return "Aur (Auriga)"
            if 7.5 <= ra_h < 11: return "Lyn (Lynx)"
            if 11 <= ra_h < 14: return "CVn (Canes Venatici)"
            if 14 <= ra_h < 16.5: return "Boo (Bootes)"
            if 16.5 <= ra_h < 18.5: return "Her (Hercules)"
            if 18.5 <= ra_h < 20.5: return "Lyr (Lyra)"
            if 20.5 <= ra_h < 23: return "Cyg (Cygnus)"
            return "Peg (Pegasus)"
        else:
            if 0 <= ra_h < 3.5: return "Eri (Eridanus)"
            if 3.5 <= ra_h < 6: return "Lep (Lepus)"
            if 6 <= ra_h < 8.5: return "CMa (Canis Major)"
            if 8.5 <= ra_h < 11.5: return "Hya (Hydra)"
            if 11.5 <= ra_h < 14: return "Crv (Corvus)"
            if 14 <= ra_h < 16: return "Lup (Lupus)"
            if 16 <= ra_h < 18: return "Sco (Scorpius)"
            if 18 <= ra_h < 20.5: return "Sgr (Sagittarius)"
            if 20.5 <= ra_h < 22.5: return "Cap (Capricornus)"
            return "PsA (Piscis Austrinus)"
