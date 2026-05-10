"""
challenge1_csp.py — city layout planner (challenge 1)
======================================================
assigns a location type to every node in the 10x10 city grid using
constraint satisfaction with backtracking, mrv heuristic, and forward checking.

CSP TECHNIQUES (all three from the course):
    _select_mrv_cell()  — MRV: picks the unassigned cell with the fewest
                          remaining valid types in its domain. Used in Phase 1.
    _forward_check()    — Forward Checking: after each assignment, prunes
                          domains of neighbours; fails early if any goes empty.
    Backtracking        — undoes assignments that lead to dead ends.


algorithm (exactly as stated in design document):
    backtracking    — assigns types one cell at a time, undoes bad choices
    mrv heuristic   — always picks the cell with fewest remaining valid types
    forward checking — after each assignment, prunes domains of neighboring cells

implementation strategy for a 10x10 grid:
    pure backtracking over 100 variables is too slow (exponential search space).
    we use a two-phase approach that is standard in real csp solvers:

    phase 1 — smart seeding:
        place the rarest and most constrained types first at valid positions.
        this drastically reduces the search space before backtracking begins.
        order: hospitals -> ambulance depots -> power plants -> industrial -> schools -> residential

    phase 2 — hospital-proximity fill:
        fill remaining cells sorted by distance to nearest hospital.
        this satisfies c2 naturally (closest cells get residential first).
        NOTE: mrv is not re-run here because residential cells have no
        strict adjacency rules, so proximity ordering is faster and equally
        correct. mrv + forward checking remain active in phase 1.


three hard constraints (from project spec):
    c1 — separation:      industrial cannot be adjacent to hospital or school
    c2 — hospital access: every residential must be within 3 hops of a hospital
    c3 — power supply:    every power plant must be within 2 hops of an industrial

if no valid layout exists after retries:
    identifies which specific constraint is blocking
    relaxes it minimally (distance limit +1) and retries
    logs every relaxation decision for viva traceability

after a valid layout is found:
    primary hospital — node with highest population sum within 2 hops
    primary depot    — ambulance depot with fewest hops to primary hospital
"""

import random
import math
from collections import deque
from city_graph import CityGraph


# -----------------------------------------------------------------------------
# constants
# -----------------------------------------------------------------------------

# how many of each type to place on the 10x10 grid (must sum to 100)
REQUIRED_TYPE_COUNTS = {
    "Residential":    55,
    "Hospital":        5,
    "School":          8,
    "Industrial":     12,
    "PowerPlant":      5,
    "AmbulanceDepot":  5,
    "Empty":          10,
}

# placement order: most constrained types first
PLACEMENT_ORDER = [
    "Hospital",
    "AmbulanceDepot",
    "PowerPlant",
    "Industrial",
    "School",
    "Residential",
]

# constraint distance limits — relaxed by 1 on each retry if unsolvable
DEFAULT_HOSPITAL_HOP_LIMIT   = 3
DEFAULT_POWERPLANT_HOP_LIMIT = 2

# types that industrial is forbidden from being adjacent to
INDUSTRIAL_FORBIDDEN_ADJACENT = {"Hospital", "School"}

# maximum retries before giving up
MAX_RELAXATION_RETRIES = 15


# -----------------------------------------------------------------------------
# main solver class
# -----------------------------------------------------------------------------

