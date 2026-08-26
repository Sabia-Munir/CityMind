"""
ui.py  —  CityMind Urban Intelligence System
=============================================
Redesigned with:
  • True isometric 3-D projection with depth sorting
  • Four camera rotations  (N / E / S / W view)  via arrow keys or buttons
  • Hand-drawn building sprites for every zone type
  • Smooth animated ambulance & team vehicles driving along road lanes
  • Soft pastel + vivid accent palette — warm sky gradient backdrop
  • Cute floating popups when civilians are rescued
  • Pixel-art trees, lamp-posts, benches scattered on grass tiles
  • Road textures with centre-line dashes and crosswalk stripes
  • Glowing risk-heat overlay blended softly over tiles
  • Animated water ripples for flooded roads
  • Slide-in event toast notifications
"""

import pygame
import sys
import math
import random
from collections import deque

import config
from city_graph import CityGraph
from challenge1_csp import run_layout_planner
from challenge2_mst import build_road_network
from challenge3_ga import place_ambulances
from challenge4_astar import run_emergency_routing
from challenge5_ml import run_risk_pipeline
from helpers import generate_flood_events, pick_civilians, _unblock_random_roads

# ──────────────────────────────────────────────────────────────────────────────
# WINDOW / GRID CONSTANTS
# ──────────────────────────────────────────────────────────────────────────────
WIN_W, WIN_H   = 1400, 860
GRID_N         = 10
PANEL_W        = 280          # right-side panel
CANVAS_W       = WIN_W - PANEL_W

# Isometric tile dimensions
TILE_W         = 88           # width of the diamond
TILE_H         = 44           # height of the diamond (TILE_W / 2)
TILE_DEPTH     = 28           # vertical wall depth

# Centre of the isometric grid in canvas space
ISO_CX         = CANVAS_W // 2
ISO_CY         = 160          # push down so buildings don't clip the header

LOG_H          = 180

SIM = {
    'RISK_REFRESH_EVERY': config.RISK_REFRESH_EVERY,
    'NUM_CIVILIANS':       config.NUM_CIVILIANS,
    'MAX_FLOODS':          config.MAX_FLOODS_PER_STEP,
    'SEED':                config.RANDOM_SEED,
}

# ──────────────────────────────────────────────────────────────────────────────
# COLOUR PALETTE  — soft pastels + vivid pops
# ──────────────────────────────────────────────────────────────────────────────
SKY_TOP   = (180, 210, 255)
SKY_BOT   = (255, 240, 210)

C = {
    # Zone top-face colours (bright, saturated)
    'Residential':     (100, 210, 130),    # sage green
    'Hospital':        (255, 120, 130),    # coral red
    'School':          (255, 205,  80),    # warm amber
    'Industrial':      (180, 190, 200),    # steel grey
    'PowerPlant':      (200, 140, 255),    # soft violet
    'AmbulanceDepot':  ( 90, 180, 255),    # sky blue
    'Empty':           (160, 220, 160),    # pale lawn

    # Iso side-wall shading (darker tones)
    'Residential_S':   ( 55, 145,  80),
    'Hospital_S':      (200,  60,  70),
    'School_S':        (200, 140,  20),
    'Industrial_S':    (110, 120, 130),
    'PowerPlant_S':    (130,  70, 200),
    'AmbulanceDepot_S':(  40, 110, 200),
    'Empty_S':         ( 90, 155,  90),

    # Roads
    'ROAD':            ( 80,  85,  95),    # asphalt
    'ROAD_EDGE':       ( 55,  58,  68),
    'ROAD_LINE':       (255, 240, 160),    # centre dash
    'ROAD_BLK':        (255,  80,  60),    # flooded
    'ROAD_WATER':      ( 80, 160, 230),

    # Overlays / FX
    'PATH':            ( 60, 240, 140),
    'AMB':             (255, 255, 255),
    'AMB_BODY':        (255,  60,  60),
    'AMB_LIGHT':       (255, 230,  60),
    'TEAM_BODY':       ( 60, 140, 255),
    'CIVILIAN':        (255, 180,  60),
    'RISK_H':          (255,  60,  60),
    'RISK_M':          (255, 190,  60),
    'RISK_L':          ( 60, 210,  80),

    # Panel / UI
    'PANEL':           ( 28,  32,  48),
    'PANEL2':          ( 38,  44,  64),
    'PANEL_BD':        ( 70,  80, 120),
    'HDR':             ( 20,  24,  40),
    'TXT':             (240, 244, 255),
    'TXT2':            (150, 160, 190),
    'ACCENT':          ( 90, 200, 255),
    'ACCENT2':         (255, 140, 200),
    'OK':              ( 80, 220, 120),
    'WARN':            (255, 200,  60),
    'ERR':             (255,  80,  80),
    'BTN':             ( 48,  56,  84),
    'BTN_HV':          ( 70,  80, 120),
    'BTN_ACTIVE':      ( 40, 160, 255),
}

