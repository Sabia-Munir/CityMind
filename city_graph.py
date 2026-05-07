"""
city_graph.py — the shared city graph (phase 0)
================================================
this is the single source of truth for the entire citymind system.
every module (csp, mst, a*, ga, ml) reads from and writes to this one object.
no module is allowed to keep its own separate copy of city data.

grid layout (4-directional connections as stated in design document):
    nodes are identified by (row, col) tuples.
    (0,0) is top-left, (9,9) is bottom-right.
    each node connects to its horizontal and vertical neighbors only.

    (0,0) — (0,1) — (0,2) ... (0,9)
      |       |       |
    (1,0) — (1,1) — (1,2) ... (1,9)
      ...
    (9,0) — (9,1) — (9,2) ... (9,9)

improvements over base version:
    1. realistic population density per location type
    2. smart initial risk index based on location type
    3. human-readable node label stored alongside (row,col) id
    4. validate() method for full graph consistency checking
    5. timestamped and categorized event log with step tracking
"""

import networkx as nx
import math
from collections import deque


# ─────────────────────────────────────────────────────────────────────────────
# constants
# ─────────────────────────────────────────────────────────────────────────────

# all valid location types the csp module can assign to a node
VALID_LOCATION_TYPES = [
    "Residential",
    "Hospital",
    "School",
    "Industrial",
    "PowerPlant",
    "AmbulanceDepot",
    "Empty"
]

# realistic baseline population density per location type.
# hospitals and schools serve large populations so they get high values.
# power plants are mostly automated so they get very low values.
POPULATION_BY_TYPE = {
    "Residential":    8.0,
    "Hospital":       6.0,
    "School":         5.5,
    "Industrial":     3.0,
    "AmbulanceDepot": 2.0,
    "PowerPlant":     1.5,
    "Empty":          0.0
}

# smart initial risk index per location type.
# industrial zones start elevated due to hazards and isolation.
# challenge 5 (ml) will overwrite these with model-predicted values later.
INITIAL_RISK_BY_TYPE = {
    "Residential":    0.3,
    "Hospital":       0.1,
    "School":         0.15,
    "Industrial":     0.5,
    "AmbulanceDepot": 0.1,
    "PowerPlant":     0.4,
    "Empty":          0.0
}

# event category constants used in the structured log
EVENT_FLOOD    = "FLOOD"
EVENT_RESTORE  = "RESTORE"
EVENT_RISK     = "RISK_UPDATE"
EVENT_REROUTE  = "REROUTE"
EVENT_ISOLATE  = "ISOLATE"
EVENT_LAYOUT   = "LAYOUT"
EVENT_SYSTEM   = "SYSTEM"
EVENT_VALIDATE = "VALIDATE"


# ─────────────────────────────────────────────────────────────────────────────
# main class
# ─────────────────────────────────────────────────────────────────────────────