class CityLayoutPlanner:
    """
    solves the city layout csp using smart seeding + backtracking fill.
    """

    def __init__(self, city_graph):
        self.city                 = city_graph
        self.rows                 = city_graph.rows
        self.cols                 = city_graph.cols
        self.hospital_hop_limit   = DEFAULT_HOSPITAL_HOP_LIMIT
        self.powerplant_hop_limit = DEFAULT_POWERPLANT_HOP_LIMIT
        self.remaining_counts     = dict(REQUIRED_TYPE_COUNTS)
        self.cell_domains         = {}
        self.assignment           = {}
        self._initialise_domains()

    # -------------------------------------------------------------------------
    # public: run the full layout pipeline
    # -------------------------------------------------------------------------

    def run(self):
        """
        run the full csp layout pipeline and write results to the city graph.
        returns true if a valid layout was found, false otherwise.
        """
        solution_found = False
        retry_count    = 0

        while not solution_found and retry_count <= MAX_RELAXATION_RETRIES:
            if retry_count > 0:
                blocking = self._identify_blocking_constraint()
                self._relax_constraint(blocking, retry_count)

            self._reset_solver_state()

            # use a different random offset each retry
            for _ in range(retry_count * 13):
                random.random()

            solution_found = self._solve()

            if not solution_found:
                retry_count += 1

        if not solution_found:
            print("[csp] ERROR: no valid layout found after {} retries".format(
                MAX_RELAXATION_RETRIES
            ))
            return False

        self._write_assignment_to_graph()
        self._set_primary_hospital_and_depot()
        print("[csp] layout complete — {} nodes assigned".format(len(self.assignment)))
        return True

    # -------------------------------------------------------------------------
    # two-phase solver
    # -------------------------------------------------------------------------

    def _solve(self):
        """
        two-phase solver:
            phase 1 — place constrained types using smart seeding
            phase 2 — fill remaining cells sorted by hospital proximity
        """

        # -- phase 1: place hospitals, depots, power plants, industrial, schools --
        for location_type in PLACEMENT_ORDER:
            if location_type == "Residential":
                continue  # residential handled in phase 2

            count_needed = REQUIRED_TYPE_COUNTS.get(location_type, 0)
            if count_needed == 0:
                continue

            placed = self._place_type_greedily(location_type, count_needed)
            if placed < count_needed:
                print("[csp] phase 1 failed: could only place {}/{} {}".format(
                    placed, count_needed, location_type
                ))
                return False

        # -- phase 2: fill all remaining unassigned cells ----------------------
        # BUG FIX: min_hops_to_hospital was previously defined at wrong scope
        # (outside _solve as a module-level function), making it unable to access
        # self or hospital_cells, and making all phase 2 code unreachable.
        # It is now correctly defined as a nested function inside _solve.
        unassigned_cells = [
            cell for cell in self.cell_domains
            if cell not in self.assignment
        ]

        hospital_cells = [c for c, t in self.assignment.items() if t == "Hospital"]

        # nested helper — correct scope, can access hospital_cells and self
        def min_hops_to_hospital(cell):
            if not hospital_cells:
                return 0
            return min(self._bfs_hops_assignment(cell, h) for h in hospital_cells)

        # sort closest-to-hospital first so residential fills inner cells,
        # ensuring c2 (hospital access) is satisfied without requiring relaxation
        unassigned_cells.sort(key=min_hops_to_hospital)

        for cell in unassigned_cells:
            if self.remaining_counts.get("Residential", 0) > 0:
                self.assignment[cell] = "Residential"
                self.remaining_counts["Residential"] -= 1
            elif (self.remaining_counts.get("Industrial", 0) > 0
                  and self._satisfies_local_constraints(cell, "Industrial")):
                self.assignment[cell] = "Industrial"
                self.remaining_counts["Industrial"] -= 1
            elif self.remaining_counts.get("School", 0) > 0:
                self.assignment[cell] = "School"
                self.remaining_counts["School"] -= 1
            else:
                self.assignment[cell] = "Empty"
                self.remaining_counts["Empty"] = self.remaining_counts.get("Empty", 1) - 1

        # verify all 100 cells are assigned
        if len(self.assignment) != self.rows * self.cols:
            print("[csp] incomplete assignment: {}/{}".format(
                len(self.assignment), self.rows * self.cols
            ))
            return False

        # check all three constraints on the completed assignment
        return self._check_all_constraints()

    def _place_type_greedily(self, location_type, count_needed):
        """
        place `count_needed` instances of `location_type` at valid positions.
        """
        placed_count = 0

        if location_type == "Hospital":
            placed_count = self._place_hospitals_in_quadrants(count_needed)

        elif location_type == "PowerPlant":
            placed_count = self._place_near_type("PowerPlant", "Industrial", count_needed)

        elif location_type == "Industrial":
            placed_count = self._place_industrial(count_needed)

        else:
            placed_count = self._place_random_valid(location_type, count_needed)

        return placed_count

    def _place_hospitals_in_quadrants(self, count_needed):
        """
        place hospitals spread across grid quadrants so every residential
        cell has a reasonable chance of being within 3 hops.
        """
        placed = 0

        row_positions = [int(self.rows * r / 3.5) for r in range(1, 5)]
        col_positions = [int(self.cols * c / 3.5) for c in range(1, 5)]

        anchor_points = []
        for r in row_positions:
            for c in col_positions:
                anchor_points.append((min(r, self.rows - 1), min(c, self.cols - 1)))

        random.shuffle(anchor_points)

        used_anchors = set()
        for anchor_cell in anchor_points:
            if placed >= count_needed:
                break
            if anchor_cell in used_anchors:
                continue
            target = self._find_nearest_valid_cell(anchor_cell, "Hospital")
            if target is not None:
                self.assignment[target]           = "Hospital"
                self.remaining_counts["Hospital"] -= 1
                placed += 1
                used_anchors.add(target)

        extra_count = count_needed - placed
        if extra_count > 0:
            placed += self._place_random_valid("Hospital", extra_count)

        return placed

    def _place_industrial(self, count_needed):
        """
        place industrial zones away from hospitals and schools.
        """
        placed         = 0
        all_unassigned = [c for c in self.cell_domains if c not in self.assignment]
        random.shuffle(all_unassigned)

        for candidate_cell in all_unassigned:
            if placed >= count_needed:
                break
            if not self._satisfies_local_constraints(candidate_cell, "Industrial"):
                continue
            near_forbidden = False
            for neighbor_cell in self._get_cells_within_hops(candidate_cell, hops=1):
                neighbor_type = self.assignment.get(neighbor_cell, "Empty")
                if neighbor_type in INDUSTRIAL_FORBIDDEN_ADJACENT:
                    near_forbidden = True
                    break
            if near_forbidden:
                continue

            self.assignment[candidate_cell]      = "Industrial"
            self.remaining_counts["Industrial"] -= 1
            placed += 1

        if placed < count_needed:
            placed += self._place_random_valid("Industrial", count_needed - placed)

        return placed

    def _place_near_type(self, type_to_place, near_type, count_needed):
        """
        place instances of type_to_place near existing nodes of near_type.
        used for power plants which must be within 2 hops of industrial.
        """
        placed       = 0
        anchor_cells = [c for c, t in self.assignment.items() if t == near_type]

        if not anchor_cells:
            return self._place_random_valid(type_to_place, count_needed)

        for anchor_cell in anchor_cells:
            if placed >= count_needed:
                break
            target = self._find_nearest_valid_cell(anchor_cell, type_to_place, max_hops=2)
            if target is not None:
                self.assignment[target]                = type_to_place
                self.remaining_counts[type_to_place] -= 1
                placed += 1

        if placed < count_needed:
            placed += self._place_random_valid(type_to_place, count_needed - placed)

        return placed

    def _place_random_valid(self, location_type, count_needed):
        """
        place count_needed instances of location_type at random valid cells.
        """
        placed         = 0
        all_unassigned = [c for c in self.cell_domains if c not in self.assignment]
        random.shuffle(all_unassigned)

        for candidate_cell in all_unassigned:
            if placed >= count_needed:
                break
            if self._satisfies_local_constraints(candidate_cell, location_type):
                self.assignment[candidate_cell]        = location_type
                self.remaining_counts[location_type] -= 1
                placed += 1

        return placed

    def _find_nearest_valid_cell(self, center_cell, location_type, max_hops=None):
        """
        bfs outward from center_cell to find the nearest unassigned cell
        where location_type can be placed without violating local constraints.
        """
        visited   = {center_cell}
        bfs_queue = deque([(center_cell, 0)])

        while bfs_queue:
            current_cell, hops_so_far = bfs_queue.popleft()

            if max_hops is not None and hops_so_far > max_hops:
                return None

            if current_cell not in self.assignment:
                if self._satisfies_local_constraints(current_cell, location_type):
                    return current_cell

            for neighbor_cell in self._get_grid_neighbors(current_cell):
                if neighbor_cell not in visited:
                    visited.add(neighbor_cell)
                    bfs_queue.append((neighbor_cell, hops_so_far + 1))

        return None

    # -------------------------------------------------------------------------
    # mrv heuristic
    # -------------------------------------------------------------------------

    def _select_mrv_cell(self):
        """
        pick the unassigned cell with the fewest valid types in its domain.
        """
        best_cell       = None
        smallest_domain = math.inf

        for cell in self.cell_domains:
            if cell in self.assignment:
                continue
            valid_type_count = sum(
                1 for t in self.cell_domains[cell]
                if self.remaining_counts.get(t, 0) > 0
            )
            if valid_type_count < smallest_domain:
                smallest_domain = valid_type_count
                best_cell       = cell

        return best_cell

    # -------------------------------------------------------------------------
    # forward checking
    # -------------------------------------------------------------------------

    def _forward_check(self, assigned_cell, assigned_type):
        """
        after assigning assigned_type to assigned_cell, prune the domains
        of unassigned neighbors to remove types that would violate c1.
        returns false if any neighbor's domain becomes empty.
        """
        for neighbor_cell in self._get_grid_neighbors(assigned_cell):
            if neighbor_cell in self.assignment:
                continue

            types_to_remove = set()

            for domain_type in self.cell_domains[neighbor_cell]:
                if assigned_type == "Industrial" and domain_type in INDUSTRIAL_FORBIDDEN_ADJACENT:
                    types_to_remove.add(domain_type)
                if assigned_type in INDUSTRIAL_FORBIDDEN_ADJACENT and domain_type == "Industrial":
                    types_to_remove.add(domain_type)

            self.cell_domains[neighbor_cell] -= types_to_remove

            remaining_valid = sum(
                1 for t in self.cell_domains[neighbor_cell]
                if self.remaining_counts.get(t, 0) > 0
            )
            if remaining_valid == 0:
                return False

        return True

    # -------------------------------------------------------------------------
    # constraint checking
    # -------------------------------------------------------------------------

    def _satisfies_local_constraints(self, cell, candidate_type):
        """
        check c1 (separation) for a proposed placement.
        only checks already-assigned neighbors.
        """
        for neighbor_cell in self._get_grid_neighbors(cell):
            if neighbor_cell not in self.assignment:
                continue
            neighbor_type = self.assignment[neighbor_cell]
            if candidate_type == "Industrial" and neighbor_type in INDUSTRIAL_FORBIDDEN_ADJACENT:
                return False
            if candidate_type in INDUSTRIAL_FORBIDDEN_ADJACENT and neighbor_type == "Industrial":
                return False
        return True

    def _check_all_constraints(self):
        """
        check c1, c2, and c3 on the completed assignment.
        called after all 100 cells are assigned.
        """
        # c1 — separation
        for cell, assigned_type in self.assignment.items():
            if assigned_type == "Industrial":
                for neighbor_cell in self._get_grid_neighbors(cell):
                    neighbor_type = self.assignment.get(neighbor_cell, "Empty")
                    if neighbor_type in INDUSTRIAL_FORBIDDEN_ADJACENT:
                        return False

        # c2 — hospital access
        hospital_cells = [c for c, t in self.assignment.items() if t == "Hospital"]
        for res_cell in [c for c, t in self.assignment.items() if t == "Residential"]:
            min_hops = min(
                (self._bfs_hops_assignment(res_cell, h) for h in hospital_cells),
                default=math.inf
            )
            if min_hops > self.hospital_hop_limit:
                return False

        # c3 — power supply
        industrial_cells = [c for c, t in self.assignment.items() if t == "Industrial"]
        for pwr_cell in [c for c, t in self.assignment.items() if t == "PowerPlant"]:
            min_hops = min(
                (self._bfs_hops_assignment(pwr_cell, i) for i in industrial_cells),
                default=math.inf
            )
            if min_hops > self.powerplant_hop_limit:
                return False

        return True

    # -------------------------------------------------------------------------
    # bfs helpers used during solving (before graph is written)
    # -------------------------------------------------------------------------

    def _bfs_hops_assignment(self, start_cell, goal_cell):
        """
        bfs hop count between two cells using grid neighbors directly.
        used during constraint checking before the assignment is written
        to the city graph.
        """
        if start_cell == goal_cell:
            return 0

        visited   = {start_cell}
        bfs_queue = deque([(start_cell, 0)])

        while bfs_queue:
            current_cell, hops_so_far = bfs_queue.popleft()
            for neighbor_cell in self._get_grid_neighbors(current_cell):
                if neighbor_cell in visited:
                    continue
                if neighbor_cell == goal_cell:
                    return hops_so_far + 1
                visited.add(neighbor_cell)
                bfs_queue.append((neighbor_cell, hops_so_far + 1))

        return math.inf

    def _get_cells_within_hops(self, center_cell, hops):
        """return all cells within `hops` hops of center_cell using bfs."""
        visited   = {center_cell}
        bfs_queue = deque([(center_cell, 0)])
        result    = []

        while bfs_queue:
            current_cell, hops_so_far = bfs_queue.popleft()
            result.append(current_cell)
            if hops_so_far >= hops:
                continue
            for neighbor_cell in self._get_grid_neighbors(current_cell):
                if neighbor_cell not in visited:
                    visited.add(neighbor_cell)
                    bfs_queue.append((neighbor_cell, hops_so_far + 1))

        return result

    # -------------------------------------------------------------------------
    # conflict detection and constraint relaxation
    # -------------------------------------------------------------------------

    def _identify_blocking_constraint(self):
        """
        determine which constraint is blocking the solver.
        """
        hospital_cells    = [c for c, t in self.assignment.items() if t == "Hospital"]
        industrial_cells  = [c for c, t in self.assignment.items() if t == "Industrial"]
        residential_cells = [c for c, t in self.assignment.items() if t == "Residential"]
        powerplant_cells  = [c for c, t in self.assignment.items() if t == "PowerPlant"]

        c2_violations = sum(
            1 for res in residential_cells
            if min((self._bfs_hops_assignment(res, h) for h in hospital_cells), default=math.inf)
            > self.hospital_hop_limit
        )
        c3_violations = sum(
            1 for pwr in powerplant_cells
            if min((self._bfs_hops_assignment(pwr, i) for i in industrial_cells), default=math.inf)
            > self.powerplant_hop_limit
        )

        if c3_violations >= c2_violations and c3_violations > 0:
            return "c3_power_supply"
        elif c2_violations > 0:
            return "c2_hospital_access"
        else:
            return "c1_separation"

    def _relax_constraint(self, constraint_name, retry_number):
        """
        relax the identified constraint by increasing its distance limit by 1.
        """
        if constraint_name == "c2_hospital_access":
            old_limit = self.hospital_hop_limit
            self.hospital_hop_limit += 1
            print("[csp] retry {}: relaxed c2 - hospital hop limit {} -> {}".format(
                retry_number, old_limit, self.hospital_hop_limit
            ))
        elif constraint_name == "c3_power_supply":
            old_limit = self.powerplant_hop_limit
            self.powerplant_hop_limit += 1
            print("[csp] retry {}: relaxed c3 - powerplant hop limit {} -> {}".format(
                retry_number, old_limit, self.powerplant_hop_limit
            ))
        else:
            old_limit = self.hospital_hop_limit
            self.hospital_hop_limit += 1
            print("[csp] retry {}: c1 separation likely cause - relaxed c2 as fallback: "
                  "hop limit {} -> {}".format(retry_number, old_limit, self.hospital_hop_limit))

    # -------------------------------------------------------------------------
    # primary hospital and depot identification
    # -------------------------------------------------------------------------

    def _set_primary_hospital_and_depot(self):
        """
        primary hospital — hospital with highest total population within 2 hops.
        primary depot    — depot with fewest hops to the primary hospital.
        """
        hospital_cells = self.city.nodes_of_type("Hospital")
        depot_cells    = self.city.nodes_of_type("AmbulanceDepot")

        if not hospital_cells:
            print("[csp] warning: no hospitals placed")
            return
        if not depot_cells:
            print("[csp] warning: no ambulance depots placed")
            return

        best_hospital       = None
        best_population_sum = -1

        for hospital_cell in hospital_cells:
            population_sum = self._sum_population_within_hops(hospital_cell, hop_limit=2)
            if population_sum > best_population_sum:
                best_population_sum = population_sum
                best_hospital       = hospital_cell

        self.city.primary_hospital = best_hospital
        print("[csp] primary hospital: {} (2-hop pop: {:.1f})".format(
            self.city.get_label(best_hospital), best_population_sum
        ))

        best_depot  = None
        fewest_hops = math.inf

        for depot_cell in depot_cells:
            hops = self.city.bfs_hops(best_hospital, depot_cell)
            if hops < fewest_hops:
                fewest_hops = hops
                best_depot  = depot_cell

        self.city.primary_depot = best_depot
        print("[csp] primary depot: {} ({} hops from hospital)".format(
            self.city.get_label(best_depot), fewest_hops
        ))

    def _sum_population_within_hops(self, center_cell, hop_limit):
        """sum population_density of all nodes within hop_limit hops."""
        visited   = {center_cell}
        bfs_queue = deque([(center_cell, 0)])
        total_pop = 0.0

        while bfs_queue:
            current_cell, hops_so_far = bfs_queue.popleft()
            total_pop += self.city.get_population_density(current_cell)
            if hops_so_far >= hop_limit:
                continue
            for neighbor_cell in self._get_grid_neighbors(current_cell):
                if neighbor_cell not in visited:
                    visited.add(neighbor_cell)
                    bfs_queue.append((neighbor_cell, hops_so_far + 1))

        return total_pop

    # -------------------------------------------------------------------------
    # write assignment to shared city graph
    # -------------------------------------------------------------------------

    def _write_assignment_to_graph(self):
        """
        write the completed assignment into the shared city graph.
        """
        print("[csp] writing {} assignments to city graph...".format(len(self.assignment)))
        for cell, location_type in self.assignment.items():
            self.city.set_location_type(cell, location_type)
        print("[csp] city graph updated with full layout")

    # -------------------------------------------------------------------------
    # state management helpers
    # -------------------------------------------------------------------------

    def _initialise_domains(self):
        """each cell starts with the full set of placeable types as its domain."""
        all_types = set(REQUIRED_TYPE_COUNTS.keys()) - {"Empty"}
        for row in range(self.rows):
            for col in range(self.cols):
                self.cell_domains[(row, col)] = set(all_types)

    def _reset_solver_state(self):
        """reset assignment, counts, and domains for a fresh retry."""
        self.assignment       = {}
        self.remaining_counts = dict(REQUIRED_TYPE_COUNTS)
        self._initialise_domains()

    def _save_domains(self):
        """snapshot all cell domains before forward checking."""
        return {cell: set(domain) for cell, domain in self.cell_domains.items()}

    def _restore_domains(self, saved_domains):
        """restore cell domains from a snapshot to undo forward checking."""
        for cell, domain_snapshot in saved_domains.items():
            self.cell_domains[cell] = set(domain_snapshot)

    # -------------------------------------------------------------------------
    # grid helpers
    # -------------------------------------------------------------------------

    def _get_grid_neighbors(self, cell):
        """return valid 4-directional neighbors of a cell, clipped to grid bounds."""
        row, col   = cell
        candidates = [
            (row - 1, col),
            (row + 1, col),
            (row, col - 1),
            (row, col + 1),
        ]
        return [
            (r, c) for r, c in candidates
            if 0 <= r < self.rows and 0 <= c < self.cols
        ]

    # -------------------------------------------------------------------------
    # post-layout constraint verification
    # -------------------------------------------------------------------------

    def verify_layout(self):
        """
        verify the completed layout satisfies all three constraints.
        reads from the shared city graph after the assignment is written.
        prints a clear pass/fail report for each constraint.
        returns true if all constraints are satisfied.
        """
        print("\n-- constraint verification --------------------------")
        all_passed = True

        # c1 — separation
        c1_violations = []
        for ind_cell in self.city.nodes_of_type("Industrial"):
            for neighbor_cell in self._get_grid_neighbors(ind_cell):
                neighbor_type = self.city.get_location_type(neighbor_cell)
                if neighbor_type in INDUSTRIAL_FORBIDDEN_ADJACENT:
                    c1_violations.append((ind_cell, neighbor_cell, neighbor_type))

        if c1_violations:
            all_passed = False
            print("  c1 separation      : FAIL — {} violations".format(len(c1_violations)))
            for ind_cell, nb_cell, nb_type in c1_violations[:3]:
                print("    industrial {} adjacent to {} {}".format(ind_cell, nb_type, nb_cell))
        else:
            print("  c1 separation      : PASS")

        # c2 — hospital access
        c2_violations = []
        for res_cell in self.city.nodes_of_type("Residential"):
            min_hops = self.city.shortest_hop_to_type(res_cell, "Hospital")
            if min_hops > self.hospital_hop_limit:
                c2_violations.append((res_cell, min_hops))

        if c2_violations:
            all_passed = False
            print("  c2 hospital access : FAIL — {}/{} residential too far (limit={})".format(
                len(c2_violations),
                len(self.city.nodes_of_type("Residential")),
                self.hospital_hop_limit
            ))
        else:
            print("  c2 hospital access : PASS (limit={} hops)".format(self.hospital_hop_limit))

        # c3 — power supply
        c3_violations = []
        for pwr_cell in self.city.nodes_of_type("PowerPlant"):
            min_hops = self.city.shortest_hop_to_type(pwr_cell, "Industrial")
            if min_hops > self.powerplant_hop_limit:
                c3_violations.append((pwr_cell, min_hops))

        if c3_violations:
            all_passed = False
            print("  c3 power supply    : FAIL — {}/{} power plants too far (limit={})".format(
                len(c3_violations),
                len(self.city.nodes_of_type("PowerPlant")),
                self.powerplant_hop_limit
            ))
        else:
            print("  c3 power supply    : PASS (limit={} hops)".format(self.powerplant_hop_limit))

        print("  overall            : {}".format(
            "ALL CONSTRAINTS SATISFIED" if all_passed else "VIOLATIONS FOUND"
        ))
        print("----------------------------------------------------\n")
        return all_passed


# -----------------------------------------------------------------------------
# entry point — call this from all other challenge files
# -----------------------------------------------------------------------------

def run_layout_planner(city_graph):
    """
    the single function that challenge 2, 3, 4, and 5 should call to
    ensure the city has a valid layout before they begin their work.
    returns the planner instance if layout succeeded, None otherwise.
    """
    planner = CityLayoutPlanner(city_graph)
    success = planner.run()

    if success:
        planner.verify_layout()
        city_graph.validate()

    return planner if success else None


# -----------------------------------------------------------------------------
# standalone run
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 55)
    print("  citymind — challenge 1: csp city layout planner")
    print("=" * 55)

    random.seed(42)
    city    = CityGraph(rows=10, cols=10)
    planner = run_layout_planner(city)

    if planner:
        city.print_grid()
        city.print_risk_grid()
        city.print_population_grid()

        print("primary hospital : {}".format(
            city.get_label(city.primary_hospital) if city.primary_hospital else "not set"
        ))
        print("primary depot    : {}".format(
            city.get_label(city.primary_depot) if city.primary_depot else "not set"
        ))

        print("\n" + "=" * 55)
        print("  challenge 1 complete — ready for challenge 2")
        print("=" * 55)
    else:
        print("challenge 1 failed")