# ──────────────────────────────────────────────────────────────────────────────
# ISO PROJECTION HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def iso_proj(row, col, elev=0, rotation=0):
    """
    Convert grid (row, col) to screen (x, y) with camera rotation.
    rotation: 0=North(default), 1=East, 2=South, 3=West
    """
    r, c = row, col
    if rotation == 1:
        r, c = c, GRID_N - 1 - row
    elif rotation == 2:
        r, c = GRID_N - 1 - row, GRID_N - 1 - col
    elif rotation == 3:
        r, c = GRID_N - 1 - col, row

    sx = ISO_CX + (c - r) * (TILE_W // 2)
    sy = ISO_CY + (c + r) * (TILE_H // 2) - elev * TILE_DEPTH
    return sx, sy


def tile_corners(row, col, rotation=0, elev=0):
    """Return the four corners of the top diamond face (top, right, bottom, left)."""
    cx, cy = iso_proj(row, col, elev, rotation)
    return [
        (cx,             cy - TILE_H // 2),
        (cx + TILE_W // 2, cy),
        (cx,             cy + TILE_H // 2),
        (cx - TILE_W // 2, cy),
    ]


def draw_order(rotation=0):
    """Return grid coords in painter's order (back-to-front) for given rotation."""
    coords = [(r, c) for r in range(GRID_N) for c in range(GRID_N)]
    # Sort by projected y of the tile top, then x
    coords.sort(key=lambda rc: iso_proj(rc[0], rc[1], 0, rotation)[1] * 1000
                               + iso_proj(rc[0], rc[1], 0, rotation)[0])
    return coords


# ──────────────────────────────────────────────────────────────────────────────
# DRAWING HELPERS
# ──────────────────────────────────────────────────────────────────────────────
def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def draw_sky(surf):
    """Warm gradient sky for the canvas area."""
    for y in range(WIN_H):
        t = y / WIN_H
        col = lerp_color(SKY_TOP, SKY_BOT, t)
        pygame.draw.line(surf, col, (0, y), (CANVAS_W, y))


def rounded_rect(surf, color, rect, r=8, border=0, border_col=None):
    pygame.draw.rect(surf, color, rect, border_radius=r)
    if border and border_col:
        pygame.draw.rect(surf, border_col, rect, border, border_radius=r)


def draw_text(surf, font, text, color, pos, anchor="topleft"):
    ts = font.render(text, True, color)
    r = ts.get_rect(**{anchor: pos})
    surf.blit(ts, r)
    return r


# ──────────────────────────────────────────────────────────────────────────────
# ISOMETRIC TILE RENDERER  (the "sprite" library)
# ──────────────────────────────────────────────────────────────────────────────
class IsoRenderer:
    """Draws isometric tiles + buildings for each zone type."""

    def __init__(self, screen, fonts):
        self.screen = screen
        self.fonts  = fonts

    # ── base tile (ground diamond + walls) ──────────────────────────────────
    def draw_tile(self, row, col, rotation, zone, elev=1, alpha_surf=None):
        top_col = C.get(zone, C['Empty'])
        sid_col = C.get(zone + '_S', C['Empty_S'])
        corners = tile_corners(row, col, rotation, elev)
        cx, cy  = iso_proj(row, col, elev, rotation)
        base_y  = cy + TILE_H // 2

        # Left wall
        lwall = [
            corners[3],
            corners[2],
            (corners[2][0], corners[2][1] + TILE_DEPTH),
            (corners[3][0], corners[3][1] + TILE_DEPTH),
        ]
        # Right wall
        rwall = [
            corners[2],
            corners[1],
            (corners[1][0], corners[1][1] + TILE_DEPTH),
            (corners[2][0], corners[2][1] + TILE_DEPTH),
        ]
        dark_l = tuple(max(0, v - 30) for v in sid_col)
        pygame.draw.polygon(self.screen, dark_l, lwall)
        pygame.draw.polygon(self.screen, sid_col, rwall)

        # Top face
        pygame.draw.polygon(self.screen, top_col, corners)
        # Subtle outline
        pygame.draw.polygon(self.screen, tuple(max(0, v - 40) for v in top_col),
                            corners, 1)

    # ── road tile (flat, no walls) ───────────────────────────────────────────
    def draw_road_tile(self, row, col, rotation, edges, blocked_edges=None,
                       flood_anim=0):
        blocked_edges = blocked_edges or set()
        corners = tile_corners(row, col, rotation, elev=0)
        cx, cy  = iso_proj(row, col, 0, rotation)

        # Asphalt ground face
        pygame.draw.polygon(self.screen, C['ROAD'], corners)
        pygame.draw.polygon(self.screen, C['ROAD_EDGE'], corners, 1)

        # Thin road-markings along connected neighbours
        for (dr, dc) in edges:
            nr, nc = row + dr, col + dc
            if 0 <= nr < GRID_N and 0 <= nc < GRID_N:
                ncx, ncy = iso_proj(nr, nc, 0, rotation)
                mid = ((cx + ncx) // 2, (cy + ncy) // 2)
                if (dr, dc) in blocked_edges:
                    # Blue water shimmer
                    wc = lerp_color(C['ROAD_WATER'], (200, 230, 255),
                                    abs(math.sin(flood_anim * 0.05 + row + col)))
                    pygame.draw.line(self.screen, wc, (cx, cy), mid, 6)
                else:
                    # Centre dashes
                    dash_col = C['ROAD_LINE']
                    steps = 4
                    for s in range(steps):
                        t0 = s / steps
                        t1 = (s + 0.5) / steps
                        p0 = (int(cx + (mid[0]-cx)*t0), int(cy + (mid[1]-cy)*t0))
                        p1 = (int(cx + (mid[0]-cx)*t1), int(cy + (mid[1]-cy)*t1))
                        pygame.draw.line(self.screen, dash_col, p0, p1, 1)

    # ── building sprites ─────────────────────────────────────────────────────
    def draw_building(self, row, col, rotation, zone, anim=0):
        cx, cy = iso_proj(row, col, 1, rotation)
        elev   = 1

        if zone == 'Hospital':
            self._hospital(cx, cy, anim)
        elif zone == 'School':
            self._school(cx, cy, anim)
        elif zone == 'PowerPlant':
            self._powerplant(cx, cy, anim)
        elif zone == 'AmbulanceDepot':
            self._amb_depot(cx, cy, anim)
        elif zone == 'Industrial':
            self._industrial(cx, cy, anim)
        elif zone == 'Residential':
            self._house(cx, cy, anim)
        elif zone == 'Empty':
            self._park_deco(cx, cy, anim)

    def _house(self, cx, cy, anim):
        # Base box
        bw, bh = 26, 20
        bx, by = cx - bw//2, cy - bh - 6
        pygame.draw.rect(self.screen, (255, 235, 185), (bx, by, bw, bh), border_radius=2)
        pygame.draw.rect(self.screen, (200, 175, 120), (bx, by, bw, bh), 1, border_radius=2)
        # Door
        pygame.draw.rect(self.screen, (140, 100, 60), (cx-4, by+bh-8, 8, 8))
        # Window
        pygame.draw.rect(self.screen, (160, 220, 255), (bx+4, by+4, 7, 6), border_radius=1)
        pygame.draw.rect(self.screen, (bx+4, by+4, 7, 6), (140, 170, 200), 1)
        # Roof (triangle)
        roof = [(cx - bw//2 - 3, by + 2),
                (cx,              by - 12),
                (cx + bw//2 + 3,  by + 2)]
        pygame.draw.polygon(self.screen, (220, 80, 80), roof)
        pygame.draw.polygon(self.screen, (180, 50, 50), roof, 1)
        # Chimney
        pygame.draw.rect(self.screen, (170, 100, 80), (cx + 6, by - 18, 5, 10))
        # Smoke puff
        sc = (220, 220, 220)
        off = int(math.sin(anim * 0.03) * 2)
        pygame.draw.circle(self.screen, sc, (cx + 9, by - 20 + off), 4)

    def _hospital(self, cx, cy, anim):
        bw, bh = 34, 26
        bx, by = cx - bw//2, cy - bh - 4
        pygame.draw.rect(self.screen, (250, 250, 255), (bx, by, bw, bh), border_radius=3)
        pygame.draw.rect(self.screen, (200, 200, 220), (bx, by, bw, bh), 1, border_radius=3)
        # Red cross on facade
        cross_col = (240, 60, 80)
        pygame.draw.rect(self.screen, cross_col, (cx-2, by+4, 4, 14))
        pygame.draw.rect(self.screen, cross_col, (cx-7, by+9, 14, 4))
        # Windows row
        for i in range(3):
            wx = bx + 4 + i*10
            pygame.draw.rect(self.screen, (160, 220, 255), (wx, by+bh-12, 6, 7))
        # Flat roof top accent
        pygame.draw.rect(self.screen, (200, 220, 255), (bx, by, bw, 4), border_radius=3)
        # Pulse ring on red cross
        pulse = int(abs(math.sin(anim * 0.06)) * 5)
        pygame.draw.circle(self.screen, (255, 100, 110), (cx, by+11), 10 + pulse, 1)

    def _school(self, cx, cy, anim):
        bw, bh = 36, 22
        bx, by = cx - bw//2, cy - bh - 4
        pygame.draw.rect(self.screen, (255, 240, 180), (bx, by, bw, bh), border_radius=2)
        pygame.draw.rect(self.screen, (200, 170, 80), (bx, by, bw, bh), 1, border_radius=2)
        # Bell tower
        pygame.draw.rect(self.screen, (240, 200, 100), (cx-4, by-14, 8, 14))
        pygame.draw.polygon(self.screen, (200, 140, 40),
                            [(cx-5, by-14), (cx, by-22), (cx+5, by-14)])
        # Windows
        for i in range(3):
            pygame.draw.rect(self.screen, (160, 220, 255), (bx+4+i*11, by+5, 7, 8))
        # Flag
        flag_col = (60, 140, 255)
        pygame.draw.line(self.screen, (100, 100, 100), (cx+4, by-22), (cx+4, by-14), 1)
        pygame.draw.polygon(self.screen, flag_col,
                            [(cx+4, by-22), (cx+11, by-19), (cx+4, by-16)])

    def _powerplant(self, cx, cy, anim):
        # Cooling tower silhouette
        tw, th = 16, 28
        tx, ty = cx - tw//2, cy - th - 2
        tower_pts = [
            (tx, ty + th),
            (tx + tw, ty + th),
            (tx + tw - 3, ty + 6),
            (tx + tw//2 + 3, ty),
            (tx + tw//2 - 3, ty),
            (tx + 3, ty + 6),
        ]
        pygame.draw.polygon(self.screen, (160, 150, 190), tower_pts)
        pygame.draw.polygon(self.screen, (110, 100, 140), tower_pts, 1)
        # Steam
        for i in range(3):
            off_x = int(math.sin(anim * 0.04 + i * 1.2) * 3)
            alpha = max(60, 220 - anim % 60 * 3)
            sc = (240, 240, 255)
            pygame.draw.circle(self.screen, sc, (cx - 4 + i*4 + off_x, ty - 4 - i*3), 3 + i)
        # Energy bolt
        bolt = (255, 230, 60)
        bx2, by2 = cx - 4, cy - 10
        pygame.draw.polygon(self.screen, bolt,
                            [(bx2, by2), (bx2+5, by2-5), (bx2+2, by2-5),
                             (bx2+8, by2-14), (bx2+1, by2-8), (bx2+4, by2-8)])

    def _amb_depot(self, cx, cy, anim):
        bw, bh = 38, 20
        bx, by = cx - bw//2, cy - bh - 2
        pygame.draw.rect(self.screen, (210, 235, 255), (bx, by, bw, bh), border_radius=3)
        pygame.draw.rect(self.screen, (90, 160, 230), (bx, by, bw, bh), 2, border_radius=3)
        # Large door arch
        pygame.draw.arc(self.screen, (140, 180, 220),
                        pygame.Rect(cx-9, by+bh-16, 18, 16), 0, math.pi, 3)
        pygame.draw.rect(self.screen, (100, 140, 190), (cx-9, by+bh-8, 18, 8))
        # Ambulance cross sign
        cross_col = (255, 80, 100)
        pygame.draw.rect(self.screen, cross_col, (bx+4, by+3, 3, 9))
        pygame.draw.rect(self.screen, cross_col, (bx+1, by+6, 9, 3))
        # Roof stripe
        pygame.draw.rect(self.screen, (60, 140, 220), (bx, by, bw, 4), border_radius=3)
        # Rotating beacon
        angle = anim * 0.08
        bx2 = int(cx + math.cos(angle) * 5)
        by2 = int(by - 3 + math.sin(angle) * 2)
        pygame.draw.circle(self.screen, (255, 200, 60), (bx2, by2), 3)

    def _industrial(self, cx, cy, anim):
        bw, bh = 30, 18
        bx, by = cx - bw//2, cy - bh - 2
        pygame.draw.rect(self.screen, (180, 190, 200), (bx, by, bw, bh), border_radius=1)
        pygame.draw.rect(self.screen, (130, 140, 150), (bx, by, bw, bh), 1)
        # Chimney stacks
        for i in range(2):
            chx = bx + 4 + i*14
            pygame.draw.rect(self.screen, (140, 140, 150), (chx, by-14, 7, 14))
            sc = (220, 210, 220)
            off = int(math.sin(anim * 0.03 + i) * 2)
            pygame.draw.circle(self.screen, sc, (chx+3, by-15+off), 4)
        # Corrugated roof detail
        for i in range(5):
            lx = bx + i * 6
            pygame.draw.arc(self.screen, (160, 170, 180),
                            pygame.Rect(lx, by-2, 7, 6), 0, math.pi, 1)

    def _park_deco(self, cx, cy, anim):
        # Small tree
        sway = int(math.sin(anim * 0.02) * 1)
        pygame.draw.line(self.screen, (120, 90, 60),
                         (cx, cy - 4), (cx + sway, cy - 16), 2)
        pygame.draw.circle(self.screen, (80, 180, 80), (cx + sway, cy - 18), 7)
        pygame.draw.circle(self.screen, (60, 160, 60), (cx + sway - 2, cy - 20), 5)
        # Bench
        pygame.draw.rect(self.screen, (160, 120, 80),
                         (cx + 6, cy - 8, 10, 3), border_radius=1)
        pygame.draw.line(self.screen, (140, 100, 60), (cx+7, cy-8), (cx+7, cy-4), 1)
        pygame.draw.line(self.screen, (140, 100, 60), (cx+14, cy-8), (cx+14, cy-4), 1)

    # ── vehicle sprites ──────────────────────────────────────────────────────
    def draw_ambulance(self, screen_x, screen_y, anim):
        """Small top-down-ish ambulance sprite in isometric perspective."""
        ax, ay = int(screen_x), int(screen_y)
        # Body
        body = pygame.Rect(ax-9, ay-6, 18, 12)
        pygame.draw.rect(self.screen, C['AMB_BODY'], body, border_radius=3)
        pygame.draw.rect(self.screen, (200, 40, 40), body, 1, border_radius=3)
        # White cross
        pygame.draw.rect(self.screen, (255,255,255), (ax-2, ay-5, 4, 8))
        pygame.draw.rect(self.screen, (255,255,255), (ax-5, ay-2, 10, 3))
        # Wheels
        wc = (40, 40, 40)
        for wx, wy in [(-7, -4), (5, -4), (-7, 4), (5, 4)]:
            pygame.draw.ellipse(self.screen, wc, (ax+wx, ay+wy, 5, 3))
        # Beacon flash
        bc = (255, 240, 60) if (anim // 8) % 2 == 0 else (255, 120, 120)
        pygame.draw.circle(self.screen, bc, (ax, ay-8), 4)
        pygame.draw.circle(self.screen, (255, 255, 255), (ax, ay-8), 2)

    def draw_team_vehicle(self, screen_x, screen_y, anim):
        """Medical team SUV."""
        ax, ay = int(screen_x), int(screen_y)
        body = pygame.Rect(ax-10, ay-6, 20, 12)
        pygame.draw.rect(self.screen, (60, 120, 255), body, border_radius=3)
        pygame.draw.rect(self.screen, (30, 80, 200), body, 1, border_radius=3)
        # Windshield
        pygame.draw.rect(self.screen, (180, 220, 255), (ax-6, ay-5, 12, 5), border_radius=1)
        # Wheels
        for wx, wy in [(-8, -4), (5, -4), (-8, 4), (5, 4)]:
            pygame.draw.ellipse(self.screen, (30, 30, 30), (ax+wx, ay+wy, 5, 3))
        # Top siren
        sc = (255, 200, 60) if (anim // 6) % 2 == 0 else (60, 200, 255)
        pygame.draw.rect(self.screen, sc, (ax-4, ay-10, 8, 4), border_radius=2)

    def draw_civilian_marker(self, screen_x, screen_y, anim):
        """Cute waving person marker."""
        ax, ay = int(screen_x), int(screen_y)
        bob = int(math.sin(anim * 0.1) * 3)
        ay += bob
        # SOS bubble
        bubble_r = pygame.Rect(ax-14, ay-34, 28, 18)
        pygame.draw.rect(self.screen, (255, 240, 80), bubble_r, border_radius=8)
        pygame.draw.rect(self.screen, (200, 160, 0), bubble_r, 1, border_radius=8)
        # Tail
        pts = [(ax-3, ay-16), (ax+3, ay-16), (ax, ay-10)]
        pygame.draw.polygon(self.screen, (255, 240, 80), pts)
        # SOS text
        f = pygame.font.SysFont("consolas", 8, bold=True)
        ts = f.render("SOS", True, (180, 60, 0))
        self.screen.blit(ts, (ax-10, ay-31))
        # Body
        body_col = (255, 180, 100)
        pygame.draw.circle(self.screen, body_col, (ax, ay-6), 5)
        pygame.draw.rect(self.screen, body_col, (ax-4, ay-2, 8, 8), border_radius=2)


# ──────────────────────────────────────────────────────────────────────────────
# TOAST NOTIFICATION
# ──────────────────────────────────────────────────────────────────────────────
class Toast:
    def __init__(self, msg, color, duration=120):
        self.msg      = msg
        self.color    = color
        self.ttl      = duration
        self.max_ttl  = duration

    def draw(self, surf, font, x, y):
        alpha  = min(255, int(255 * self.ttl / max(1, self.max_ttl)))
        ts     = font.render(self.msg, True, self.color)
        bg     = pygame.Surface((ts.get_width() + 20, ts.get_height() + 10), pygame.SRCALPHA)
        bg.fill((20, 24, 40, min(220, alpha)))
        surf.blit(bg, (x - ts.get_width()//2 - 10, y - 2))
        ts.set_alpha(alpha)
        surf.blit(ts, (x - ts.get_width()//2, y + 2))
        self.ttl -= 1
        return self.ttl > 0


# ──────────────────────────────────────────────────────────────────────────────
# SCROLLABLE LOG
# ──────────────────────────────────────────────────────────────────────────────
class Log:
    def __init__(self, x, y, w, h, font):
        self.rect  = pygame.Rect(x, y, w, h)
        self.font  = font
        self.lines = []
        self.lh    = 16
        self.vis   = (h - 30) // self.lh
        self.off   = 0

    def add(self, msg):
        self.lines.append(msg)
        if len(self.lines) > 500:
            self.lines.pop(0)
        self.off = max(0, len(self.lines) - self.vis)

    def draw(self, surf):
        rounded_rect(surf, C['PANEL'], self.rect, 8, 1, C['PANEL_BD'])
        draw_text(surf, self.font, "▸ EVENT LOG", C['ACCENT'], (self.rect.x+10, self.rect.y+6))
        pygame.draw.line(surf, C['PANEL_BD'],
                         (self.rect.x+6, self.rect.y+24),
                         (self.rect.right-6, self.rect.y+24), 1)
        end = min(len(self.lines), self.off + self.vis)
        for i, idx in enumerate(range(self.off, end)):
            ln  = self.lines[idx]
            col = C['TXT2']
            if 'FLOOD' in ln or 'blocked' in ln: col = C['WARN']
            elif '[A*]' in ln or 'dispatched' in ln: col = C['ACCENT']
            elif 'rescued' in ln or 'complete' in ln: col = C['OK']
            elif 'ERROR' in ln or 'FAIL' in ln: col = C['ERR']
            elif '[ML]' in ln or '[GA]' in ln: col = C['ACCENT2']
            if len(ln) > 100: ln = ln[:97] + '...'
            surf.blit(self.font.render(ln, True, col),
                      (self.rect.x+10, self.rect.y+28+i*self.lh))

    def scroll(self, dy):
        self.off = max(0, min(len(self.lines)-self.vis, self.off+dy))


# ──────────────────────────────────────────────────────────────────────────────
# BUTTON
# ──────────────────────────────────────────────────────────────────────────────
class Btn:
    def __init__(self, x, y, w, h, label, font, active_flag=None, icon=''):
        self.rect        = pygame.Rect(x, y, w, h)
        self.label       = label
        self.font        = font
        self.active_flag = active_flag  # if not None, draws as toggle
        self.icon        = icon
        self.hov         = False

    def draw(self, surf, active=None):
        is_on = active if active is not None else False
        col   = C['BTN_ACTIVE'] if is_on else (C['BTN_HV'] if self.hov else C['BTN'])
        rounded_rect(surf, col, self.rect, 8, 1, C['PANEL_BD'])
        txt = f"{self.icon}  {self.label}" if self.icon else self.label
        draw_text(surf, self.font, txt, C['TXT'], self.rect.center, anchor='center')

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hov = self.rect.collidepoint(ev.pos)
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.hov:
            return True
        return False


# ──────────────────────────────────────────────────────────────────────────────
# MAIN UI CLASS
# ──────────────────────────────────────────────────────────────────────────────
class CityMindUI:

    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H),
                                              pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("CityMind — Urban Intelligence System")
        self.clock = pygame.time.Clock()

        # fonts
        self.f_sm  = pygame.font.SysFont("segoeui",  12)
        self.f_md  = pygame.font.SysFont("segoeui",  15)
        self.f_lg  = pygame.font.SysFont("segoeui",  19, bold=True)
        self.f_ti  = pygame.font.SysFont("segoeui",  28, bold=True)
        self.f_mono= pygame.font.SysFont("consolas", 12)

        self.renderer = IsoRenderer(self.screen, {})
        self.sky_surf = None   # cached sky

        # state
        self.city        = None
        self.running     = False
        self.paused      = False
        self.step        = 0
        self.civilians   = []
        self.team_pos    = None
        self.cur_path    = []
        self.rng         = random.Random(SIM['SEED'])
        self.stats       = {'vis':0,'unr':0,'rer':0,'cost':0.0,'fld':0}
        self.narration   = "Press PLAY or SPACE to start the simulation."
        self.anim        = 0
        self.last_step_t = 0
        self.rotation    = 0    # 0=N 1=E 2=S 3=W
        self.zoom        = 1.0  # future expansion

        # ambulance animation
        self.is_animating       = False
        self.anim_path          = []
        self.anim_idx           = 0
        self.anim_pixel_pos     = None
        self.anim_speed         = 2.5
        self.pending_step_res   = None
        self.pending_flood_txt  = ""

        # stationary ambulances lerp-target positions (smooth repositioning)
        self.amb_pixel_positions = {}

        # overlays
        self.show_roads   = True
        self.show_risk    = False
        self.show_amb     = True
        self.show_cov     = False

        # toasts
        self.toasts = []

        # sky cache
        self._build_sky()

        # panel layout
        px  = CANVAS_W + 10
        pw  = PANEL_W - 20
        self.log = Log(0, WIN_H - LOG_H - 4, CANVAS_W, LOG_H, self.f_mono)

        y = 70
        def btn(lbl, icon=''):
            nonlocal y
            b = Btn(px, y, pw, 32, lbl, self.f_md, icon=icon)
            y += 38
            return b

        self.b_play   = btn("PLAY",  "▶")
        self.b_pause  = btn("PAUSE", "⏸")
        self.b_step   = btn("STEP",  "⏭")
        self.b_reset  = btn("RESET", "↺")
        y += 10
        self.b_rotL   = btn("Rotate ◀", "")
        self.b_rotR   = btn("Rotate ▶", "")
        y += 10
        self.b_roads  = btn("Roads",  "🛣")
        self.b_risk   = btn("Risk Map","⚠")
        self.b_amb    = btn("Ambulances","🚑")
        self.b_cov    = btn("Coverage", "◉")

        self.buttons = [self.b_play, self.b_pause, self.b_step, self.b_reset,
                        self.b_rotL, self.b_rotR,
                        self.b_roads, self.b_risk, self.b_amb, self.b_cov]

        self._init_city()

    # ─────────────────────────────────────────────────────────────────────────
    def _build_sky(self):
        self.sky_surf = pygame.Surface((CANVAS_W, WIN_H - LOG_H))
        for yy in range(WIN_H - LOG_H):
            t = yy / (WIN_H - LOG_H)
            col = lerp_color(SKY_TOP, SKY_BOT, t)
            pygame.draw.line(self.sky_surf, col, (0, yy), (CANVAS_W, yy))

    # ─────────────────────────────────────────────────────────────────────────
    def _init_city(self):
        random.seed(SIM['SEED'])
        self.city    = CityGraph(rows=GRID_N, cols=GRID_N)
        self.rng     = random.Random(SIM['SEED'])
        self.cur_path = []
        self.log.add("[SYS] Initialising CityMind...")

        p = run_layout_planner(self.city)
        if not p: self.log.add("[ERR] CSP layout failed!"); return
        self.log.add("[CH1] City layout complete")

        rd = build_road_network(self.city)
        if not rd: self.log.add("[ERR] Road network failed!"); return
        self.log.add(f"[CH2] {len(rd['mst_edges'])} roads | cost {rd['total_cost']:.1f}")

        ml = run_risk_pipeline(self.city)
        if ml: self.log.add(f"[CH5] Risk model ready | accuracy {ml['cv_accuracy']:.2f}")

        pos = place_ambulances(self.city)
        if pos:
            self.city.ambulance_positions = pos
            self.log.add(f"[CH3] {len(pos)} ambulances deployed")
            self.amb_pixel_positions = {
                p: iso_proj(p[0], p[1], 0, self.rotation)
                for p in pos
            }

        self.civilians = pick_civilians(self.city, SIM['NUM_CIVILIANS'], self.rng)
        self.team_pos  = self.city.primary_depot
        self.log.add("[SYS] Ready — Press PLAY or SPACE")
        self.toasts.append(Toast("CityMind ready! Press PLAY", C['OK']))

    # ─────────────────────────────────────────────────────────────────────────
    def _do_step(self):
        if self.step >= 20:
            self.log.add("[SIM] Simulation complete — 20 steps done.")
            self.running = False; return
        if self.is_animating: return

        self.step += 1
        self.city.set_simulation_step(self.step)

        flooded    = generate_flood_events(self.city, self.rng)
        flood_txt  = ""
        if flooded:
            self.stats['fld'] += len(flooded)
            flood_txt = f"{len(flooded)} road(s) flooded"
            for a, b in flooded:
                self.log.add(
                    f"[FLD] ⚠ {self.city.get_label(a)} ↔ {self.city.get_label(b)} blocked")
            self.toasts.append(Toast(f"⚠ {len(flooded)} road(s) flooded!", C['WARN']))
        else:
            flood_txt = "no floods"

        self.civilians = pick_civilians(self.city, SIM['NUM_CIVILIANS'], self.rng)
        self.cur_path  = []
        res            = None

        if self.civilians and self.team_pos:
            res = run_emergency_routing(
                city=self.city,
                civilian_nodes=self.civilians,
                start_node=self.team_pos,
                flood_schedule=list(flooded) if flooded else [])

            if res and res.get('full_path'):
                self.pending_step_res  = res
                self.pending_flood_txt = flood_txt
                self.anim_path  = res['full_path']
                self.anim_idx   = 0
                self.cur_path   = self.anim_path
                self.is_animating = True
                self.anim_pixel_pos = iso_proj(
                    self.team_pos[0], self.team_pos[1], 0, self.rotation)
                self.log.add(
                    f"[SIM] 🚑 Team dispatched → {len(res['visited'])} civilian(s)")
                return

        self._finish_step(res, flood_txt)

    def _finish_step(self, res, flood_txt):
        if res:
            self.stats['vis']  += len(res.get('visited', []))
            self.stats['unr']  += len(res.get('unreachable', []))
            self.stats['rer']  += res.get('reroutes', 0)
            self.stats['cost'] += res.get('total_cost', 0.0)
            if res['visited']:
                self.team_pos = res['visited'][-1]
                self.toasts.append(
                    Toast(f"✓ {len(res['visited'])} civilian(s) rescued!", C['OK']))
            elif res.get('full_path'):
                self.team_pos = res['full_path'][-1]
            vis_n = len(res['visited'])
            unr_n = len(res['unreachable'])
            self.narration = (
                f"Step {self.step}  |  {flood_txt}  |  "
                f"Rescued {vis_n}  |  Unreachable {unr_n}  |  "
                f"Cost {res['total_cost']:.1f}")
            self.log.add(
                f"[A*] vis={vis_n} unr={unr_n} cost={res['total_cost']:.1f}")

        if self.step % SIM['RISK_REFRESH_EVERY'] == 0:
            ml = run_risk_pipeline(self.city)
            if ml: self.log.add(f"[ML] Risk refreshed | acc {ml['cv_accuracy']:.2f}")
            np_ = place_ambulances(self.city,
                                   seed_chromosome=list(self.city.ambulance_positions))
            if np_:
                self.city.ambulance_positions = np_
                self.log.add("[GA] Ambulances repositioned")

        if self.step % 3 == 0:
            ub = _unblock_random_roads(self.city, self.rng, max_unblocks=2)
            if ub: self.log.add(f"[REC] {ub} road(s) cleared")

    # ─────────────────────────────────────────────────────────────────────────
    # DRAWING
    # ─────────────────────────────────────────────────────────────────────────
    def _draw_canvas(self):
        # sky
        self.screen.blit(self.sky_surf, (0, 50))

        order = draw_order(self.rotation)

        # Collect road edge data once
        edge_map = {}  # (row,col) -> list of (dr, dc)
        blocked  = set()
        if self.show_roads:
            for a, b, data in self.city.get_all_edges():
                ar, ac = a; br, bc = b
                if data.get('blocked', False):
                    blocked.add((a, b)); blocked.add((b, a))
                edge_map.setdefault(a, []).append((br-ar, bc-ac))
                edge_map.setdefault(b, []).append((ar-br, ac-bc))

        # Build set of road tiles (both endpoints of every edge)
        road_tiles = set()
        if self.show_roads:
            for a, b, _ in self.city.get_all_edges():
                road_tiles.add(a); road_tiles.add(b)

        # Risk overlay surface
        risk_ovl = None
        if self.show_risk:
            risk_ovl = pygame.Surface((CANVAS_W, WIN_H), pygame.SRCALPHA)

        # Coverage overlay
        cov_set = set()
        if self.show_cov and self.city.ambulance_positions:
            for amb in self.city.ambulance_positions:
                q = deque([(amb, 0)]); vis = {amb}
                while q:
                    cur, d = q.popleft(); cov_set.add(cur)
                    if d < 3:
                        for nb, co in self.city.get_open_neighbors_with_cost(cur):
                            if nb not in vis and co < float('inf'):
                                vis.add(nb); q.append((nb, d+1))

        # ── draw tiles back-to-front ──────────────────────────────────────
        for (r, c) in order:
            node  = self.city.get_node((r, c))
            zone  = node.get('location_type', 'Empty')
            is_road = (r, c) in road_tiles

            if is_road and self.show_roads:
                edges      = edge_map.get((r, c), [])
                blk_edges  = set()
                for (dr, dc) in edges:
                    nb = (r+dr, c+dc)
                    if ((r,c), nb) in blocked or (nb,(r,c)) in blocked:
                        blk_edges.add((dr, dc))
                self.renderer.draw_road_tile(r, c, self.rotation,
                                             edges, blk_edges, self.anim)
            else:
                elev = 1
                if zone in ('Hospital', 'PowerPlant', 'AmbulanceDepot'):
                    elev = 2
                elif zone == 'Industrial':
                    elev = 1
                self.renderer.draw_tile(r, c, self.rotation, zone, elev)
                self.renderer.draw_building(r, c, self.rotation, zone, self.anim)

            # risk overlay
            if self.show_risk and risk_ovl:
                risk = node.get('risk_index', 0)
                if risk >= 0.65:
                    col = (*C['RISK_H'], 110)
                elif risk >= 0.35:
                    col = (*C['RISK_M'], 80)
                else:
                    col = (*C['RISK_L'], 40)
                corners = tile_corners(r, c, self.rotation, 0)
                pygame.draw.polygon(risk_ovl, col, corners)

            # coverage overlay
            if self.show_cov and (r, c) in cov_set:
                corners = tile_corners(r, c, self.rotation, 0)
                ovl2 = pygame.Surface((CANVAS_W, WIN_H), pygame.SRCALPHA)
                pygame.draw.polygon(ovl2, (*C['OK'], 45), corners)
                self.screen.blit(ovl2, (0, 0))

        if risk_ovl:
            self.screen.blit(risk_ovl, (0, 0))

        # ── A* path ────────────────────────────────────────────────────────
        if self.cur_path and len(self.cur_path) > 1:
            for i in range(len(self.cur_path)-1):
                ax, ay = iso_proj(*self.cur_path[i],   0, self.rotation)
                bx, by = iso_proj(*self.cur_path[i+1], 0, self.rotation)
                pulse  = int(abs(math.sin(self.anim*0.06 + i*0.3)) * 3)
                pygame.draw.line(self.screen, C['PATH'], (ax,ay), (bx,by), 4+pulse)
                pygame.draw.circle(self.screen, C['PATH'], (bx,by), 3)

        # ── civilian markers ──────────────────────────────────────────────
        for civ in self.civilians:
            sx, sy = iso_proj(civ[0], civ[1], 1, self.rotation)
            self.renderer.draw_civilian_marker(sx, sy, self.anim)

        # ── stationary ambulances ─────────────────────────────────────────
        if self.show_amb and self.city.ambulance_positions:
            for pos in self.city.ambulance_positions:
                tx, ty = iso_proj(pos[0], pos[1], 0, self.rotation)
                # lerp to new position smoothly
                cur = self.amb_pixel_positions.get(pos, (tx, ty))
                lx  = cur[0] + (tx - cur[0]) * 0.15
                ly  = cur[1] + (ty - cur[1]) * 0.15
                self.amb_pixel_positions[pos] = (lx, ly)
                self.renderer.draw_ambulance(lx, ly, self.anim)

        # ── animated team vehicle ─────────────────────────────────────────
        if self.team_pos:
            if self.is_animating and self.anim_pixel_pos:
                vx, vy = self.anim_pixel_pos
            else:
                vx, vy = iso_proj(self.team_pos[0], self.team_pos[1], 0, self.rotation)
            self.renderer.draw_team_vehicle(vx, vy, self.anim)

        # ── toasts ────────────────────────────────────────────────────────
        ty_off = 80
        self.toasts = [t for t in self.toasts
                       if t.draw(self.screen, self.f_md, CANVAS_W//2, ty_off + 32*self.toasts.index(t))]

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_header(self):
        pygame.draw.rect(self.screen, C['HDR'], (0, 0, WIN_W, 50))
        draw_text(self.screen, self.f_ti, "CITYMIND", C['ACCENT'], (18, 10))
        draw_text(self.screen, self.f_sm, "Urban Intelligence System",
                  C['TXT2'], (22, 36))
        view_lbl = ["North", "East", "South", "West"][self.rotation]
        draw_text(self.screen, self.f_md, f"View: {view_lbl}", C['TXT2'],
                  (CANVAS_W - 120, 15))
        if self.running and not self.paused:
            st, sc = "● RUNNING", C['OK']
        elif self.paused:
            st, sc = "⏸ PAUSED",  C['WARN']
        else:
            st, sc = "○ READY",   C['TXT2']
        draw_text(self.screen, self.f_lg, st, sc, (WIN_W - 20, 15), anchor='topright')
        pygame.draw.line(self.screen, C['PANEL_BD'], (0, 50), (WIN_W, 50), 1)

    # ─────────────────────────────────────────────────────────────────────────
    def _draw_panel(self):
        px = CANVAS_W
        pygame.draw.rect(self.screen, C['PANEL'],
                         (px, 0, PANEL_W, WIN_H))
        pygame.draw.line(self.screen, C['PANEL_BD'],
                         (px, 50), (px, WIN_H), 1)
        draw_text(self.screen, self.f_lg, "CONTROLS", C['ACCENT'], (px+10, 56))

        for b in self.buttons:
            active = None
            if b is self.b_roads: active = self.show_roads
            elif b is self.b_risk: active = self.show_risk
            elif b is self.b_amb:  active = self.show_amb
            elif b is self.b_cov:  active = self.show_cov
            b.draw(self.screen, active)

        # Step progress bar
        bx = CANVAS_W + 10
        bw = PANEL_W - 20
        bar_y = self.b_cov.rect.bottom + 14
        draw_text(self.screen, self.f_md,
                  f"Step  {self.step:02d} / 20", C['TXT'],
                  (bx, bar_y))
        bar_y += 22
        pygame.draw.rect(self.screen, C['BTN'], (bx, bar_y, bw, 8), border_radius=4)
        prog_w = int(bw * self.step / 20)
        if prog_w > 0:
            pygame.draw.rect(self.screen, C['ACCENT'], (bx, bar_y, prog_w, 8), border_radius=4)
        bar_y += 18

        # Stats
        sy = bar_y + 4
        for label, key, fmt in [
            ("Rescued",     'vis',  'd'),
            ("Unreachable", 'unr',  'd'),
            ("Reroutes",    'rer',  'd'),
            ("Cost",        'cost', '.1f'),
            ("Floods",      'fld',  'd'),
        ]:
            v = self.stats[key]
            draw_text(self.screen, self.f_md,
                      f"{label}:  {v:{fmt}}", C['TXT2'], (bx+2, sy))
            sy += 20

        # Legend
        ly = WIN_H - LOG_H - 200
        draw_text(self.screen, self.f_lg, "LEGEND", C['ACCENT'], (bx, ly))
        ly += 22
        items = [
            ('Residential',    'Sage green'),
            ('Hospital',       'Coral red'),
            ('School',         'Amber'),
            ('Industrial',     'Steel'),
            ('PowerPlant',     'Violet'),
            ('AmbulanceDepot', 'Sky blue'),
        ]
        for zone, name in items:
            col = C.get(zone, (100,100,100))
            pygame.draw.rect(self.screen, col, (bx, ly, 13, 13), border_radius=3)
            draw_text(self.screen, self.f_sm, name, C['TXT2'], (bx+18, ly))
            ly += 17

        # Narration strip just above log
        nr_rect = pygame.Rect(0, WIN_H - LOG_H - 26, CANVAS_W, 26)
        pygame.draw.rect(self.screen, (18, 22, 36), nr_rect)
        draw_text(self.screen, self.f_mono,
                  self.narration[:130], C['ACCENT'], (8, WIN_H - LOG_H - 22))

    # ─────────────────────────────────────────────────────────────────────────
    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q): return False
                if ev.key == pygame.K_SPACE:
                    if not self.running:
                        self.running = True; self.paused = False
                        self.log.add("[SIM] Simulation started")
                    else:
                        self.paused = not self.paused
                if ev.key == pygame.K_s and not self.is_animating: self._do_step()
                if ev.key == pygame.K_r: self._reset()
                if ev.key == pygame.K_LEFT:  self._rotate(-1)
                if ev.key == pygame.K_RIGHT: self._rotate(1)
                if ev.key == pygame.K_1: self.show_roads = not self.show_roads
                if ev.key == pygame.K_2: self.show_risk  = not self.show_risk
                if ev.key == pygame.K_3: self.show_amb   = not self.show_amb
                if ev.key == pygame.K_4: self.show_cov   = not self.show_cov
                if ev.key == pygame.K_UP:   self.log.scroll(-3)
                if ev.key == pygame.K_DOWN: self.log.scroll(3)
            if ev.type == pygame.MOUSEWHEEL: self.log.scroll(-ev.y * 3)

            for b in self.buttons: b.handle(ev)

            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if self.b_play.hov:
                    self.running = True; self.paused = False
                    self.log.add("[SIM] Simulation started")
                if self.b_pause.hov: self.paused = not self.paused
                if self.b_step.hov and not self.is_animating: self._do_step()
                if self.b_reset.hov: self._reset()
                if self.b_rotL.hov:  self._rotate(-1)
                if self.b_rotR.hov:  self._rotate(1)
                if self.b_roads.hov: self.show_roads = not self.show_roads
                if self.b_risk.hov:  self.show_risk  = not self.show_risk
                if self.b_amb.hov:   self.show_amb   = not self.show_amb
                if self.b_cov.hov:   self.show_cov   = not self.show_cov

        return True

    def _rotate(self, d):
        self.rotation = (self.rotation + d) % 4
        # Invalidate anim_pixel_pos so team vehicle snaps correctly
        if self.team_pos and not self.is_animating:
            pass  # will be recalculated in draw

    def _reset(self):
        self.running       = False
        self.paused        = False
        self.step          = 0
        self.stats         = {'vis':0,'unr':0,'rer':0,'cost':0.0,'fld':0}
        self.cur_path      = []
        self.is_animating  = False
        self.toasts        = []
        self.log.lines.clear()
        self._init_city()

    # ─────────────────────────────────────────────────────────────────────────
    def run(self):
        alive = True
        while alive:
            alive = self._events()
            self.anim += 1

            # Animation tick — smooth vehicle movement
            if self.is_animating and self.anim_path:
                if self.anim_idx < len(self.anim_path) - 1:
                    target    = self.anim_path[self.anim_idx + 1]
                    tx, ty    = iso_proj(target[0], target[1], 0, self.rotation)
                    cx, cy    = self.anim_pixel_pos
                    dx, dy    = tx - cx, ty - cy
                    dist      = math.hypot(dx, dy)
                    spd       = self.anim_speed * max(0.5, dist / 30)
                    if dist <= spd:
                        self.anim_pixel_pos = (tx, ty)
                        self.anim_idx      += 1
                        self.team_pos       = self.anim_path[self.anim_idx]
                        if self.team_pos in self.civilians:
                            self.civilians.remove(self.team_pos)
                            self.toasts.append(Toast("✓ Rescued!", C['OK'], 80))
                    else:
                        self.anim_pixel_pos = (
                            cx + (dx/dist)*spd,
                            cy + (dy/dist)*spd)
                else:
                    self.is_animating = False
                    self._finish_step(self.pending_step_res, self.pending_flood_txt)
            else:
                now = pygame.time.get_ticks()
                if (self.running and not self.paused and self.step < 20
                        and now - self.last_step_t >= 900):
                    self._do_step()
                    self.last_step_t = now

            # DRAW
            self.screen.fill(C['HDR'])
            self._draw_canvas()
            self._draw_header()
            self._draw_panel()
            self.log.draw(self.screen)

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    ui = CityMindUI()
    ui.run()