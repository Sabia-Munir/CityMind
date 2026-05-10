"""
challenge4_astar.py — emergency routing under dynamic conditions (challenge 4)
==============================================================================
FIXED: Properly tracks team position and visits civilians in sequence.
"""

import math
import heapq
from city_graph import CityGraph


def run_emergency_routing(city, civilian_nodes=None, start_node=None, flood_schedule=None):
    """
    Run the full emergency routing mission for one simulation step.
    
    FIXED: Actually visits civilians in sequence, updates position after each visit.
    """
    # resolve start node
    if start_node is None:
        start_node = city.primary_depot
        if start_node is None:
            hospitals = city.nodes_of_type("Hospital")
            start_node = hospitals[0] if hospitals else city.all_nodes()[0]
    
    # resolve civilian list
    if civilian_nodes is None:
        civilian_nodes = _generate_civilian_nodes(city, count=6)
    
    city._log("SYSTEM", "emergency routing starting from {}".format(city.get_label(start_node)))
    city._log("SYSTEM", "civilians to visit: {}".format(len(civilian_nodes)))

    # FIXED: if the assigned start node is already isolated, find the nearest
    # accessible node via BFS so the team is never stranded before it begins.
    if not city.get_node(start_node)["is_accessible"]:
        recovered = _find_nearest_accessible(city, start_node)
        if recovered is not None:
            city._log("SYSTEM", "start node {} is isolated — recovering to {}".format(
                city.get_label(start_node), city.get_label(recovered)
            ))
            start_node = recovered
        else:
            city._log("SYSTEM", "ERROR: entire graph is isolated — aborting routing")
            return {"visited": [], "unreachable": list(civilian_nodes),
                    "total_cost": 0.0, "full_path": [], "reroutes": 0, "last_path": []}

    router = EmergencyRouter(city, start_node, civilian_nodes, flood_schedule)
    return router.run()


