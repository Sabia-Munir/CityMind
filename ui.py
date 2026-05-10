"""
ui.py - CityMind 2D Top-Down Pygame GUI
========================================
Clean, readable 2D grid with dark theme, toggle overlays,
simulation controls, event log, cell selection, and smooth animations.
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

# =============================================================================
# LAYOUT CONSTANTS
# =============================================================================
WIN_W, WIN_H = 1050, 720
GRID_N = 10
CELL = 35                         # shrank cell pixel size to zoom out more
GRID_PAD_X, GRID_PAD_Y = 40, 65   # grid top-left offset
GRID_PX = CELL * GRID_N            # total grid pixel width
PANEL_X = GRID_PAD_X + GRID_PX + 40  # right panel left edge
PANEL_W = WIN_W - PANEL_X - 20
LOG_H = 160

SIM = {
    'RISK_REFRESH_EVERY': config.RISK_REFRESH_EVERY,
    'NUM_CIVILIANS': config.NUM_CIVILIANS,
    'MAX_FLOODS': config.MAX_FLOODS_PER_STEP,
    'SEED': config.RANDOM_SEED,
}

# =============================================================================
# COLOR PALETTE  (dark theme, vibrant nodes)
# =============================================================================
C = {
    'BG':        (12, 14, 20),
    'GRID_LINE': (30, 34, 45),
    'PANEL':     (18, 22, 32),
    'PANEL_BD':  (44, 50, 66),
    'HDR':       (16, 20, 30),
    # node types
    'Residential':   (34, 197, 94),
    'Hospital':      (239, 68, 68),
    'School':        (250, 176, 5),
    'Industrial':    (148, 163, 184),
    'PowerPlant':    (168, 85, 247),
    'AmbulanceDepot':(59, 130, 246),
    'Empty':         (30, 36, 50),
    # overlays
    'RISK_H': (239, 68, 68),
    'RISK_M': (234, 179, 8),
    'RISK_L': (34, 197, 94),
    'ROAD':   (80, 140, 200),
    'ROAD_BLK': (200, 60, 60),
    'PATH':   (0, 230, 120),
    'AMB':    (255, 255, 255),
    'AMB_GLOW': (239, 68, 68),
    'TEAM':   (255, 220, 40),
    'COV':    (34, 197, 94),
    # text / ui
    'TXT':    (230, 234, 240),
    'TXT2':   (140, 150, 170),
    'ACCENT': (56, 189, 248),
    'OK':     (34, 197, 94),
    'WARN':   (234, 179, 8),
    'ERR':    (239, 68, 68),
    'BTN':    (38, 45, 62),
    'BTN_HV': (56, 189, 248),
}

# =============================================================================
# TINY HELPERS
# =============================================================================
def _rect(r, c):
    """Screen rect for grid cell (row, col)."""
    return pygame.Rect(GRID_PAD_X + c * CELL, GRID_PAD_Y + r * CELL, CELL, CELL)

def _center(r, c):
    rc = _rect(r, c)
    return rc.centerx, rc.centery

# =============================================================================
# BUTTON
# =============================================================================
class Btn:
    def __init__(self, x, y, w, h, label, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.label = label
        self.font = font
        self.hov = False

    def draw(self, surf):
        col = C['BTN_HV'] if self.hov else C['BTN']
        pygame.draw.rect(surf, col, self.rect, border_radius=6)
        pygame.draw.rect(surf, C['PANEL_BD'], self.rect, 1, border_radius=6)
        ts = self.font.render(self.label, True, C['TXT'])
        surf.blit(ts, ts.get_rect(center=self.rect.center))

    def handle(self, ev):
        if ev.type == pygame.MOUSEMOTION:
            self.hov = self.rect.collidepoint(ev.pos)
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and self.hov:
            return True
        return False

# =============================================================================
# SCROLLABLE LOG
# =============================================================================
class Log:
    def __init__(self, x, y, w, h, font):
        self.rect = pygame.Rect(x, y, w, h)
        self.font = font
        self.lines = []
        self.lh = 18
        self.vis = (h - 32) // self.lh
        self.off = 0

    def add(self, msg):
        self.lines.append(msg)
        if len(self.lines) > 500:
            self.lines.pop(0)
        self.off = max(0, len(self.lines) - self.vis)

    def draw(self, surf):
        pygame.draw.rect(surf, C['PANEL'], self.rect, border_radius=8)
        pygame.draw.rect(surf, C['PANEL_BD'], self.rect, 1, border_radius=8)
        ts = self.font.render("EVENT LOG", True, C['ACCENT'])
        surf.blit(ts, (self.rect.x + 10, self.rect.y + 6))
        pygame.draw.line(surf, C['PANEL_BD'],
                         (self.rect.x + 6, self.rect.y + 26),
                         (self.rect.right - 6, self.rect.y + 26), 1)
        end = min(len(self.lines), self.off + self.vis)
        for i, idx in enumerate(range(self.off, end)):
            ln = self.lines[idx]
            col = C['TXT2']
            if 'FLOOD' in ln or 'blocked' in ln: col = C['WARN']
            elif 'RISK' in ln: col = C['ACCENT']
            elif 'visited' in ln or 'complete' in ln: col = C['OK']
            elif 'ERROR' in ln or 'FAIL' in ln: col = C['ERR']
            if len(ln) > 95: ln = ln[:92] + '...'
            surf.blit(self.font.render(ln, True, col),
                      (self.rect.x + 10, self.rect.y + 32 + i * self.lh))

    def scroll(self, dy):
        self.off = max(0, min(len(self.lines) - self.vis, self.off + dy))

# =============================================================================
# MAIN UI CLASS
# =============================================================================
class CityMindUI:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WIN_W, WIN_H), pygame.RESIZABLE | pygame.SCALED)
        pygame.display.set_caption("CityMind - Urban Intelligence System")
        self.clock = pygame.time.Clock()
        self.f_sm = pygame.font.SysFont("consolas", 13)
        self.f_md = pygame.font.SysFont("consolas", 15)
        self.f_lg = pygame.font.SysFont("consolas", 20, bold=True)
        self.f_ti = pygame.font.SysFont("consolas", 24, bold=True)
        self.anim = 0
        self.last_step_t = 0

        # sim state
        self.city = None
        self.running = False
        self.paused = False
        self.step = 0
        self.civilians = []
        self.team_pos = None
        self.cur_path = []
        self.rng = random.Random(SIM['SEED'])
        self.stats = {'vis': 0, 'unr': 0, 'rer': 0, 'cost': 0.0, 'fld': 0}
        self.narration = "Press PLAY or SPACE to start the simulation."

        # animation state
        self.is_animating = False
        self.anim_path = []
        self.anim_idx = 0
        self.anim_pixel_pos = None
        self.anim_speed = 10.0 # pixels per frame
        self.pending_step_res = None
        self.pending_flood_txt = ""

        # overlay toggles
        self.show_roads = True
        self.show_risk = False
        self.show_amb = True
        self.sel = None   # selected cell
        self.hov = None   # hovered cell

        # log
        self.log = Log(GRID_PAD_X, WIN_H - LOG_H - 10,
                       PANEL_X - GRID_PAD_X - 15, LOG_H, self.f_sm)

        # buttons
        bw = PANEL_W - 20
        bx = PANEL_X + 10
        self.b_play  = Btn(bx, 80, bw, 34, "PLAY",  self.f_md)
        self.b_pause = Btn(bx, 120, bw, 34, "PAUSE", self.f_md)
        self.b_step  = Btn(bx, 160, bw, 34, "STEP",  self.f_md)
        self.b_reset = Btn(bx, 200, bw, 34, "RESET", self.f_md)
        self.b_roads = Btn(bx, 260, bw, 34, "Toggle Roads",      self.f_md)
        self.b_risk  = Btn(bx, 300, bw, 34, "Toggle Risk Map",   self.f_md)
        self.b_amb   = Btn(bx, 340, bw, 34, "Toggle Ambulances", self.f_md)
        self.buttons = [self.b_play, self.b_pause, self.b_step, self.b_reset,
                        self.b_roads, self.b_risk, self.b_amb]

        self._init_city()

    # ----- city init (runs all 5 challenges) -----
    def _init_city(self):
        random.seed(SIM['SEED'])
        self.city = CityGraph(rows=GRID_N, cols=GRID_N)
        self.rng = random.Random(SIM['SEED'])
        self.cur_path = []
        self.log.add("[SYS] Initialising CityMind...")

        p = run_layout_planner(self.city)
        if not p:
            self.log.add("[ERR] CSP layout failed!"); return
        self.log.add("[CH1] Layout complete")

        rd = build_road_network(self.city)
        if not rd:
            self.log.add("[ERR] MST failed!"); return
        self.log.add(f"[CH2] {len(rd['mst_edges'])} roads | cost {rd['total_cost']:.1f}")

        ml = run_risk_pipeline(self.city)
        if ml:
            self.log.add(f"[CH5] Risk done | CV {ml['cv_accuracy']:.2f}")

        pos = place_ambulances(self.city)
        if pos:
            self.city.ambulance_positions = pos
            self.log.add(f"[CH3] {len(pos)} ambulances placed")

        self.civilians = pick_civilians(self.city, SIM['NUM_CIVILIANS'], self.rng)
        self.team_pos = self.city.primary_depot
        self.log.add("[SYS] Ready. Press PLAY or SPACE.")

    # ----- one simulation step (mirrors main.py) -----
    def _do_step(self):
        if self.step >= 20:
            self.log.add("[SIM] Done! 20 steps complete.")
            self.running = False; return

        if self.is_animating:
            return

        self.step += 1
        self.city.set_simulation_step(self.step)

        # 1. floods
        flooded = generate_flood_events(self.city, self.rng)
        flood_txt = ""
        if flooded:
            self.stats['fld'] += len(flooded)
            flood_txt = f"{len(flooded)} road(s) flooded"
            for a, b in flooded:
                self.log.add(f"[FLD] Blocked {self.city.get_label(a)}<->{self.city.get_label(b)}")
        else:
            flood_txt = "no floods"
            self.log.add(f"[S{self.step:02d}] No floods")

        # 2. A* routing
        self.civilians = pick_civilians(self.city, SIM['NUM_CIVILIANS'], self.rng)
        self.cur_path = []
        res = None
        if self.civilians and self.team_pos:
            res = run_emergency_routing(
                city=self.city, civilian_nodes=self.civilians,
                start_node=self.team_pos, flood_schedule=list(flooded) if flooded else [])
            
            if res and res.get('full_path'):
                self.pending_step_res = res
                self.pending_flood_txt = flood_txt
                self.anim_path = res['full_path']
                self.anim_idx = 0
                self.cur_path = self.anim_path # draw full path immediately
                self.is_animating = True
                
                # Start team at current pixel pos
                self.anim_pixel_pos = _center(*self.team_pos)
                
                self.log.add(f"[SIM] Team dispatched to rescue {len(res['visited'])} civilian(s)...")
                return # Skip finish_step until animation completes

        # If no path found or no civilians, finish immediately
        self._finish_step(res, flood_txt)

    def _finish_step(self, res, flood_txt):
        if res:
            self.stats['vis'] += len(res.get('visited', []))
            self.stats['unr'] += len(res.get('unreachable', []))
            self.stats['rer'] += res.get('reroutes', 0)
            self.stats['cost'] += res.get('total_cost', 0.0)
            if res['visited']:
                self.team_pos = res['visited'][-1]
            elif res.get('full_path'):
                self.team_pos = res['full_path'][-1]
                
            vis_n = len(res['visited'])
            unr_n = len(res['unreachable'])
            self.narration = (
                f"Step {self.step}: {flood_txt} | "
                f"Team rescued {vis_n} civilian(s), {unr_n} unreachable | "
                f"cost {res['total_cost']:.1f}")
            self.log.add(
                f"[A*] vis={vis_n} unr={unr_n} "
                f"cost={res['total_cost']:.1f}")

        # 3. every 5 steps: ML + GA
        if self.step % SIM['RISK_REFRESH_EVERY'] == 0:
            ml = run_risk_pipeline(self.city)
            if ml:
                self.log.add(f"[ML] Risk refreshed | CV {ml['cv_accuracy']:.2f}")
            np_ = place_ambulances(self.city,
                                   seed_chromosome=list(self.city.ambulance_positions))
            if np_:
                self.city.ambulance_positions = np_
                self.log.add("[GA] Ambulances repositioned")

        # 4. every 3 steps: road recovery
        if self.step % 3 == 0:
            ub = _unblock_random_roads(self.city, self.rng, max_unblocks=2)
            if ub:
                self.log.add(f"[REC] {ub} road(s) unblocked")


    # ===================== DRAWING =====================

    def _draw_header(self):
        pygame.draw.rect(self.screen, C['HDR'], (0, 0, WIN_W, 55))
        self.screen.blit(
            self.f_ti.render("CITYMIND", True, C['ACCENT']), (15, 12))
        self.screen.blit(
            self.f_sm.render("Urban Intelligence System", True, C['TXT2']), (15, 40))
        # status
        if self.running and not self.paused:
            st, sc = "RUNNING", C['OK']
        elif self.paused:
            st, sc = "PAUSED", C['WARN']
        else:
            st, sc = "READY", C['TXT2']
        ts = self.f_lg.render(st, True, sc)
        self.screen.blit(ts, (WIN_W - ts.get_width() - 20, 18))
        pygame.draw.line(self.screen, C['PANEL_BD'], (0, 55), (WIN_W, 55), 2)

    def _draw_grid(self):
        """Draw a clean 2D top-down grid."""
        # grid background
        pygame.draw.rect(self.screen, (20, 24, 34),
                         (GRID_PAD_X - 2, GRID_PAD_Y - 2, GRID_PX + 4, GRID_PX + 4),
                         border_radius=4)

        # --- 1. cells ---
        for r in range(GRID_N):
            for c in range(GRID_N):
                rect = _rect(r, c)
                node = self.city.get_node((r, c))
                ntype = node.get('location_type', 'Empty')

                # base color
                col = C.get(ntype, C['Empty'])
                # shrink the cell block so there's a visible gap for roads between them
                pygame.draw.rect(self.screen, col, rect.inflate(-6, -6), border_radius=6)

                # risk overlay
                if self.show_risk:
                    risk = node.get('risk_index', 0)
                    ov = pygame.Surface((CELL - 6, CELL - 6), pygame.SRCALPHA)
                    if risk >= 0.65:
                        ov.fill((*C['RISK_H'], 140))
                    elif risk >= 0.35:
                        ov.fill((*C['RISK_M'], 100))
                    else:
                        ov.fill((*C['RISK_L'], 50))
                    self.screen.blit(ov, (rect.x + 3, rect.y + 3))

                # tiny label
                abbr = ntype[0] if ntype != 'AmbulanceDepot' else 'D'
                if ntype == 'Empty': abbr = ''
                if abbr:
                    ts = self.f_sm.render(abbr, True, (255, 255, 255))
                    self.screen.blit(ts, ts.get_rect(center=rect.center))

                # hover / selection highlight
                if (r, c) == self.hov:
                    pygame.draw.rect(self.screen, C['ACCENT'],
                                     rect.inflate(-2, -2), 3, border_radius=6)
                if (r, c) == self.sel:
                    pygame.draw.rect(self.screen, C['TXT'],
                                     rect.inflate(2, 2), 3, border_radius=6)

        # --- 2. grid lines ---
        for i in range(GRID_N + 1):
            x = GRID_PAD_X + i * CELL
            y = GRID_PAD_Y + i * CELL
            pygame.draw.line(self.screen, C['GRID_LINE'],
                             (x, GRID_PAD_Y), (x, GRID_PAD_Y + GRID_PX), 1)
            pygame.draw.line(self.screen, C['GRID_LINE'],
                             (GRID_PAD_X, y), (GRID_PAD_X + GRID_PX, y), 1)

        # --- 3. ambulance coverage overlay ---
        if self.show_amb and self.city.ambulance_positions:
            cov = set()
            for amb in self.city.ambulance_positions:
                q = deque([(amb, 0)]); vis = {amb}
                while q:
                    cur, d = q.popleft(); cov.add(cur)
                    if d < 3:
                        for nb, co in self.city.get_open_neighbors_with_cost(cur):
                            if nb not in vis and co < float('inf'):
                                vis.add(nb); q.append((nb, d + 1))
            for (r, c) in cov:
                ov = pygame.Surface((CELL, CELL), pygame.SRCALPHA)
                ov.fill((*C['COV'], 35))
                self.screen.blit(ov, (GRID_PAD_X + c * CELL, GRID_PAD_Y + r * CELL))

        # --- 4. edges (roads & floods) drawn ON TOP of the grid ---
        if self.show_roads:
            for a, b, data in self.city.get_all_edges():
                ax, ay = _center(*a)
                bx, by = _center(*b)
                if data.get('blocked', False):
                    # Draw a thick red X for blocked roads
                    pygame.draw.line(self.screen, C['ROAD_BLK'], (ax, ay), (bx, by), 4)
                    mx, my = (ax + bx) // 2, (ay + by) // 2
                    pygame.draw.line(self.screen, C['ROAD_BLK'],
                                     (mx - 8, my - 8), (mx + 8, my + 8), 4)
                    pygame.draw.line(self.screen, C['ROAD_BLK'],
                                     (mx + 8, my - 8), (mx - 8, my + 8), 4)
                else:
                    # Draw normal active roads
                    pygame.draw.line(self.screen, C['ROAD'], (ax, ay), (bx, by), 2)

        # --- 5. A* path overlay drawn ON TOP of everything ---
        if self.cur_path and len(self.cur_path) > 1:
            for i in range(len(self.cur_path) - 1):
                ax, ay = _center(*self.cur_path[i])
                bx, by = _center(*self.cur_path[i + 1])
                # Draw thick green path
                pygame.draw.line(self.screen, C['PATH'], (ax, ay), (bx, by), 6)
                pygame.draw.circle(self.screen, C['PATH'], (bx, by), 3) # round corners

        # --- 6. civilian markers ---
        for civ in self.civilians:
            cx, cy = _center(*civ)
            sz = 7
            cy -= 8 # shift slightly up so they don't cover the path
            pygame.draw.polygon(self.screen, (255, 200, 60),
                                [(cx, cy - sz), (cx + sz, cy),
                                 (cx, cy + sz), (cx - sz, cy)])
            pygame.draw.polygon(self.screen, (0, 0, 0),
                                [(cx, cy - sz), (cx + sz, cy),
                                 (cx, cy + sz), (cx - sz, cy)], 2)

        # --- 7. ambulance markers (STATIONARY BACKUPS) ---
        if self.show_amb and self.city.ambulance_positions:
            pulse = int(abs(math.sin(self.anim * 0.1)) * 6)
            for pos in self.city.ambulance_positions:
                cx, cy = _center(*pos)
                pygame.draw.circle(self.screen, C['AMB_GLOW'], (cx, cy), 14 + pulse)
                pygame.draw.circle(self.screen, C['AMB'], (cx, cy), 9)
                pygame.draw.circle(self.screen, C['AMB_GLOW'], (cx, cy), 5)

        # --- 8. team marker (THE ONES ACTUALLY DRIVING AROUND) ---
        if self.team_pos:
            if self.is_animating and self.anim_pixel_pos:
                cx, cy = self.anim_pixel_pos
            else:
                cx, cy = _center(*self.team_pos)
                
            pulse = int(abs(math.sin(self.anim * 0.15)) * 5)
            # Make the team marker very obvious
            pygame.draw.circle(self.screen, C['TEAM'], (cx, cy), 14 + pulse)
            pygame.draw.circle(self.screen, (0, 0, 0), (cx, cy), 14 + pulse, 2)
            pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), 6)

    def _draw_panel(self):
        """Right-side control panel."""
        pygame.draw.rect(self.screen, C['PANEL'],
                         (PANEL_X, 60, PANEL_W, WIN_H - 70), border_radius=8)
        pygame.draw.rect(self.screen, C['PANEL_BD'],
                         (PANEL_X, 60, PANEL_W, WIN_H - 70), 1, border_radius=8)

        self.screen.blit(
            self.f_lg.render("CONTROLS", True, C['ACCENT']), (PANEL_X + 10, 70))

        # step counter
        sc = C['OK'] if self.step > 0 else C['TXT2']
        self.screen.blit(
            self.f_md.render(f"Step: {self.step:02d} / 20", True, sc),
            (PANEL_X + 10, 390))

        # stats
        sy = 420
        for label, key, fmt in [
            ("Visited",     'vis',  'd'),
            ("Unreachable", 'unr',  'd'),
            ("Reroutes",    'rer',  'd'),
            ("Cost",        'cost', '.1f'),
            ("Floods",      'fld',  'd'),
        ]:
            v = self.stats[key]
            txt = f"{label}: {v:{fmt}}"
            self.screen.blit(self.f_sm.render(txt, True, C['TXT2']), (PANEL_X + 12, sy))
            sy += 20

        # toggle indicators
        for btn, on in [(self.b_roads, self.show_roads),
                        (self.b_risk, self.show_risk),
                        (self.b_amb, self.show_amb)]:
            if on:
                pygame.draw.circle(self.screen, C['OK'],
                                   (btn.rect.right - 14, btn.rect.centery), 5)

        # buttons
        for b in self.buttons:
            b.draw(self.screen)

        # selected cell info
        if self.sel and self.city:
            nd = self.city.get_node(self.sel)
            sy = 530
            info = [
                f"Cell: {self.city.get_label(self.sel)}",
                f"Type: {nd['location_type']}",
                f"Risk: {nd['risk_index']:.2f}",
                f"Pop:  {nd['population_density']:.1f}",
            ]
            self.screen.blit(
                self.f_md.render("SELECTED", True, C['ACCENT']),
                (PANEL_X + 10, sy)); sy += 22
            for ln in info:
                self.screen.blit(self.f_sm.render(ln, True, C['TXT']),
                                 (PANEL_X + 12, sy)); sy += 18

        # legend
        ly = WIN_H - 140
        self.screen.blit(
            self.f_md.render("LEGEND", True, C['ACCENT']), (PANEL_X + 10, ly))
        ly += 22
        for label, col in [('R Residential', 'Residential'),
                           ('H Hospital', 'Hospital'),
                           ('S School', 'School'),
                           ('I Industrial', 'Industrial'),
                           ('P PowerPlant', 'PowerPlant'),
                           ('D AmbDepot', 'AmbulanceDepot')]:
            pygame.draw.rect(self.screen, C[col], (PANEL_X + 12, ly, 12, 12))
            self.screen.blit(self.f_sm.render(label, True, C['TXT2']),
                             (PANEL_X + 30, ly)); ly += 18

    # ===================== EVENTS =====================

    def _events(self):
        mx, my = pygame.mouse.get_pos()
        # hover detection
        self.hov = None
        for r in range(GRID_N):
            for c in range(GRID_N):
                if _rect(r, c).collidepoint(mx, my):
                    self.hov = (r, c)

        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_ESCAPE, pygame.K_q):
                    return False
                if ev.key == pygame.K_SPACE:
                    if not self.running:
                        self.running = True; self.paused = False
                        self.log.add("[SIM] Started")
                    else:
                        self.paused = not self.paused
                if ev.key == pygame.K_s and not self.is_animating:
                    self._do_step()
                if ev.key == pygame.K_r:
                    self._reset()
                if ev.key == pygame.K_1:
                    self.show_roads = not self.show_roads
                if ev.key == pygame.K_2:
                    self.show_risk = not self.show_risk
                if ev.key == pygame.K_3:
                    self.show_amb = not self.show_amb
                if ev.key == pygame.K_UP:
                    self.log.scroll(-3)
                if ev.key == pygame.K_DOWN:
                    self.log.scroll(3)
            if ev.type == pygame.MOUSEWHEEL:
                self.log.scroll(-ev.y * 3)
            if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if self.hov:
                    self.sel = self.hov
            # buttons
            for b in self.buttons:
                b.handle(ev)
            if self.b_play.handle(ev):
                self.running = True; self.paused = False
                self.log.add("[SIM] Started")
            if self.b_pause.handle(ev):
                self.paused = not self.paused
            if self.b_step.handle(ev) and not self.is_animating:
                self._do_step()
            if self.b_reset.handle(ev):
                self._reset()
            if self.b_roads.handle(ev):
                self.show_roads = not self.show_roads
            if self.b_risk.handle(ev):
                self.show_risk = not self.show_risk
            if self.b_amb.handle(ev):
                self.show_amb = not self.show_amb
        return True

    def _reset(self):
        self.running = False; self.paused = False
        self.step = 0
        self.stats = {'vis': 0, 'unr': 0, 'rer': 0, 'cost': 0.0, 'fld': 0}
        self.cur_path = []; self.sel = None
        self.is_animating = False
        self.log.lines.clear()
        self._init_city()

    # ===================== MAIN LOOP =====================

    def run(self):
        alive = True
        while alive:
            alive = self._events()
            self.anim += 1

            # --- ANIMATION TICK ---
            if self.is_animating and self.anim_path:
                if self.anim_idx < len(self.anim_path) - 1:
                    target_pos = self.anim_path[self.anim_idx + 1]
                    tx, ty = _center(*target_pos)
                    cx, cy = self.anim_pixel_pos
                    dx, dy = tx - cx, ty - cy
                    dist = math.hypot(dx, dy)
                    
                    if dist <= self.anim_speed:
                        # reached node
                        self.anim_pixel_pos = (tx, ty)
                        self.anim_idx += 1
                        self.team_pos = self.anim_path[self.anim_idx]
                        
                        # Remove civilian marker once reached
                        if self.team_pos in self.civilians:
                            self.civilians.remove(self.team_pos)
                    else:
                        # move towards target
                        self.anim_pixel_pos = (cx + (dx/dist)*self.anim_speed, cy + (dy/dist)*self.anim_speed)
                else:
                    # animation complete
                    self.is_animating = False
                    self._finish_step(self.pending_step_res, self.pending_flood_txt)
            else:
                # auto-step
                now = pygame.time.get_ticks()
                if (self.running and not self.paused and self.step < 20
                        and now - self.last_step_t >= 800):
                    self._do_step()
                    self.last_step_t = now

            # draw
            self.screen.fill(C['BG'])
            self._draw_header()
            self._draw_grid()
            self._draw_panel()
            self.log.draw(self.screen)

            # narration bar above event log
            nr_y = self.log.rect.y - 24
            nr_w = self.log.rect.width
            pygame.draw.rect(self.screen, (22, 28, 42),
                             (GRID_PAD_X, nr_y, nr_w, 22), border_radius=4)
            self.screen.blit(
                self.f_sm.render(self.narration[:120], True, C['ACCENT']),
                (GRID_PAD_X + 8, nr_y + 4))

            pygame.display.flip()
            self.clock.tick(60)

        pygame.quit()


# =============================================================================
if __name__ == "__main__":
    ui = CityMindUI()
    ui.run()