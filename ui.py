"""
ui.py - CityMind Urban Intelligence System GUI
================================================
A beautiful, modern Pygame-based user interface for the CityMind system.
- Larger grid visualization (72px cells)
- Clear isometric 3D view
- Full simulation controls
"""

import pygame
import sys
import math
import random
from pygame.locals import *

# Import CityMind modules
from city_graph import CityGraph
from challenge1_csp import run_layout_planner
from challenge2_mst import build_road_network
from challenge3_ga import place_ambulances
from challenge4_astar import run_emergency_routing
from challenge5_ml import run_risk_pipeline

# Import simulation helpers from main (flood generator, civilian picker)
from main import generate_flood_events, pick_civilians, _unblock_random_roads


# =============================================================================
# CONSTANTS - ADJUSTED FOR LARGER, CLEARER VISUALIZATION
# =============================================================================

# Window settings - larger window for better visibility
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900

# Grid settings - BIGGER cells for clear visibility
GRID_SIZE = 10
CELL_SIZE = 72                    # Much larger! (was 52)
CELL_HEIGHT = CELL_SIZE // 2      # Half for isometric (36px)

# Grid positioning - centered and well-spaced
GRID_MARGIN_TOP = 80
GRID_MARGIN_LEFT = 50

# Panel settings - wider to accommodate controls
PANEL_WIDTH = 340
PANEL_MARGIN_RIGHT = 30
LOG_HEIGHT = 200

# Colors - Dark Theme with vibrant accents
COLORS = {
    'BG_PRIMARY': (8, 12, 25),
    'BG_SECONDARY': (15, 25, 45),
    'BG_PANEL': (20, 30, 55, 235),
    'BG_LOG': (10, 20, 45, 245),
    
    # Cell colors (base and dark for 3D effect)
    'RESIDENTIAL': (16, 185, 129),
    'RESIDENTIAL_DARK': (10, 120, 80),
    'HOSPITAL': (239, 68, 68),
    'HOSPITAL_DARK': (180, 40, 40),
    'SCHOOL': (245, 158, 11),
    'SCHOOL_DARK': (180, 110, 5),
    'INDUSTRIAL': (107, 114, 128),
    'INDUSTRIAL_DARK': (70, 75, 85),
    'POWER_PLANT': (139, 92, 246),
    'POWER_PLANT_DARK': (100, 60, 200),
    'AMBULANCE_DEPOT': (59, 130, 246),
    'AMBULANCE_DEPOT_DARK': (40, 90, 200),
    'EMPTY': (30, 41, 59),
    'EMPTY_DARK': (20, 28, 40),
    
    # Risk heatmap colors
    'RISK_LOW': (16, 185, 129),
    'RISK_MEDIUM': (245, 158, 11),
    'RISK_HIGH': (239, 68, 68),
    
    # Roads
    'ROAD_NORMAL': (100, 116, 139, 220),
    'ROAD_FLOODED': (6, 182, 212),
    'ROAD_FLOODED_GLOW': (6, 182, 212, 100),
    
    # UI Elements
    'TEXT_PRIMARY': (248, 250, 252),
    'TEXT_SECONDARY': (148, 163, 184),
    'TEXT_ACCENT': (56, 189, 248),
    'BUTTON_HOVER': (56, 189, 248),
    'BUTTON_NORMAL': (51, 65, 85),
    'BORDER': (51, 65, 85),
    'SUCCESS': (34, 197, 94),
    'WARNING': (234, 179, 8),
    'ERROR': (239, 68, 68),
    'SHADOW': (0, 0, 0, 80),
}

# Simulation settings
SIMULATION_SETTINGS = {
    'RISK_REFRESH_EVERY': 5,
    'NUM_CIVILIANS': 6,
    'MAX_FLOODS_PER_STEP': 2,
    'RANDOM_SEED': 42,
}


# =============================================================================
# UI HELPER FUNCTIONS
# =============================================================================

def draw_rounded_rect(surface, color, rect, radius=10):
    """Draw a rectangle with rounded corners."""
    pygame.draw.rect(surface, color, rect, border_radius=radius)


def draw_glass_panel(surface, rect, radius=12):
    """Draw a glassmorphism-style panel."""
    panel_surface = pygame.Surface((rect.width, rect.height), pygame.SRCALPHA)
    pygame.draw.rect(panel_surface, (*COLORS['BG_PANEL'][:3], 220), 
                     panel_surface.get_rect(), border_radius=radius)
    pygame.draw.rect(panel_surface, (*COLORS['BORDER'], 100), 
                     panel_surface.get_rect(), width=2, border_radius=radius)
    surface.blit(panel_surface, rect)


def draw_text(surface, text, font, color, x, y, center=False):
    """Draw text on surface."""
    text_surface = font.render(text, True, color)
    if center:
        text_rect = text_surface.get_rect(center=(x, y))
        surface.blit(text_surface, text_rect)
    else:
        surface.blit(text_surface, (x, y))