class EmergencyRouter:
    def __init__(self, city, start_node, civilian_nodes, flood_schedule=None):
        self.city           = city
        self.current_pos    = start_node
        self.remaining      = list(civilian_nodes)
        self.visited        = []
        self.unreachable    = []
        self.total_cost     = 0.0
        self.full_path      = [start_node]
        self.reroutes       = 0
        self.flood_schedule = flood_schedule or []
        self.step           = 0
        self.current_active_path = []
    
    def run(self):
        """Main mission loop - visits civilians in nearest-first order."""
        while self.remaining:
            # FIXED: before each visit attempt, check whether current_pos is
            # still accessible.  If flooding isolated it since the last visit,
            # escape to the nearest reachable node first.
            if not self.city.get_node(self.current_pos)["is_accessible"]:
                recovered = _find_nearest_accessible(self.city, self.current_pos)
                if recovered is not None:
                    self.city._log("SYSTEM",
                        "team stranded at {} — recovering to {}".format(
                            self.city.get_label(self.current_pos),
                            self.city.get_label(recovered)
                        )
                    )
                    self.current_pos = recovered
                    self.full_path.append(recovered)
                else:
                    # whole graph isolated — give up gracefully
                    self.city._log("SYSTEM", "entire graph isolated — mission aborted")
                    self.unreachable.extend(self.remaining)
                    self.remaining = []
                    break

            # Pick nearest reachable civilian from current position
            next_target = self._pick_nearest_civilian()
            
            if next_target is None:
                # No reachable civilians remain
                self.city._log("SYSTEM", "no reachable civilians remain — mission ending early")
                self.unreachable.extend(self.remaining)
                self.remaining = []
                break
            
            self.remaining.remove(next_target)
            success, path = self._navigate_to(next_target)
            
            if success:
                self.visited.append(next_target)
                self.city._log("SYSTEM", "reached civilian at {}".format(
                    self.city.get_label(next_target)
                ))
            else:
                self.unreachable.append(next_target)
                self.city._log("SYSTEM", "civilian at {} is unreachable — skipping".format(
                    self.city.get_label(next_target)
                ))
        
        # Flush any remaining floods that didn't happen during movement
        while self.flood_schedule:
            fa, fb = self.flood_schedule.pop(0)
            self.city.block_road(fa, fb)

        self.city._log("SYSTEM",
            "mission complete | visited={} | unreachable={} | total_cost={:.3f} | reroutes={}".format(
                len(self.visited), len(self.unreachable),
                self.total_cost, self.reroutes
            )
        )
        
        return {
            "visited":     self.visited,
            "unreachable": self.unreachable,
            "total_cost":  self.total_cost,
            "full_path":   self.full_path,
            "reroutes":    self.reroutes,
            "last_path":   self.current_active_path,
        }
    
    def _navigate_to(self, target):
        """Navigate from current_pos to target using A* with dynamic flood handling.

        FIXED: floods now block the ACTUAL scheduled edge (not the team's path).
        The flood is processed BEFORE the path-validity check so that if the
        newly blocked edge happens to be on the planned route, the replan
        logic catches it in the same iteration — producing a genuine reroute.
        """
        path = astar(self.city, self.current_pos, target)
        self.current_active_path = path

        if path is None:
            return False, None

        path_index = 0

        while self.current_pos != target:
            # ── step A: simulate one real-time flood event ──────────────
            # Block the ACTUAL scheduled edge so graph fragmentation
            # matches the design-doc flood count exactly.
            if self.flood_schedule:
                fa, fb = self.flood_schedule.pop(0)
                if not self.city.is_road_blocked(fa, fb):
                    self.city.block_road(fa, fb)

            # ── step B: check if the planned path is still valid ────────
            need_replan = False
            replan_reason = ""

            if path_index + 1 >= len(path):
                need_replan = True
                replan_reason = "path exhausted"
            else:
                # Check immediate next edge
                next_node = path[path_index + 1]
                if self.city.is_road_blocked(self.current_pos, next_node):
                    need_replan = True
                    replan_reason = "road blocked: {} -> {}".format(
                        self.city.get_label(self.current_pos),
                        self.city.get_label(next_node)
                    )
                elif self.city.get_effective_cost(self.current_pos, next_node) == math.inf:
                    need_replan = True
                    replan_reason = "effective cost is inf (blocked/isolated)"
                else:
                    # Proactive look-ahead: scan the ENTIRE remaining path
                    # for broken edges so we reroute early instead of walking
                    # into a dead-end several hops later.
                    for j in range(path_index + 1, len(path) - 1):
                        if self.city.is_road_blocked(path[j], path[j + 1]):
                            need_replan = True
                            replan_reason = "upcoming road blocked: {} -> {}".format(
                                self.city.get_label(path[j]),
                                self.city.get_label(path[j + 1])
                            )
                            break

            # ── step C: replan if necessary ─────────────────────────────
            if need_replan:
                self.city._log("REROUTE", "replanning at {} - reason: {}".format(
                    self.city.get_label(self.current_pos), replan_reason
                ))

                old_path = path[path_index:] if path_index < len(path) else path
                new_path = astar(self.city, self.current_pos, target)

                if new_path is None:
                    if not self.city.get_node(target)["is_accessible"]:
                        self.city._log("REROUTE", "target {} is isolated - marking unreachable".format(
                            self.city.get_label(target)
                        ))
                    else:
                        self.city._log("REROUTE", "no alternative path to {}".format(
                            self.city.get_label(target)
                        ))
                    return False, None

                if new_path != old_path:
                    self.city.log_reroute(old_path, new_path)
                    self.reroutes += 1

                path = new_path
                path_index = 0
                self.current_active_path = path
                continue

            # ── step D: normal movement ─────────────────────────────────
            next_node = path[path_index + 1]
            step_cost = self.city.get_effective_cost(self.current_pos, next_node)

            self.total_cost += step_cost
            self.full_path.append(next_node)
            self.current_pos = next_node
            path_index += 1
            self.step += 1

        return True, path
    
    def _pick_nearest_civilian(self):
        """Find the nearest remaining civilian using A* path cost."""
        # If current_pos itself is isolated there is nothing we can reach —
        # return None immediately so the caller triggers the stranded-recovery
        # path rather than spinning through every civilian with A* calls that
        # will all return None.
        if not self.city.get_node(self.current_pos)["is_accessible"]:
            return None

        best_target = None
        best_cost = float("inf")

        for civilian in self.remaining:
            if not self.city.get_node(civilian)["is_accessible"]:
                continue
            path = astar(self.city, self.current_pos, civilian)
            if path is not None:
                cost = _path_cost(self.city, path)
                if cost < best_cost:
                    best_cost = cost
                    best_target = civilian

        return best_target