class CityGraph:
    """
    represents the entire city as a weighted undirected graph.

    undirected means travel is possible in both directions on every road.
    weighted means each road has a cost that affects routing decisions.

    all five challenge modules share this single object.
    changes by one module (e.g. ml updating risk) immediately affect
    all other modules (e.g. a* reading effective_cost on next call).

    attributes
    ----------
    rows : int
        number of rows in the grid (default 10)
    cols : int
        number of columns in the grid (default 10)
    graph : networkx.Graph
        the underlying graph storing all node and edge data
    current_simulation_step : int
        tracks which simulation step we are on — used for log timestamps
    event_log : list of dict
        each entry is {"step": int, "category": str, "message": str}
    primary_hospital : tuple or None
        (row, col) of the designated primary hospital — set by challenge 2
    primary_depot : tuple or None
        (row, col) of the designated primary ambulance depot — set by challenge 2
    ambulance_positions : list of tuple
        current positions of the 3 ambulances — set and updated by challenge 3
    """

    def __init__(self, rows=10, cols=10):
        """
        create an empty city grid with the given dimensions.

        parameters
        ----------
        rows : int — number of rows (default 10)
        cols : int — number of columns (default 10)
        """
        self.rows = rows
        self.cols = cols

        # the networkx graph is the core data structure holding all city data
        self.graph = nx.Graph()

        # tracks which simulation step is currently running — used for log timestamps
        self.current_simulation_step = 0

        # structured event log: each entry is a dict with step, category, message
        self.event_log = []

        # set by challenge 2 after the mst road network is built
        self.primary_hospital = None
        self.primary_depot    = None

        # set by challenge 3 after the genetic algorithm places ambulances
        self.ambulance_positions = []

        # build all nodes and connecting edges for the full grid
        self._build_grid()

        self._log(
            EVENT_SYSTEM,
            "citygraph initialised: {}x{} grid, {} nodes, {} edges".format(
                rows, cols, rows * cols, self.graph.number_of_edges()
            )
        )

    # ─────────────────────────────────────────────────────────────────────────
    # private: build the initial grid
    # ─────────────────────────────────────────────────────────────────────────

    def _build_grid(self):
        """
        populate the graph with all nodes and all possible connecting edges.

        step a: one node per grid cell with default attribute values.
        step b: edges between every horizontally and vertically adjacent pair.
                connecting right and down only avoids duplicate edges.

        challenge 2 (mst) will later decide which edges become actual roads
        and will set their final costs.
        """

        # step a — add all nodes with default attribute values
        for row in range(self.rows):
            for col in range(self.cols):
                cell_id = (row, col)

                # human-readable label for ui and event log display
                # e.g. node (3,7) gets label "N(3,7)" until a type is assigned
                readable_label = "N({},{})".format(row, col)

                self.graph.add_node(
                    cell_id,
                    label              = readable_label,
                    location_type      = "Empty",
                    population_density = 0.0,
                    risk_index         = 0.0,
                    is_accessible      = True
                )

        # step b — connect each cell to its right and bottom neighbors only
        for row in range(self.rows):
            for col in range(self.cols):
                current_cell = (row, col)

                # right neighbor: same row, next column
                if col + 1 < self.cols:
                    right_cell = (row, col + 1)
                    self.graph.add_edge(
                        current_cell, right_cell,
                        base_cost = 1.0,
                        blocked   = False
                    )

                # bottom neighbor: next row, same column
                if row + 1 < self.rows:
                    bottom_cell = (row + 1, col)
                    self.graph.add_edge(
                        current_cell, bottom_cell,
                        base_cost = 1.0,
                        blocked   = False
                    )

    # ─────────────────────────────────────────────────────────────────────────
    # read node data
    # ─────────────────────────────────────────────────────────────────────────

    def get_node(self, cell):
        """
        return all stored attributes for a node as a dictionary.

        example return value:
            {
                "label":              "Hospital(2,3)",
                "location_type":      "Hospital",
                "population_density": 6.0,
                "risk_index":         0.1,
                "is_accessible":      True
            }
        """
        return self.graph.nodes[cell]

    def get_label(self, cell):
        """
        return the human-readable label for a node.
        before type assignment: "N(3,7)".
        after type assignment: "Hospital(3,7)".
        used by the ui and event log for clear identification.
        """
        return self.graph.nodes[cell]["label"]

    def get_location_type(self, cell):
        """return the location type string, e.g. "Hospital"."""
        return self.graph.nodes[cell]["location_type"]

    def get_risk_index(self, cell):
        """return the current risk index float (range 0.0 to 1.0)."""
        return self.graph.nodes[cell]["risk_index"]

    def get_population_density(self, cell):
        """return the population density float for a node."""
        return self.graph.nodes[cell]["population_density"]

    def get_open_neighbors(self, cell):
        """
        return a list of neighboring nodes reachable via unblocked roads.
        blocked roads are treated as if they do not exist.
        used by bfs when traversing the graph.
        """
        open_neighbors = []
        for neighbor_cell in self.graph.neighbors(cell):
            road_data = self.graph.edges[cell, neighbor_cell]
            if not road_data["blocked"]:
                open_neighbors.append(neighbor_cell)
        return open_neighbors

    def get_open_neighbors_with_cost(self, cell):
        """
        return a list of (neighbor, effective_cost) tuples for all
        reachable neighbors via unblocked roads.

        used by challenge 3 (ga dijkstra) and challenge 4 (a*) so they
        get risk-weighted costs automatically without reading edge data directly.
        blocked roads are excluded — they produce no entry in the list.

        example:
            for neighbor, cost in city.get_open_neighbors_with_cost((3,4)):
                new_dist = current_dist + cost
        """
        neighbors_with_cost = []
        for neighbor_cell in self.graph.neighbors(cell):
            cost = self.get_effective_cost(cell, neighbor_cell)
            if cost < math.inf:
                neighbors_with_cost.append((neighbor_cell, cost))
        return neighbors_with_cost

    def all_nodes(self):
        """return a list of all (row, col) node ids in the graph."""
        return list(self.graph.nodes)

    def nodes_of_type(self, target_type):
        """
        return all nodes that have a specific location type.

        example:
            all_hospitals = city.nodes_of_type("Hospital")
            all_depots    = city.nodes_of_type("AmbulanceDepot")
        """
        matching_nodes = []
        for cell in self.graph.nodes:
            if self.graph.nodes[cell]["location_type"] == target_type:
                matching_nodes.append(cell)
        return matching_nodes

    # ─────────────────────────────────────────────────────────────────────────
    # write node data
    # ─────────────────────────────────────────────────────────────────────────

    def set_location_type(self, cell, location_type):
        """
        assign a location type to a node.
        called by challenge 1 (csp) when placing buildings on the grid.

        automatically handles 4 side effects:
            1. sets the location_type attribute
            2. sets realistic population_density from POPULATION_BY_TYPE
            3. sets smart initial risk_index from INITIAL_RISK_BY_TYPE
            4. upgrades the label e.g. from "N(2,3)" to "Hospital(2,3)"
            5. updates base_cost on all adjacent edges
               (roads touching residential zones cost 0.8, others 1.0)
        """
        if location_type not in VALID_LOCATION_TYPES:
            raise ValueError("unknown location type '{}'. valid: {}".format(
                location_type, VALID_LOCATION_TYPES
            ))

        row, col = cell

        self.graph.nodes[cell]["location_type"]      = location_type
        self.graph.nodes[cell]["population_density"] = POPULATION_BY_TYPE.get(location_type, 0.0)
        self.graph.nodes[cell]["risk_index"]          = INITIAL_RISK_BY_TYPE.get(location_type, 0.0)

        # upgrade label to include the assigned type for clarity in logs and ui
        self.graph.nodes[cell]["label"] = "{}({},{})".format(location_type, row, col)

        # update road costs for all edges touching this node
        for neighbor_cell in self.graph.neighbors(cell):
            neighbor_type = self.graph.nodes[neighbor_cell]["location_type"]
            if location_type == "Residential" or neighbor_type == "Residential":
                self.graph.edges[cell, neighbor_cell]["base_cost"] = 0.8
            else:
                self.graph.edges[cell, neighbor_cell]["base_cost"] = 1.0

        self._log(
            EVENT_LAYOUT,
            "placed {} at {} | pop={:.1f} | initial_risk={:.2f}".format(
                location_type,
                self.get_label(cell),
                self.graph.nodes[cell]["population_density"],
                self.graph.nodes[cell]["risk_index"]
            )
        )

    def set_population_density(self, cell, density_value):
        """
        manually override the population density for a node.
        set_location_type() handles this automatically in normal use.
        use this only when a specific custom value is needed.
        """
        self.graph.nodes[cell]["population_density"] = float(density_value)

    def update_risk(self, cell, new_risk_value):
        """
        update the crime risk index for a node.
        called by challenge 5 (ml pipeline) every 5 simulation steps.

        because get_effective_cost() reads risk_index live at call time,
        this change immediately affects all routing and ambulance placement.
        no other module needs to be notified.

        the value is clamped to [0.0, 1.0] to protect against ml edge cases.
        """
        clamped_risk = max(0.0, min(1.0, float(new_risk_value)))
        old_risk     = self.graph.nodes[cell]["risk_index"]

        self.graph.nodes[cell]["risk_index"] = clamped_risk

        self._log(
            EVENT_RISK,
            "risk updated at {} | {:.2f} → {:.2f}".format(
                self.get_label(cell), old_risk, clamped_risk
            )
        )

    def set_simulation_step(self, step_number):
        """
        update the simulation step counter.
        called by the simulation loop at the start of every step.
        all log entries after this call will carry this step as their timestamp.
        """
        self.current_simulation_step = step_number

    # ─────────────────────────────────────────────────────────────────────────
    # read edge data
    # ─────────────────────────────────────────────────────────────────────────

    def get_effective_cost(self, cell_a, cell_b):
        """
        compute and return the effective travel cost between two adjacent nodes.

        formula from the design document:
            effective_cost = base_cost x (1 + (risk_a + risk_b) / 2)

        returns math.inf if the road is blocked or does not exist.
        a* and ga always call this — never base_cost directly.
        this is how challenge 5 risk scores automatically affect
        all routing and ambulance placement in challenges 3 and 4.
        """
        if not self.graph.has_edge(cell_a, cell_b):
            return math.inf

        road_data = self.graph.edges[cell_a, cell_b]

        if road_data["blocked"]:
            return math.inf

        road_base_cost = road_data["base_cost"]
        risk_at_a      = self.graph.nodes[cell_a]["risk_index"]
        risk_at_b      = self.graph.nodes[cell_b]["risk_index"]
        average_risk   = (risk_at_a + risk_at_b) / 2.0

        return road_base_cost * (1.0 + average_risk)

    def is_road_blocked(self, cell_a, cell_b):
        """return true if the road between cell_a and cell_b is blocked or missing."""
        if not self.graph.has_edge(cell_a, cell_b):
            return True
        return self.graph.edges[cell_a, cell_b]["blocked"]

    def get_all_edges(self):
        """
        return all edges as a list of (cell_a, cell_b, data_dict) tuples.
        used by challenge 2 (mst) to iterate over all possible roads.
        """
        return list(self.graph.edges(data=True))

    def get_blocked_edges(self):
        """
        Return a list of all blocked edges (tuples of (cell_a, cell_b)).
        Used for flood recovery.
        """
        blocked = []
        for a, b, data in self.graph.edges(data=True):
            if data["blocked"]:
                blocked.append((a, b))
        return blocked

    # ─────────────────────────────────────────────────────────────────────────
    # write edge data — flood events
    # ─────────────────────────────────────────────────────────────────────────

    def block_road(self, cell_a, cell_b):
        """
        mark a road as blocked due to flooding, accident, or disaster.
        called by the simulation loop during environmental perturbations.

        immediately makes get_effective_cost() return math.inf for this edge.
        a* sees the change on its very next path calculation.
        also checks whether either endpoint is now fully isolated.
        """
        if not self.graph.has_edge(cell_a, cell_b):
            self._log(EVENT_SYSTEM, "warning: tried to block non-existent road {} — {}".format(
                cell_a, cell_b
            ))
            return

        self.graph.edges[cell_a, cell_b]["blocked"] = True

        self._log(
            EVENT_FLOOD,
            "road blocked: {} ↔ {} (effective cost now inf)".format(
                self.get_label(cell_a), self.get_label(cell_b)
            )
        )

        # check if either endpoint lost all its open roads
        self._check_and_update_accessibility(cell_a)
        self._check_and_update_accessibility(cell_b)

    def unblock_road(self, cell_a, cell_b):
        """
        Restore a previously blocked road.
        Called during flood recovery events.
        """
        if not self.graph.has_edge(cell_a, cell_b):
            self._log(EVENT_SYSTEM, "warning: tried to unblock non-existent road {} — {}".format(
                cell_a, cell_b
            ))
            return
        
        if self.graph.edges[cell_a, cell_b]["blocked"]:
            self.graph.edges[cell_a, cell_b]["blocked"] = False
            self._log(
                EVENT_RESTORE,
                "road restored: {} ↔ {}".format(
                    self.get_label(cell_a), self.get_label(cell_b)
                )
            )
            # Re-check accessibility for both endpoints
            self._check_and_update_accessibility(cell_a)
            self._check_and_update_accessibility(cell_b)

    def set_base_cost(self, cell_a, cell_b, new_cost):
        """
        set the base construction cost of a road.
        called by challenge 2 (mst) when finalising the road network.
        """
        if self.graph.has_edge(cell_a, cell_b):
            self.graph.edges[cell_a, cell_b]["base_cost"] = float(new_cost)

    def _check_and_update_accessibility(self, cell):
        """
        check whether a node still has at least one unblocked road.
        if all roads are blocked the node is isolated — mark it inaccessible.
        challenge 4 uses this to skip civilians who cannot be reached.
        """
        has_any_open_road = any(
            not self.graph.edges[cell, neighbor]["blocked"]
            for neighbor in self.graph.neighbors(cell)
        )
        was_accessible = self.graph.nodes[cell]["is_accessible"]
        self.graph.nodes[cell]["is_accessible"] = has_any_open_road

        if was_accessible and not has_any_open_road:
            self._log(
                EVENT_ISOLATE,
                "node {} is now isolated — all connecting roads are blocked".format(
                    self.get_label(cell)
                )
            )

    # ─────────────────────────────────────────────────────────────────────────
    # utility: bfs hop counting
    # ─────────────────────────────────────────────────────────────────────────

    def bfs_hops(self, start_cell, goal_cell):
        """
        return the number of road hops between two nodes using bfs.
        only traverses unblocked roads.

        used by challenge 1 (csp) to verify layout constraints:
            - every residential node must be within 3 hops of a hospital
            - every power plant must be within 2 hops of an industrial zone

        returns math.inf if no path exists.
        """
        if start_cell == goal_cell:
            return 0

        visited_cells = {start_cell}
        bfs_queue     = deque([(start_cell, 0)])  # (current cell, hops taken so far)

        while bfs_queue:
            current_cell, hops_so_far = bfs_queue.popleft()

            for neighbor_cell in self.graph.neighbors(current_cell):
                if neighbor_cell in visited_cells:
                    continue

                road_data = self.graph.edges[current_cell, neighbor_cell]
                if road_data["blocked"]:
                    continue

                if neighbor_cell == goal_cell:
                    return hops_so_far + 1

                visited_cells.add(neighbor_cell)
                bfs_queue.append((neighbor_cell, hops_so_far + 1))

        return math.inf

    def shortest_hop_to_type(self, start_cell, target_type):
        """
        find the minimum hop count from start_cell to the nearest
        node of the given location type.

        example:
            hops = city.shortest_hop_to_type((4, 2), "Hospital")

        returns math.inf if no reachable node of that type exists.
        """
        minimum_hops = math.inf
        for candidate_cell in self.nodes_of_type(target_type):
            hop_count = self.bfs_hops(start_cell, candidate_cell)
            if hop_count < minimum_hops:
                minimum_hops = hop_count
        return minimum_hops

    # ─────────────────────────────────────────────────────────────────────────
    # utility: geometry helpers
    # ─────────────────────────────────────────────────────────────────────────

    def euclidean_distance(self, cell_a, cell_b):
        """
        straight-line distance between two grid cells.
        used by challenge 4 (a*) as its admissible heuristic.

        a* applies h(n) = euclidean_distance(n, goal) x 0.8 because
        0.8 is the minimum possible edge cost (residential roads).
        this guarantees the heuristic never overestimates the true cost.
        """
        row_diff = cell_a[0] - cell_b[0]
        col_diff = cell_a[1] - cell_b[1]
        return math.sqrt(row_diff ** 2 + col_diff ** 2)

    def get_pixel_center(self, cell, cell_size=56, margin=20):
        """
        convert a (row, col) node id to pixel screen coordinates.
        used by the pygame ui to position cells and draw roads correctly.

        parameters
        ----------
        cell      : tuple — (row, col)
        cell_size : int   — pixel size of each grid cell (default 56px)
        margin    : int   — pixel border around the grid canvas (default 20px)
        """
        row, col = cell
        pixel_x  = margin + col * cell_size + cell_size // 2
        pixel_y  = margin + row * cell_size + cell_size // 2
        return (pixel_x, pixel_y)

    def is_valid_cell(self, cell):
        """return true if (row, col) is within the grid boundaries."""
        row, col = cell
        return 0 <= row < self.rows and 0 <= col < self.cols

    # ─────────────────────────────────────────────────────────────────────────
    # validation — full consistency check for the entire graph
    # ─────────────────────────────────────────────────────────────────────────

    def validate(self):
        """
        run a complete consistency check on the city graph.

        checks performed:
            1. total node count matches rows x cols
            2. all nodes have valid location types
            3. all risk values are within [0.0, 1.0]
            4. all population values are non-negative
            5. all edge base costs are positive
            6. node labels contain the correct (row, col) coordinates
            7. is_accessible flags match the actual road state

        called after each major operation (layout, road building, risk update)
        and during the viva to demonstrate graph integrity live.

        returns
        -------
        dict with:
            "passed"   : bool        — true if zero errors found
            "errors"   : list of str — critical problems
            "warnings" : list of str — non-critical notices
        """
        found_errors   = []
        found_warnings = []

        # check 1: correct total node count
        expected_node_count = self.rows * self.cols
        actual_node_count   = self.graph.number_of_nodes()
        if actual_node_count != expected_node_count:
            found_errors.append(
                "node count: expected {} but found {}".format(
                    expected_node_count, actual_node_count
                )
            )

        # checks 2, 3, 4, 6, 7: validate each node individually
        for cell in self.graph.nodes:
            node_data     = self.graph.nodes[cell]
            node_label    = node_data.get("label", "unknown")
            location_type = node_data.get("location_type", None)
            risk_value    = node_data.get("risk_index", None)
            population    = node_data.get("population_density", None)
            is_accessible = node_data.get("is_accessible", None)

            # check 2: location type must be one of the valid options
            if location_type not in VALID_LOCATION_TYPES:
                found_errors.append(
                    "{} has invalid location type '{}'".format(node_label, location_type)
                )

            # check 3: risk index must be within 0.0 to 1.0
            if risk_value is not None and not (0.0 <= risk_value <= 1.0):
                found_errors.append(
                    "{} has out-of-range risk index {:.3f}".format(node_label, risk_value)
                )

            # check 4: population density cannot be negative
            if population is not None and population < 0:
                found_errors.append(
                    "{} has negative population {:.2f}".format(node_label, population)
                )

            # check 6: label must contain the correct coordinates
            row, col               = cell
            expected_coord_suffix  = "({},{})".format(row, col)
            if expected_coord_suffix not in node_label:
                found_errors.append(
                    "label '{}' does not match position {}".format(node_label, cell)
                )

            # check 7: is_accessible must reflect actual open road count
            actual_open_road_count   = sum(
                1 for nb in self.graph.neighbors(cell)
                if not self.graph.edges[cell, nb]["blocked"]
            )
            correct_accessibility = actual_open_road_count > 0
            if is_accessible != correct_accessibility:
                found_errors.append(
                    "{} accessibility flag is stale: stored={} but should be {}".format(
                        node_label, is_accessible, correct_accessibility
                    )
                )

        # check 5: all edge costs must be positive
        for cell_a, cell_b, road_data in self.graph.edges(data=True):
            base_cost = road_data.get("base_cost", None)
            if base_cost is not None and base_cost <= 0:
                found_errors.append(
                    "road {} — {} has non-positive base cost {:.3f}".format(
                        cell_a, cell_b, base_cost
                    )
                )

        # warning if more than half the nodes are still empty
        empty_node_count = len(self.nodes_of_type("Empty"))
        total_nodes      = self.rows * self.cols
        if empty_node_count > total_nodes * 0.5:
            found_warnings.append(
                "{}/{} nodes still empty — challenge 1 may not have run yet".format(
                    empty_node_count, total_nodes
                )
            )

        # warning if primary hospital or depot not set yet
        if self.primary_hospital is None:
            found_warnings.append("primary hospital not set — challenge 2 not yet run")
        if self.primary_depot is None:
            found_warnings.append("primary depot not set — challenge 2 not yet run")

        all_checks_passed = len(found_errors) == 0

        self._log(
            EVENT_VALIDATE,
            "validation {} | {} errors | {} warnings".format(
                "passed" if all_checks_passed else "FAILED",
                len(found_errors),
                len(found_warnings)
            )
        )

        return {
            "passed":   all_checks_passed,
            "errors":   found_errors,
            "warnings": found_warnings
        }

    # ─────────────────────────────────────────────────────────────────────────
    # event log — timestamped and categorized
    # ─────────────────────────────────────────────────────────────────────────

    def _log(self, category, message):
        """
        append a structured entry to the event log.

        every entry records:
            - current simulation step (timestamp)
            - event category (flood, risk_update, reroute, etc.)
            - human-readable message

        the pygame ui reads get_log_as_strings() to display the event log panel.
        categories allow the ui to filter or color-code entries by type.
        """
        log_entry = {
            "step":     self.current_simulation_step,
            "category": category,
            "message":  message
        }
        self.event_log.append(log_entry)

        print("[step {:02d}] [{:10s}] {}".format(
            self.current_simulation_step, category, message
        ))

    def log_reroute(self, old_path, new_path):
        """
        log a reroute event when a* recalculates a path after a flood.
        called by challenge 4 whenever the active route changes mid-journey.

        parameters
        ----------
        old_path : list of tuples — the path before the road was blocked
        new_path : list of tuples — the new path calculated after blocking
        """
        old_label_path = " → ".join(self.get_label(cell) for cell in old_path)
        new_label_path = " → ".join(self.get_label(cell) for cell in new_path)
        self._log(
            EVENT_REROUTE,
            "rerouted | old: {} | new: {}".format(old_label_path, new_label_path)
        )

    def get_log(self):
        """return the full event log as a list of dicts."""
        return self.event_log

    def get_log_by_category(self, category):
        """
        return only log entries of a specific category.
        example: city.get_log_by_category("FLOOD") returns all flood events.
        useful for ui filtering and post-simulation analysis.
        """
        return [entry for entry in self.event_log if entry["category"] == category]

    def get_log_as_strings(self):
        """
        return the event log as a list of formatted strings.
        this is what the pygame scrollable event log panel displays.

        example output:
            "[step 07] [FLOOD     ] road blocked: Hospital(2,3) — N(2,4)"
            "[step 07] [REROUTE   ] rerouted | old: ... | new: ..."
        """
        formatted_lines = []
        for entry in self.event_log:
            line = "[step {:02d}] [{:10s}] {}".format(
                entry["step"], entry["category"], entry["message"]
            )
            formatted_lines.append(line)
        return formatted_lines

    def clear_log(self):
        """clear the event log. useful when restarting the simulation."""
        self.event_log = []

    # ─────────────────────────────────────────────────────────────────────────
    # debug: print the grid to terminal
    # ─────────────────────────────────────────────────────────────────────────

    def print_grid(self):
        """
        print the city grid as a readable text map in the terminal.
        each cell shows a 3-letter abbreviation of its location type.
        """
        type_abbreviations = {
            "Empty":          "Emt",
            "Residential":    "Res",
            "Hospital":       "Hos",
            "School":         "Sch",
            "Industrial":     "Ind",
            "PowerPlant":     "Pwr",
            "AmbulanceDepot": "Dep",
        }
        print("\n── city grid ──────────────────────────────────────")
        for row in range(self.rows):
            row_display = ""
            for col in range(self.cols):
                cell_type    = self.graph.nodes[(row, col)]["location_type"]
                abbreviation = type_abbreviations.get(cell_type, "???")
                row_display += abbreviation + " "
            print(row_display)
        print("────────────────────────────────────────────────────\n")

    def print_risk_grid(self):
        """
        print a grid showing risk level at each node.
        h = high (>= 0.65), m = medium (0.35 to 0.65), . = low (< 0.35)
        """
        print("\n── risk grid ───────────────────────────────────────")
        for row in range(self.rows):
            row_display = ""
            for col in range(self.cols):
                risk_value = self.graph.nodes[(row, col)]["risk_index"]
                if risk_value >= 0.65:
                    row_display += "H "
                elif risk_value >= 0.35:
                    row_display += "M "
                else:
                    row_display += ". "
            print(row_display)
        print("────────────────────────────────────────────────────\n")

    def print_population_grid(self):
        """
        print a grid showing population density at each node.
        shows a single rounded integer per cell for readability.
        """
        print("\n── population density grid ─────────────────────────")
        for row in range(self.rows):
            row_display = ""
            for col in range(self.cols):
                pop_value = self.graph.nodes[(row, col)]["population_density"]
                row_display += "{:.0f} ".format(pop_value)
            print(row_display)
        print("────────────────────────────────────────────────────\n")
        
    def verify_hospital_depot_redundancy(self):
        """
        Verify that there are two edge-disjoint paths between primary hospital and depot.
        Returns (bool, connectivity_value, message)
        """
        if self.primary_hospital is None or self.primary_depot is None:
            return False, 0, "primary hospital or depot not set"
        
        try:
            # Create temporary graph with only unblocked edges
            import networkx as nx
            temp_graph = nx.Graph()
            for cell in self.all_nodes():
                temp_graph.add_node(cell)
            for u, v, data in self.get_all_edges():
                if not data["blocked"]:
                    temp_graph.add_edge(u, v, weight=data["base_cost"])
            
            # Check edge connectivity
            conn = nx.edge_connectivity(temp_graph, self.primary_hospital, self.primary_depot)
            
            if conn >= 2:
                self._log("SYSTEM", "redundancy verified: {} independent paths between hospital and depot".format(conn))
                return True, conn, "OK - {} independent paths".format(conn)
            else:
                self._log("SYSTEM", "WARNING: only {} path between hospital and depot".format(conn))
                return False, conn, "WARNING: only {} path(s) - redundancy missing".format(conn)
        except Exception as e:
            return False, 0, "verification error: {}".format(str(e))

    def summary(self):
        """
        print a full summary of the current city graph state.
        automatically runs validate() and reports any problems found.
        call this anytime during development for a sanity check.
        """
        print("\n═══ citygraph summary ═══════════════════════════════")
        print("  grid size         : {}×{}".format(self.rows, self.cols))
        print("  total nodes       : {}".format(self.graph.number_of_nodes()))
        print("  total edges       : {}".format(self.graph.number_of_edges()))
        print("  simulation step   : {}".format(self.current_simulation_step))

        # count each location type across all nodes
        type_counts = {}
        for cell in self.graph.nodes:
            cell_type              = self.graph.nodes[cell]["location_type"]
            type_counts[cell_type] = type_counts.get(cell_type, 0) + 1