def draw_3d_cell(surface, x, y, width, height, base_color, dark_color, selected=False, animation=0):
    """Draw a 3D-looking isometric cell with depth effect."""
    # Calculate isometric points
    top_center = (x + width // 2, y)
    left_point = (x, y + height // 2)
    right_point = (x + width, y + height // 2)
    bottom_center = (x + width // 2, y + height)
    
    # Top face (lighter - catches "light")
    top_color = base_color
    pygame.draw.polygon(surface, top_color, [top_center, left_point, right_point])
    
    # Left/Side face (darker - shadow effect)
    side_color = dark_color
    pygame.draw.polygon(surface, side_color, [left_point, (x, y + height), bottom_center, right_point])
    
    # Highlight edge for 3D effect
    highlight = (min(255, dark_color[0] + 40), min(255, dark_color[1] + 40), min(255, dark_color[2] + 40))
    pygame.draw.line(surface, highlight, left_point, (x, y + height), 2)
    
    # Selection highlight (pulsing effect)
    if selected:
        pulse = int(12 + abs(math.sin(animation * 0.08)) * 10)
        pygame.draw.polygon(surface, (255, 255, 255, 150), 
                           [top_center, left_point, right_point, bottom_center], pulse)


def draw_3d_road(surface, x1, y1, x2, y2, color, width=5, is_flooded=False, animation=0):
    """Draw a 3D-looking road with glow effect for flooded roads."""
    if is_flooded:
        # Glow effect for flooded roads
        glow_intensity = int(80 + abs(math.sin(animation * 0.15)) * 60)
        glow_color = (COLORS['ROAD_FLOODED'][0], COLORS['ROAD_FLOODED'][1], COLORS['ROAD_FLOODED'][2], glow_intensity)
        for i in range(4, 0, -1):
            pygame.draw.line(surface, (*COLORS['ROAD_FLOODED'], max(30, 80 // i)), 
                           (x1, y1), (x2, y2), width + i * 2)
    
    # Main road line
    pygame.draw.line(surface, color, (x1, y1), (x2, y2), width)
    
    # Road highlight for 3D effect
    if not is_flooded:
        highlight_color = (min(255, color[0] + 50), min(255, color[1] + 50), min(255, color[2] + 50))
        pygame.draw.line(surface, highlight_color, (x1 - 1, y1 - 1), (x2 - 1, y2 - 1), max(2, width - 3))


def draw_3d_building_top(surface, x, y, width, height, color, animation=0):
    """Draw a 3D building top extrusion for important buildings (Hospitals, Power Plants)."""
    body_height = 10
    dark_color = tuple(max(0, c - 60) for c in color)
    
    # Building top face
    pygame.draw.polygon(surface, color, [
        (x + width//4, y - body_height),
        (x + 3*width//4, y - body_height),
        (x + width, y),
        (x, y)
    ])
    
    # Building front face
    pygame.draw.polygon(surface, dark_color, [
        (x, y),
        (x + width, y),
        (x + width, y + height//2),
        (x, y + height//2)
    ])
    
    # Animated beacon for hospitals (pulsing red)
    if color == COLORS['HOSPITAL']:
        light = int(150 + abs(math.sin(animation * 0.12)) * 105)
        pygame.draw.circle(surface, (light, 0, 0), (x + width//2, y - body_height - 4), 5)
        pygame.draw.circle(surface, (255, 255, 200), (x + width//2, y - body_height - 4), 2)


# =============================================================================
# BUTTON CLASS
# =============================================================================

class Button3D:
    def __init__(self, x, y, width, height, text, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.font = font
        self.is_hovered = False
        
    def draw(self, surface, animation=0):
        if self.is_hovered:
            base_color = COLORS['BUTTON_HOVER']
        else:
            base_color = COLORS['BUTTON_NORMAL']
        
        # Shadow effect
        shadow_rect = self.rect.inflate(4, 4)
        pygame.draw.rect(surface, COLORS['SHADOW'], shadow_rect, border_radius=10)
        
        # Button body
        pygame.draw.rect(surface, base_color, self.rect, border_radius=8)
        
        # 3D highlight on top edge
        highlight_rect = pygame.Rect(self.rect.x + 2, self.rect.y + 2, 
                                     self.rect.width - 4, self.rect.height // 3)
        pygame.draw.rect(surface, (min(255, base_color[0] + 50),
                                   min(255, base_color[1] + 50),
                                   min(255, base_color[2] + 50)), 
                        highlight_rect, border_radius=5)
        
        # Border on hover
        if self.is_hovered:
            pygame.draw.rect(surface, COLORS['TEXT_ACCENT'], self.rect, width=2, border_radius=8)
        
        # Button text
        draw_text(surface, self.text, self.font, COLORS['TEXT_PRIMARY'],
                  self.rect.centerx, self.rect.centery, center=True)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEMOTION:
            self.is_hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.is_hovered:
                return True
        return False


# =============================================================================
# SCROLLABLE LOG CLASS
# =============================================================================

class ScrollableLog:
    def __init__(self, x, y, width, height, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.lines = []
        self.scroll_offset = 0
        self.line_height = 22
        self.visible_lines = height // self.line_height
        
    def add_line(self, line):
        self.lines.append(line)
        # Auto-scroll to bottom when new lines added
        self.scroll_offset = max(0, len(self.lines) - self.visible_lines)
        
    def draw(self, surface):
        # Background
        log_surface = pygame.Surface((self.rect.width, self.rect.height), pygame.SRCALPHA)
        pygame.draw.rect(log_surface, (*COLORS['BG_LOG'][:3], 230), 
                         log_surface.get_rect(), border_radius=10)
        surface.blit(log_surface, self.rect)
        pygame.draw.rect(surface, COLORS['BORDER'], self.rect, width=2, border_radius=10)
        
        # Title
        title_font = pygame.font.Font(None, 20)
        draw_text(surface, "📋 EVENT LOG", title_font, COLORS['TEXT_ACCENT'],
                  self.rect.x + 12, self.rect.y + 8)
        
        # Separator line
        pygame.draw.line(surface, COLORS['BORDER'], 
                        (self.rect.x + 8, self.rect.y + 32),
                        (self.rect.x + self.rect.width - 8, self.rect.y + 32), 2)
        
        # Log entries
        start_idx = max(0, self.scroll_offset)
        end_idx = min(len(self.lines), start_idx + self.visible_lines - 1)
        
        for i, idx in enumerate(range(start_idx, end_idx)):
            line = self.lines[idx]
            y_pos = self.rect.y + 42 + i * self.line_height
            
            # Color based on event type
            color = COLORS['TEXT_SECONDARY']
            if "FLOOD" in line or "blocked" in line:
                color = COLORS['WARNING']
            elif "RISK" in line:
                color = COLORS['TEXT_ACCENT']
            elif "reached" in line or "complete" in line or "visited" in line:
                color = COLORS['SUCCESS']
            elif "ERROR" in line or "FAILED" in line:
                color = COLORS['ERROR']
            elif "ambulance" in line or "Ambulance" in line:
                color = COLORS['AMBULANCE_DEPOT']
            
            # Truncate long lines
            if len(line) > 90:
                line = line[:87] + "..."
            
            draw_text(surface, line, self.font, color, self.rect.x + 12, y_pos)
    
    def scroll_up(self):
        self.scroll_offset = max(0, self.scroll_offset - 3)
    
    def scroll_down(self):
        self.scroll_offset = min(max(0, len(self.lines) - self.visible_lines), 
                                 self.scroll_offset + 3)


# =============================================================================
# MAIN UI CLASS
# =============================================================================

class CityMindUI:
    def __init__(self):
        pygame.init()
        
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("🏙️ CITYMIND - Urban Intelligence System | 3D Isometric View")
        
        # Fonts - larger for better readability
        self.font_small = pygame.font.Font(None, 15)
        self.font_normal = pygame.font.Font(None, 19)
        self.font_large = pygame.font.Font(None, 26)
        self.font_title = pygame.font.Font(None, 34)
        
        self.clock = pygame.time.Clock()
        self.animation_frame = 0
        
        # Simulation state
        self.city = None
        self.is_running = False
        self.is_paused = False
        self.current_step = 0

        # Simulation tracking (matches main.py state)
        self.civilians     = []        # current list of civilian nodes
        self.team_position = None      # current team position (starts at depot)
        self.current_path  = []        # last A* full path — drawn on grid
        self.sim_rng       = random.Random(SIMULATION_SETTINGS['RANDOM_SEED'])

        # UI state
        self.show_roads = True
        self.show_ambulances = True
        self.show_risk = False
        self.selected_cell = None
        self.hovered_cell = None

        # Statistics
        self.stats = {
            'visited': 0, 'unreachable': 0, 'reroutes': 0,
            'total_cost': 0.0, 'floods': 0
        }
        
        # Event log
        self.event_log = ScrollableLog(
            x=GRID_MARGIN_LEFT,
            y=WINDOW_HEIGHT - LOG_HEIGHT - 15,
            width=WINDOW_WIDTH - GRID_MARGIN_LEFT - PANEL_WIDTH - 50,
            height=LOG_HEIGHT,
            font=self.font_small
        )
        
        self._create_buttons()
        self._init_city()
        
    def _create_buttons(self):
        """Create UI buttons."""
        panel_x = WINDOW_WIDTH - PANEL_WIDTH - PANEL_MARGIN_RIGHT
        y_offset = 80
        button_width = PANEL_WIDTH - 40
        button_height = 42
        
        self.btn_play = Button3D(panel_x + 20, y_offset, button_width, button_height, "▶ PLAY", self.font_normal)
        self.btn_pause = Button3D(panel_x + 20, y_offset + 52, button_width, button_height, "⏸ PAUSE", self.font_normal)
        self.btn_stop = Button3D(panel_x + 20, y_offset + 104, button_width, button_height, "⏹ STOP", self.font_normal)
        self.btn_step = Button3D(panel_x + 20, y_offset + 156, button_width, button_height, "⏩ STEP", self.font_normal)
        
        y_offset += 230
        self.btn_roads = Button3D(panel_x + 20, y_offset, button_width, button_height, "🛣 TOGGLE ROADS", self.font_normal)
        self.btn_ambulances = Button3D(panel_x + 20, y_offset + 52, button_width, button_height, "🚑 TOGGLE AMBULANCES", self.font_normal)
        self.btn_risk = Button3D(panel_x + 20, y_offset + 104, button_width, button_height, "🔥 TOGGLE RISK", self.font_normal)
    
    def _init_city(self):
        """Initialize the city graph and run all 5 challenges (same order as main.py)."""
        self.city = CityGraph(rows=GRID_SIZE, cols=GRID_SIZE)
        self.sim_rng = random.Random(SIMULATION_SETTINGS['RANDOM_SEED'])
        self.current_path = []
        self.event_log.add_line("[SYSTEM] CityMind initialising...")

        # Challenge 1: CSP City Layout
        self.event_log.add_line("[CH1-CSP] Running city layout planner...")
        planner = run_layout_planner(self.city)
        if planner is None:
            self.event_log.add_line("[ERROR] Challenge 1 failed!")
            return
        self.event_log.add_line("[CH1-CSP] Layout complete — hospital & depot placed")

        # Challenge 2: MST Road Network
        self.event_log.add_line("[CH2-MST] Building minimum spanning tree road network...")
        road_result = build_road_network(self.city)
        if not road_result:
            self.event_log.add_line("[ERROR] Challenge 2 failed!")
            return
        self.event_log.add_line(
            f"[CH2-MST] {len(road_result['mst_edges'])} roads | "
            f"cost:{road_result['total_cost']:.1f} | "
            f"redundancy:{'YES' if road_result['redundant_edge'] else 'NO'}"
        )

        # Challenge 5: Initial ML Risk Prediction
        self.event_log.add_line("[CH5-ML] Running K-Means + Random Forest risk pipeline...")
        ml_result = run_risk_pipeline(self.city)
        if ml_result:
            self.event_log.add_line(
                f"[CH5-ML] Risk complete | CV accuracy: {ml_result['cv_accuracy']:.2f}"
            )

        # Challenge 3: GA Ambulance Placement
        self.event_log.add_line("[CH3-GA] Running genetic algorithm for ambulance placement...")
        positions = place_ambulances(self.city)
        if positions:
            self.city.ambulance_positions = positions
            self.event_log.add_line(f"[CH3-GA] 3 ambulances placed optimally")

        # Initial civilian selection & team position
        self.civilians     = self._pick_civilians()
        self.team_position = self.city.primary_depot
        self.event_log.add_line(
            f"[SIM] Team starts at {self.city.get_label(self.team_position)} | "
            f"{len(self.civilians)} civilians to rescue"
        )
        self.event_log.add_line("[SYSTEM] Ready! Press PLAY to start simulation.")
    
    def _world_to_screen(self, grid_x, grid_y):
        """Convert grid coordinates to isometric screen coordinates - centered for larger grid."""
        # Center the grid on screen
        grid_total_width = GRID_SIZE * CELL_SIZE
        grid_total_height = GRID_SIZE * CELL_HEIGHT
        offset_x = (WINDOW_WIDTH - grid_total_width) // 2 - 60  # Shift left a bit for panel
        offset_y = GRID_MARGIN_TOP + 30
        
        screen_x = (grid_x - grid_y) * CELL_SIZE // 2 + offset_x + grid_total_width // 2
        screen_y = (grid_x + grid_y) * CELL_HEIGHT // 2 + offset_y
        return int(screen_x), int(screen_y)
    
    def _get_cell_colors(self, row, col):
        """Get cell colors based on type and overlay settings."""
        cell = (row, col)
        node_data = self.city.get_node(cell)
        
        # Risk heatmap overlay takes priority
        if self.show_risk:
            risk = node_data.get('risk_index', 0)
            if risk >= 0.65:
                return COLORS['RISK_HIGH'], COLORS['RISK_HIGH']
            elif risk >= 0.35:
                return COLORS['RISK_MEDIUM'], COLORS['RISK_MEDIUM']
            return COLORS['RISK_LOW'], COLORS['RISK_LOW']
        
        # Normal cell coloring
        loc_type = node_data.get('location_type', 'Empty')
        color_map = {
            'Residential': (COLORS['RESIDENTIAL'], COLORS['RESIDENTIAL_DARK']),
            'Hospital': (COLORS['HOSPITAL'], COLORS['HOSPITAL_DARK']),
            'School': (COLORS['SCHOOL'], COLORS['SCHOOL_DARK']),
            'Industrial': (COLORS['INDUSTRIAL'], COLORS['INDUSTRIAL_DARK']),
            'PowerPlant': (COLORS['POWER_PLANT'], COLORS['POWER_PLANT_DARK']),
            'AmbulanceDepot': (COLORS['AMBULANCE_DEPOT'], COLORS['AMBULANCE_DEPOT_DARK']),
            'Empty': (COLORS['EMPTY'], COLORS['EMPTY_DARK'])
        }
        return color_map.get(loc_type, (COLORS['EMPTY'], COLORS['EMPTY_DARK']))
    
    def _draw_grid_3d(self):
        """Draw the isometric 3D grid with all elements."""
        # Sort cells for proper layering (back to front)
        cells = [(row, col) for row in range(GRID_SIZE) for col in range(GRID_SIZE)]
        cells.sort(key=lambda x: x[0] + x[1])
        
        road_segments = []
        
        for row, col in cells:
            x, y = self._world_to_screen(row, col)
            is_selected = (self.selected_cell == (row, col))
            is_hovered = (self.hovered_cell == (row, col))
            
            base_color, dark_color = self._get_cell_colors(row, col)
            
            # Draw 3D cell
            draw_3d_cell(self.screen, x, y, CELL_SIZE, CELL_HEIGHT, 
                        base_color, dark_color, is_selected or is_hovered, self.animation_frame)
            
            # Draw building top for important structures
            loc_type = self.city.get_location_type((row, col))
            if loc_type in ['Hospital', 'PowerPlant']:
                draw_3d_building_top(self.screen, x, y, CELL_SIZE, CELL_HEIGHT, 
                                    base_color, self.animation_frame)
            
            # Collect road segments for drawing after cells
            if self.show_roads:
                for dr, dc in [(1, 0), (0, 1)]:
                    nr, nc = row + dr, col + dc
                    if 0 <= nr < GRID_SIZE and 0 <= nc < GRID_SIZE:
                        if self.city.graph.has_edge((row, col), (nr, nc)):
                            x2, y2 = self._world_to_screen(nr, nc)
                            edge_data = self.city.graph.get_edge_data((row, col), (nr, nc))
                            is_blocked = edge_data.get("blocked", False) if edge_data else False
                            road_segments.append((x + CELL_SIZE//2, y + CELL_HEIGHT//2, 
                                                 x2 + CELL_SIZE//2, y2 + CELL_HEIGHT//2, is_blocked))
        
        # Draw roads
        if self.show_roads:
            for x1, y1, x2, y2, is_blocked in road_segments:
                color = COLORS['ROAD_FLOODED'] if is_blocked else COLORS['ROAD_NORMAL']
                draw_3d_road(self.screen, x1, y1, x2, y2, color,
                            width=6 if is_blocked else 4,
                            is_flooded=is_blocked,
                            animation=self.animation_frame)

        # -- Draw A* path (bright green overlay) ------------------------------
        # Shows the last computed team route so the viewer can see A* in action.
        if self.current_path and len(self.current_path) > 1:
            for i in range(len(self.current_path) - 1):
                n1 = self.current_path[i]
                n2 = self.current_path[i + 1]
                x1, y1 = self._world_to_screen(n1[0], n1[1])
                x2, y2 = self._world_to_screen(n2[0], n2[1])
                cx1 = x1 + CELL_SIZE // 2
                cy1 = y1 + CELL_HEIGHT // 2
                cx2 = x2 + CELL_SIZE // 2
                cy2 = y2 + CELL_HEIGHT // 2
                # Glowing path line
                pygame.draw.line(self.screen, (0, 255, 120), (cx1, cy1), (cx2, cy2), 5)
                pygame.draw.line(self.screen, (180, 255, 210), (cx1, cy1), (cx2, cy2), 2)

        # -- Draw team position marker -----------------------------------------
        if self.team_position:
            tx, ty = self._world_to_screen(self.team_position[0], self.team_position[1])
            tcx = tx + CELL_SIZE // 2
            tcy = ty + CELL_HEIGHT // 2
            pulse = int(abs(math.sin(self.animation_frame * 0.15)) * 8)
            pygame.draw.circle(self.screen, (255, 220, 0), (tcx, tcy), 14 + pulse, 3)
            pygame.draw.circle(self.screen, (255, 255, 180), (tcx, tcy), 7)
        
        # Draw ambulances on top
        if self.show_ambulances and self.city.ambulance_positions:
            for pos in self.city.ambulance_positions:
                row, col = pos
                x, y = self._world_to_screen(row, col)
                center_x = x + CELL_SIZE // 2
                center_y = y + CELL_HEIGHT // 2
                
                # Animated pulse effect
                pulse = abs(math.sin(self.animation_frame * 0.12)) * 10
                glow_radius = 18 + pulse
                
                # Glow effect
                for i in range(3, 0, -1):
                    alpha = 100 // i
                    pygame.draw.circle(self.screen, (COLORS['ERROR'][0], COLORS['ERROR'][1], COLORS['ERROR'][2], alpha), 
                                      (center_x, center_y), int(glow_radius * i / 2))
                
                # Main ambulance marker
                pygame.draw.circle(self.screen, COLORS['ERROR'], (center_x, center_y), 15 + pulse//3)
                pygame.draw.circle(self.screen, COLORS['TEXT_PRIMARY'], (center_x, center_y), 10)
                
                # Ambulance text
                font = pygame.font.Font(None, 22)
                text = font.render("🚑", True, COLORS['TEXT_PRIMARY'])
                text_rect = text.get_rect(center=(center_x, center_y))
                self.screen.blit(text, text_rect)
    
    def _draw_control_panel(self):
        """Draw the control panel with statistics and buttons."""
        panel_x = WINDOW_WIDTH - PANEL_WIDTH - PANEL_MARGIN_RIGHT
        panel_rect = pygame.Rect(panel_x, 60, PANEL_WIDTH, 460)
        
        # Glass panel
        panel_surface = pygame.Surface((PANEL_WIDTH, 460), pygame.SRCALPHA)
        pygame.draw.rect(panel_surface, (*COLORS['BG_PANEL'][:3], 220), 
                        panel_surface.get_rect(), border_radius=15)
        pygame.draw.rect(panel_surface, COLORS['BORDER'], 
                        panel_surface.get_rect(), width=2, border_radius=15)
        self.screen.blit(panel_surface, (panel_x, 60))
        
        # Title
        draw_text(self.screen, "🎮 CONTROL PANEL", self.font_large, COLORS['TEXT_ACCENT'],
                  panel_x + PANEL_WIDTH // 2, 85, center=True)
        
        # Step indicator with 3D effect
        step_text = f"📊 STEP: {self.current_step:02d} / 20"
        step_color = COLORS['SUCCESS'] if self.current_step > 0 else COLORS['TEXT_SECONDARY']
        draw_text(self.screen, step_text, self.font_large, step_color,
                  panel_x + PANEL_WIDTH // 2, 125, center=True)
        
        # Statistics
        stats_y = 290
        stats = [
            f"✅ VISITED: {self.stats['visited']}",
            f"❌ UNREACHABLE: {self.stats['unreachable']}",
            f"🔄 REROUTES: {self.stats['reroutes']}",
            f"💰 TOTAL COST: {self.stats['total_cost']:.2f}",
            f"💧 FLOODS: {self.stats['floods']}",
        ]
        
        for i, stat in enumerate(stats):
            draw_text(self.screen, stat, self.font_normal, COLORS['TEXT_PRIMARY'],
                      panel_x + 25, stats_y + i * 38)
        
        # Draw buttons
        self.btn_play.draw(self.screen, self.animation_frame)
        self.btn_pause.draw(self.screen, self.animation_frame)
        self.btn_stop.draw(self.screen, self.animation_frame)
        self.btn_step.draw(self.screen, self.animation_frame)
        self.btn_roads.draw(self.screen, self.animation_frame)
        self.btn_ambulances.draw(self.screen, self.animation_frame)
        self.btn_risk.draw(self.screen, self.animation_frame)
        
        # Active overlay indicators
        if self.show_roads:
            pygame.draw.circle(self.screen, COLORS['SUCCESS'], 
                             (panel_x + PANEL_WIDTH - 30, self.btn_roads.rect.centery), 8)
        if self.show_ambulances:
            pygame.draw.circle(self.screen, COLORS['SUCCESS'], 
                             (panel_x + PANEL_WIDTH - 30, self.btn_ambulances.rect.centery), 8)
        if self.show_risk:
            pygame.draw.circle(self.screen, COLORS['SUCCESS'], 
                             (panel_x + PANEL_WIDTH - 30, self.btn_risk.rect.centery), 8)
    
    def _draw_header(self):
        """Draw the header bar with title and status."""
        header_rect = pygame.Rect(0, 0, WINDOW_WIDTH, 58)
        pygame.draw.rect(self.screen, COLORS['BG_SECONDARY'], header_rect)
        
        # Title with glow effect
        draw_text(self.screen, "🏙️ CITYMIND", self.font_title, COLORS['TEXT_ACCENT'], 22, 30)
        draw_text(self.screen, "Urban Intelligence System - 3D Isometric View", self.font_small, 
                  COLORS['TEXT_SECONDARY'], 22, 52)
        
        # Status with animation
        if self.is_running and not self.is_paused:
            status = "🔴 SIMULATING"
            status_color = COLORS['SUCCESS']
            pulse = abs(math.sin(self.animation_frame * 0.1)) * 30
            status_color = (min(255, status_color[0] + int(pulse)), status_color[1], status_color[2])
        elif self.is_paused:
            status = "⏸️ PAUSED"
            status_color = COLORS['WARNING']
        else:
            status = "⚫ READY"
            status_color = COLORS['TEXT_ACCENT']
        
        draw_text(self.screen, status, self.font_large, status_color,
                  WINDOW_WIDTH - 140, 35)
        
        # Separator line
        pygame.draw.line(self.screen, COLORS['BORDER'], (0, 58), (WINDOW_WIDTH, 58), 3)
    
    def _handle_events(self):
        """Handle all input events."""
        mouse_x, mouse_y = pygame.mouse.get_pos()
        
        # Detect hovered cell (for tooltip effect)
        self.hovered_cell = None
        for row in range(GRID_SIZE):
            for col in range(GRID_SIZE):
                x, y = self._world_to_screen(row, col)
                if (x <= mouse_x <= x + CELL_SIZE and 
                    y <= mouse_y <= y + CELL_HEIGHT):
                    self.hovered_cell = (row, col)
        
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_SPACE:
                    if self.is_running and not self.is_paused:
                        self.is_paused = True
                        self.event_log.add_line("[UI] ⏸️ Simulation paused")
                    elif self.is_running and self.is_paused:
                        self.is_paused = False
                        self.event_log.add_line("[UI] ▶️ Simulation resumed")
                    else:
                        self._start_simulation()
                elif event.key == pygame.K_r:
                    self._reset_simulation()
                elif event.key == pygame.K_UP:
                    self.event_log.scroll_up()
                elif event.key == pygame.K_DOWN:
                    self.event_log.scroll_down()
                elif event.key == pygame.K_s:
                    self._step_simulation()
            
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.hovered_cell:
                    self.selected_cell = self.hovered_cell
                    node = self.city.get_node(self.selected_cell)
                    self.event_log.add_line(f"[UI] 📍 Selected: {self.city.get_label(self.selected_cell)} | Type: {node['location_type']} | Risk: {node['risk_index']:.2f}")
            
            # Button events
            if self.btn_play.handle_event(event):
                self._start_simulation()
            if self.btn_pause.handle_event(event):
                self.is_paused = not self.is_paused
                if self.is_paused:
                    self.event_log.add_line("[UI] ⏸️ Paused")
                else:
                    self.event_log.add_line("[UI] ▶️ Resumed")
            if self.btn_stop.handle_event(event):
                self._stop_simulation()
            if self.btn_step.handle_event(event):
                self._step_simulation()
            if self.btn_roads.handle_event(event):
                self.show_roads = not self.show_roads
                self.event_log.add_line(f"[UI] 🛣️ Roads overlay: {'ON' if self.show_roads else 'OFF'}")
            if self.btn_ambulances.handle_event(event):
                self.show_ambulances = not self.show_ambulances
                self.event_log.add_line(f"[UI] 🚑 Ambulances overlay: {'ON' if self.show_ambulances else 'OFF'}")
            if self.btn_risk.handle_event(event):
                self.show_risk = not self.show_risk
                self.event_log.add_line(f"[UI] 🔥 Risk heatmap: {'ON' if self.show_risk else 'OFF'}")
        
        return True
    
    def _start_simulation(self):
        """Start or resume simulation."""
        if not self.is_running:
            self.is_running = True
            self.is_paused = False
            self.current_step = 0
            self.stats = {'visited': 0, 'unreachable': 0, 'reroutes': 0, 'total_cost': 0.0, 'floods': 0}
            self.current_path  = []
            self.sim_rng       = random.Random(SIMULATION_SETTINGS['RANDOM_SEED'])
            self.team_position = self.city.primary_depot
            self.civilians     = self._pick_civilians()
            self.event_log.add_line("[SIM] Started! Running 20 steps...")
    
    def _stop_simulation(self):
        """Stop simulation."""
        self.is_running = False
        self.is_paused = False
        self.current_path = []
        self.event_log.add_line("[SIM] Stopped.")

    def _reset_simulation(self):
        """Reset simulation to initial state."""
        self.is_running = False
        self.is_paused = False
        self._init_city()
        self.current_step = 0
        self.stats = {'visited': 0, 'unreachable': 0, 'reroutes': 0, 'total_cost': 0.0, 'floods': 0}
        self.current_path  = []
        self.team_position = self.city.primary_depot if self.city else None
        self.selected_cell = None
        self.event_log.add_line("[SIM] Reset complete.")
    
    def _pick_civilians(self):
        """Pick civilians using the same logic as main.py."""
        return pick_civilians(
            self.city,
            SIMULATION_SETTINGS['NUM_CIVILIANS'],
            self.sim_rng
        )

    def _step_simulation(self):
        """
        Execute one simulation step — mirrors main.py exactly:
          Step 1: generate_flood_events()      (flood before routing)
          Step 2: run_emergency_routing()       (A* nearest-first, reroutes on flood)
          Step 3: every 5 steps — ML + GA      (risk refresh + ambulance reposition)
          Step 4: every 3 steps — road recovery (unblock 0-1 roads)
        """
        if not self.is_running:
            self.is_running = True
            self.current_step = 0

        if self.current_step >= 20:
            self.event_log.add_line("[SIM] Simulation complete! Press STOP to reset.")
            return

        self.current_step += 1
        self.city.set_simulation_step(self.current_step)

        # -- STEP 1: Flood events (design doc step 1) --------------------------
        flooded = generate_flood_events(self.city, self.sim_rng)
        if flooded:
            self.stats['floods'] += len(flooded)
            for fa, fb in flooded:
                self.event_log.add_line(
                    f"[FLOOD] Road blocked: {self.city.get_label(fa)} <-> {self.city.get_label(fb)}"
                )
        else:
            self.event_log.add_line(f"[STEP {self.current_step:02d}] No floods this step")

        # -- STEP 2: A* Emergency Routing (design doc step 2) -----------------
        # Team uses nearest-first ordering; reroutes automatically on flood.
        self.current_path = []
        if self.civilians and self.team_position:
            result = run_emergency_routing(
                city           = self.city,
                civilian_nodes = self.civilians,
                start_node     = self.team_position,
                flood_schedule = []
            )
            if result:
                self.stats['visited']     += len(result.get("visited", []))
                self.stats['unreachable'] += len(result.get("unreachable", []))
                self.stats['reroutes']    += result.get("reroutes", 0)
                self.stats['total_cost']  += result.get("total_cost", 0.0)

                # Update team position
                if result["visited"]:
                    self.team_position = result["visited"][-1]
                elif result["full_path"]:
                    self.team_position = result["full_path"][-1]

                # Store path for grid visualization
                self.current_path = result.get("full_path", [])

                if result.get("reroutes", 0) > 0:
                    self.event_log.add_line(
                        f"[CH4-A*] REROUTED x{result['reroutes']} | "
                        f"visited={len(result['visited'])} | cost={result['total_cost']:.2f}"
                    )
                else:
                    self.event_log.add_line(
                        f"[CH4-A*] visited={len(result['visited'])} | "
                        f"unreachable={len(result['unreachable'])} | "
                        f"cost={result['total_cost']:.2f}"
                    )
            else:
                self.event_log.add_line("[CH4-A*] Routing failed — no civilians reachable")

        self.event_log.add_line(
            f"[STEP {self.current_step:02d}/20] visited={self.stats['visited']} | "
            f"reroutes={self.stats['reroutes']} | cost={self.stats['total_cost']:.1f}"
        )

        # -- STEP 3: Every 5 steps — Intelligence Refresh + Strategic Realignment
        if self.current_step % SIMULATION_SETTINGS['RISK_REFRESH_EVERY'] == 0:
            # Re-select civilians
            self.civilians = self._pick_civilians()
            self.event_log.add_line(
                f"[CH5-ML] Refreshing risk scores (step {self.current_step})..."
            )
            ml_result = run_risk_pipeline(self.city)
            if ml_result:
                self.event_log.add_line(
                    f"[CH5-ML] Risk refreshed | CV: {ml_result['cv_accuracy']:.2f}"
                )
            self.event_log.add_line("[CH3-GA] Repositioning ambulances (warm start)...")
            new_positions = place_ambulances(
                self.city,
                seed_chromosome=list(self.city.ambulance_positions)
            )
            if new_positions:
                self.city.ambulance_positions = new_positions
                self.event_log.add_line("[CH3-GA] Ambulances repositioned")

        # -- STEP 4: Road recovery every 3 steps ------------------------------
        if self.current_step % 3 == 0:
            unblocked = _unblock_random_roads(self.city, self.sim_rng, max_unblocks=2)
            if unblocked > 0:
                self.event_log.add_line(
                    f"[FLOOD] {unblocked} road(s) unblocked (flood receding)"
                )
    
    def run(self):
        """Main game loop."""
        running = True
        while running:
            running = self._handle_events()
            self.animation_frame += 1
            
            # Auto-step simulation when running
            if self.is_running and not self.is_paused and self.current_step < 20:
                pygame.time.wait(600)  # 0.6 seconds per step for comfortable viewing
                self._step_simulation()
            
            # Draw everything
            self.screen.fill(COLORS['BG_PRIMARY'])
            
            # Draw subtle grid lines in background
            for i in range(0, WINDOW_WIDTH, 60):
                pygame.draw.line(self.screen, (20, 30, 55), (i, 0), (i, WINDOW_HEIGHT), 1)
            for i in range(0, WINDOW_HEIGHT, 60):
                pygame.draw.line(self.screen, (20, 30, 55), (0, i), (WINDOW_WIDTH, i), 1)
            
            self._draw_header()
            self._draw_grid_3d()
            self._draw_control_panel()
            self.event_log.draw(self.screen)
            
            # Draw selected cell info bar
            if self.selected_cell:
                info_y = WINDOW_HEIGHT - LOG_HEIGHT - 60
                cell = self.selected_cell
                node = self.city.get_node(cell)
                info_text = f"📍 SELECTED: {self.city.get_label(cell)} | Type: {node['location_type']} | Risk: {node['risk_index']:.2f} | Pop: {node['population_density']:.1f}"
                info_surface = self.font_normal.render(info_text, True, COLORS['TEXT_ACCENT'])
                info_rect = info_surface.get_rect(bottomleft=(GRID_MARGIN_LEFT, info_y))
                # Background for info bar
                pygame.draw.rect(self.screen, COLORS['BG_SECONDARY'], 
                               info_rect.inflate(20, 8), border_radius=8)
                pygame.draw.rect(self.screen, COLORS['BORDER'], 
                               info_rect.inflate(20, 8), width=1, border_radius=8)
                self.screen.blit(info_surface, info_rect.inflate(10, 4))
            
            pygame.display.flip()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

if __name__ == "__main__":
    ui = CityMindUI()
    ui.run()