def astar(city, start, goal):
    """Find shortest path from start to goal using A* with admissible heuristic."""
    if start == goal:
        return [start]
    
    g_score = {start: 0.0}
    f_score = {start: _heuristic(city, start, goal)}
    open_heap = [(f_score[start], 0, start)]
    counter = 1
    came_from = {}
    closed = set()
    
    while open_heap:
        current_f, _, current = heapq.heappop(open_heap)
        
        if current == goal:
            return _reconstruct_path(came_from, current)
        
        if current in closed:
            continue
        closed.add(current)
        
        for neighbor, edge_cost in city.get_open_neighbors_with_cost(current):
            if neighbor in closed:
                continue
            
            if edge_cost == math.inf:
                continue
            
            tentative_g = g_score[current] + edge_cost
            
            if tentative_g < g_score.get(neighbor, math.inf):
                came_from[neighbor] = current
                g_score[neighbor] = tentative_g
                f_score[neighbor] = tentative_g + _heuristic(city, neighbor, goal)
                heapq.heappush(open_heap, (f_score[neighbor], counter, neighbor))
                counter += 1
    
    return None


def _heuristic(city, node, goal):
    """Admissible heuristic: Euclidean distance × 0.8 (minimum edge cost)."""
    return city.euclidean_distance(node, goal) * 0.8


def _reconstruct_path(came_from, current):
    path = [current]
    while current in came_from:
        current = came_from[current]
        path.append(current)
    path.reverse()
    return path


def _path_cost(city, path):
    total = 0.0
    for i in range(len(path) - 1):
        cost = city.get_effective_cost(path[i], path[i + 1])
        if cost == math.inf:
            return float("inf")
        total += cost
    return total


def _generate_civilian_nodes(city, count):
    residential = [
        cell for cell in city.nodes_of_type("Residential")
        if city.get_node(cell)["is_accessible"]
    ]
    accessible = [
        cell for cell in city.all_nodes()
        if city.get_node(cell)["is_accessible"]
    ]
    pool = residential if len(residential) >= count else accessible
    import random
    return random.sample(pool, min(count, len(pool)))


def _find_nearest_accessible(city, start):
    """
    BFS from `start` (ignoring the blocked status of edges FROM start)
    to find the nearest node that has at least one open road.

    This is used to "escape" an isolated node — the team is assumed to be
    able to walk on foot a short distance to reach the closest accessible
    network entry-point.

    Returns (row, col) of the nearest accessible node, or None if the whole
    graph is isolated.
    """
    from collections import deque

    # If start is already accessible, return it immediately.
    if city.get_node(start)["is_accessible"]:
        return start

    visited = {start}
    # Explore via ALL edges (including blocked) from the isolated start node
    # so we can hop across to the first node that still has open roads.
    queue = deque()
    for neighbor in city.graph.neighbors(start):
        if neighbor not in visited:
            visited.add(neighbor)
            queue.append((neighbor, 1))

    while queue:
        node, depth = queue.popleft()
        if city.get_node(node)["is_accessible"]:
            return node
        if depth >= 15:          # limit search radius to 15 hops
            continue
        for neighbor in city.graph.neighbors(node):
            if neighbor not in visited:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))

    return None   # entire graph isolated