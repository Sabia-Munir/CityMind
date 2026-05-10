"""
main.py — CityMind integrated 20-step simulation runner
=========================================================
Single entry point for the full CityMind system.

Simulation step sequence (from design document section 9):
    1. Environmental Perturbation : generate_flood_events() blocks 0-2 roads.
       Blocked edges are immediately flagged as impassable (Effective_Cost = inf).
    2. Reactive Re-Routing (Ch 4): A* routes team to all civilians in
       nearest-first order. If a flood blocks the active path, A* reroutes
       from the team's current position in real time.
    3. Every 5 steps — Intelligence Refresh (Ch 5): ML re-analyses neighbourhood
       data; new risk scores update the cost multipliers across the grid.
    4. Every 5 steps — Strategic Realignment (Ch 3): GA re-evaluates ambulance
       positions using a warm start (seeding with the previous best solution).
    (5. Road Recovery: every 3 steps, 0-1 flooded roads are unblocked to
       simulate flood waters receding and prevent permanent graph isolation.
       This is an engineering addition not explicitly in the design document.)
"""

import random
import warnings

warnings.filterwarnings("ignore", category=UserWarning)

from city_graph       import CityGraph
from challenge1_csp   import run_layout_planner
from challenge2_mst   import build_road_network
from challenge3_ga    import place_ambulances
from challenge4_astar import run_emergency_routing
from challenge5_ml    import run_risk_pipeline


# -----------------------------------------------------------------------------
# simulation settings
# -----------------------------------------------------------------------------

RANDOM_SEED         = 4
TOTAL_STEPS         = 20
RISK_REFRESH_EVERY  = 5
MAX_FLOODS_PER_STEP = 2      # max 2 roads flood per step (from design doc)
NUM_CIVILIANS       = 6


# -----------------------------------------------------------------------------
# helpers
# -----------------------------------------------------------------------------

def pick_civilians(city, count, rng):
    """
    Randomly select `count` accessible residential nodes as trapped civilians.
    Prefers residential zones; falls back to any accessible node if needed.
    """
    residential_accessible = [
        cell for cell in city.nodes_of_type("Residential")
        if city.get_node(cell)["is_accessible"]
    ]
    if len(residential_accessible) >= count:
        return rng.sample(residential_accessible, count)
    any_accessible = [
        cell for cell in city.all_nodes()
        if city.get_node(cell)["is_accessible"]
    ]
    return rng.sample(any_accessible, min(count, len(any_accessible)))


def generate_flood_events(city, rng):
    """
    Randomly block up to MAX_FLOODS_PER_STEP edges to simulate flooding.
    Implements design-doc section 9, step 1:
        'The Flood Event Generator selects 0-2 edges to block.
         Blocked edges are immediately flagged as impassable.'
    The hospital-depot redundancy edge is NEVER blocked (safety rule).
    """
    unblocked_edges = []
    for a, b, data in city.get_all_edges():
        if data["blocked"]:
            continue
        # Never block the critical hospital-depot redundancy edge
        if (a == city.primary_hospital and b == city.primary_depot) or \
           (a == city.primary_depot and b == city.primary_hospital):
            continue
        unblocked_edges.append((a, b))

    if not unblocked_edges:
        return []

    num_floods    = min(rng.randint(0, MAX_FLOODS_PER_STEP), len(unblocked_edges))
    flooded_edges = rng.sample(unblocked_edges, num_floods)

    flooded = []
    for a, b in flooded_edges:
        # We don't block it here! We let the A* router block it mid-journey
        flooded.append((a, b))
    return flooded


def _unblock_random_roads(city, rng, max_unblocks=1):
    """
    Unblock some flooded roads to simulate flood waters receding.
    Intelligent recovery strategy: evaluates candidate edges by how many
    additional nodes they make accessible from the primary depot/hospital.
    """
    blocked_edges = city.get_blocked_edges()

    critical_edge = None
    if city.primary_hospital and city.primary_depot:
        if ((city.primary_hospital, city.primary_depot) in blocked_edges or
                (city.primary_depot, city.primary_hospital) in blocked_edges):
            critical_edge = (city.primary_hospital, city.primary_depot)

    available_edges = [
        e for e in blocked_edges
        if e != critical_edge and (e[1], e[0]) != critical_edge
    ]
    if not available_edges:
        return 0

    num_unblocks = min(rng.randint(1, max_unblocks), len(available_edges))
    if num_unblocks == 0:
        return 0

    # Evaluate edges based on reachability improvement
    def get_reachability(edge):
        a, b = edge
        # Temporarily unblock
        city.unblock_road(a, b)
        
        # Count reachable nodes from primary depot
        from collections import deque
        start = city.primary_depot if city.primary_depot else city.all_nodes()[0]
        visited = {start}
        queue = deque([start])
        while queue:
            curr = queue.popleft()
            # use get_open_neighbors_with_cost because it respects blocked status
            for nbr, cost in city.get_open_neighbors_with_cost(curr):
                if cost < float('inf') and nbr not in visited:
                    visited.add(nbr)
                    queue.append(nbr)
                    
        # Re-block
        city.block_road(a, b)
        return len(visited)

    # Sort edges by reachability (descending), then random to break ties
    rng.shuffle(available_edges)
    available_edges.sort(key=get_reachability, reverse=True)

    edges_to_unblock = available_edges[:num_unblocks]
    for a, b in edges_to_unblock:
        city.unblock_road(a, b)

    return len(edges_to_unblock)


def count_risk_levels(risk_predictions):
    high   = sum(1 for v in risk_predictions.values() if v == "High")
    medium = sum(1 for v in risk_predictions.values() if v == "Medium")
    low    = sum(1 for v in risk_predictions.values() if v == "Low")
    return high, medium, low


def print_section(title):
    width = 62
    print("\n" + "=" * width)
    print("  {}".format(title))
    print("=" * width)


def print_step_header(step):
    print("\n-- step {:02d} / {:02d} ---------------------------------------------------".format(
        step, TOTAL_STEPS
    ))


# -----------------------------------------------------------------------------
# main simulation
# -----------------------------------------------------------------------------

def main():
    random.seed(RANDOM_SEED)
    rng = random.Random(RANDOM_SEED)

    print_section("citymind — integrated 20-step simulation")

    # -- phase 0a: ONE shared city graph ---------------------------------------
    print_section("phase 0a — initialising shared city graph")
    city = CityGraph(rows=10, cols=10)

    # -- phase 0b: challenge 1 — csp city layout -------------------------------
    print_section("phase 0b — challenge 1: csp city layout")
    planner = run_layout_planner(city)
    if planner is None:
        print("[main] ERROR: challenge 1 failed — cannot continue")
        return
    print("[main] layout complete | primary hospital: {} | primary depot: {}".format(
        city.get_label(city.primary_hospital),
        city.get_label(city.primary_depot)
    ))

    # -- phase 0c: challenge 2 — mst road network ------------------------------
    print_section("phase 0c — challenge 2: mst road network")
    road_result = build_road_network(city)
    if not road_result:
        print("[main] ERROR: challenge 2 failed — cannot continue")
        return
    print("[main] road network complete | roads: {} | cost: {:.2f} | redundancy: {}".format(
        len(road_result["mst_edges"]),
        road_result["total_cost"],
        road_result["redundant_edge"] is not None
    ))
    redundancy_ok, conn, msg = city.verify_hospital_depot_redundancy()
    print("[main] redundancy verification: {}".format(msg))
    if not redundancy_ok:
        print("[main] WARNING: Hospital-depot path redundancy not satisfied!")

    # -- phase 0d: challenge 5 — initial crime risk prediction -----------------
    print_section("phase 0d — challenge 5: initial crime risk prediction")
    ml_result = run_risk_pipeline(city)
    if ml_result is None:
        print("[main] ERROR: challenge 5 failed — cannot continue")
        return
    high, medium, low = count_risk_levels(ml_result["risk_predictions"])
    print("[main] risk complete | High={} | Medium={} | Low={} | cv={:.4f}".format(
        high, medium, low, ml_result["cv_accuracy"]
    ))

    # -- phase 0e: challenge 3 — initial ambulance placement -------------------
    print_section("phase 0e — challenge 3: initial ambulance placement")
    best_positions = place_ambulances(city)
    if not best_positions:
        print("[main] ERROR: challenge 3 failed — cannot continue")
        return
    city.ambulance_positions = best_positions
    print("[main] ambulances placed:")
    for i, pos in enumerate(city.ambulance_positions, 1):
        print("[main]   ambulance {}: {}".format(i, city.get_label(pos)))

    # -- initial civilian selection ---------------------------------------------
    civilians = pick_civilians(city, NUM_CIVILIANS, rng)
    print("\n[main] initial civilians selected:")
    for i, civ in enumerate(civilians, 1):
        print("  civilian {}: {}".format(i, city.get_label(civ)))

    # -- simulation state counters ----------------------------------------------
    total_visited     = 0
    total_unreachable = 0
    total_reroutes    = 0
    total_cost        = 0.0
    risk_refreshes    = 0
    amb_repositions   = 0
    all_floods        = []

    # Team starts at primary depot (Challenge 4 — design doc section 9)
    team_position = city.primary_depot

    # -------------------------------------------------------------------------
    # 20-step simulation loop
    # -------------------------------------------------------------------------
    print_section("simulation — steps 1 to {}".format(TOTAL_STEPS))

    for step in range(1, TOTAL_STEPS + 1):
        city.set_simulation_step(step)
        print_step_header(step)

        # -- STEP 1: Environmental Perturbation — flood events -----------------
        # Design doc section 9, step 1:
        #   "The Flood Event Generator selects 0-2 edges to block.
        #    Blocked edges are immediately flagged as impassable."
        flooded_this_step = generate_flood_events(city, rng)
        all_floods.extend(flooded_this_step)
        if flooded_this_step:
            print("[main] step {:02d}: {} flood(s) scheduled for this step".format(
                step, len(flooded_this_step)
            ))
        else:
            print("[main] step {:02d}: no floods this step".format(step))

        # -- STEP 2: Reactive Re-Routing — Challenge 4 (A*) -------------------
        # Design doc section 9, step 2:
        #   "The A* router detects graph changes. If the medical team's active
        #    path is intersected by a flood, a real-time recalculation is
        #    triggered from their current node coordinates."
        # EmergencyRouter uses nearest-first ordering (design doc section 6).

        # FIXED: pick fresh civilians every step from currently accessible nodes.
        # Reusing stale civilians caused the team to retry the same unreachable
        # targets for multiple steps after flooding fragmented the graph.
        civilians = pick_civilians(city, NUM_CIVILIANS, rng)

        if civilians:
            # FIXED: validate team_position before routing.
            # If the team's last position was isolated by a flood, reset to
            # the nearest accessible node so routing can begin cleanly.
            if not city.get_node(team_position)["is_accessible"]:
                from challenge4_astar import _find_nearest_accessible
                recovered = _find_nearest_accessible(city, team_position)
                if recovered is not None:
                    print("[main] step {:02d}: team position {} isolated — recovering to {}".format(
                        step,
                        city.get_label(team_position),
                        city.get_label(recovered)
                    ))
                    team_position = recovered
                else:
                    print("[main] step {:02d}: entire graph isolated — skipping routing".format(step))
                    total_unreachable += len(civilians)
                    continue

            routing_result = run_emergency_routing(
                city           = city,
                civilian_nodes = civilians,
                start_node     = team_position,
                flood_schedule = list(flooded_this_step)  # Pass the floods to happen mid-journey
            )

            if routing_result:
                step_visited     = len(routing_result["visited"])
                step_unreachable = len(routing_result["unreachable"])
                step_reroutes    = routing_result["reroutes"]
                step_cost        = routing_result["total_cost"]

                total_visited     += step_visited
                total_unreachable += step_unreachable
                total_reroutes    += step_reroutes
                total_cost        += step_cost

                # Update team position to last civilian reached
                if routing_result["visited"]:
                    team_position = routing_result["visited"][-1]
                elif routing_result["full_path"]:
                    team_position = routing_result["full_path"][-1]

                print("[main] step {:02d}: routing | visited={} | unreachable={} | "
                      "reroutes={} | cost={:.3f} | team at {}".format(
                    step, step_visited, step_unreachable, step_reroutes,
                    step_cost, city.get_label(team_position)
                ))
            else:
                print("[main] step {:02d}: routing failed".format(step))

        # -- STEP 3 (every 5 steps): Intelligence Refresh + Strategic Realignment
        # Design doc section 9, steps 3-4:
        #   "Every 5 simulation steps (5,10,15,20), the ML pipeline re-analyses
        #    neighbourhood data. Whenever risk scores shift, the GA re-evaluates
        #    ambulance positions using a warm start."
        if step % RISK_REFRESH_EVERY == 0:

            # 3a. re-select civilians for the next cycle
            civilians = pick_civilians(city, NUM_CIVILIANS, rng)
            if civilians:
                print("[main] step {:02d}: civilians refreshed:".format(step))
                for i, civ in enumerate(civilians, 1):
                    print("[main]   civilian {}: {}".format(i, city.get_label(civ)))

            # 3b. Intelligence Refresh — Challenge 5
            print("[main] step {:02d}: refreshing risk scores (challenge 5)".format(step))
            ml_result = run_risk_pipeline(city)
            if ml_result:
                risk_refreshes += 1
                high, medium, low = count_risk_levels(ml_result["risk_predictions"])
                print("[main] step {:02d}: risk done | High={} Medium={} Low={} cv={:.4f}".format(
                    step, high, medium, low, ml_result["cv_accuracy"]
                ))

            # 3c. Strategic Realignment — Challenge 3 (warm start)
            print("[main] step {:02d}: repositioning ambulances (challenge 3)".format(step))
            new_positions = place_ambulances(
                city, seed_chromosome=list(city.ambulance_positions)
            )
            if new_positions:
                amb_repositions += 1
                city.ambulance_positions = new_positions
                print("[main] step {:02d}: ambulances repositioned:".format(step))
                for i, pos in enumerate(city.ambulance_positions, 1):
                    print("[main]   ambulance {} -> {}".format(i, city.get_label(pos)))

        # -- STEP 4: Road Recovery (engineering addition, every 3 steps) -------
        # Prevents cumulative flooding from permanently isolating graph regions.
        # FIXED: increased to max_unblocks=2 to counteract heavy fragmentation.
        if step % 3 == 0:
            unblocked = _unblock_random_roads(city, rng, max_unblocks=2)
            if unblocked > 0:
                print("[main] step {:02d}: flood recovery — {} road(s) unblocked".format(
                    step, unblocked
                ))

    # -------------------------------------------------------------------------
    # final summary
    # -------------------------------------------------------------------------
    print_section("simulation complete — final summary")

    blocked_roads = sum(1 for _, _, data in city.get_all_edges() if data["blocked"])

    print("  total steps           : {}".format(TOTAL_STEPS))
    print("  total flood events    : {}".format(len(all_floods)))
    print("  roads blocked (final) : {}".format(blocked_roads))
    print("  civilians visited     : {}".format(total_visited))
    print("  civilians unreachable : {}".format(total_unreachable))
    print("  total reroutes        : {}".format(total_reroutes))
    print("  total routing cost    : {:.3f}".format(total_cost))
    print("  risk refreshes        : {}".format(risk_refreshes))
    print("  ambulance repositions : {}".format(amb_repositions))

    # final graph validation
    print("\n-- final graph validation -------------------------------------------")
    validation = city.validate()
    print("  result  : {}".format("PASSED" if validation["passed"] else "FAILED"))
    for err in validation["errors"]:
        print("  ERROR   : {}".format(err))
    for warn in validation["warnings"]:
        print("  warning : {}".format(warn))

    city.print_risk_grid()

    print("-- final ambulance positions ----------------------------------------")
    for i, pos in enumerate(city.ambulance_positions, 1):
        print("  ambulance {} : {}".format(i, city.get_label(pos)))

    # event log breakdown by category
    log           = city.get_log()
    flood_count   = len([e for e in log if e["category"] == "FLOOD"])
    reroute_count = len([e for e in log if e["category"] == "REROUTE"])
    risk_count    = len([e for e in log if e["category"] == "RISK_UPDATE"])
    isolate_count = len([e for e in log if e["category"] == "ISOLATE"])

    print("\n-- event log summary ------------------------------------------------")
    print("  total log entries : {}".format(len(log)))
    print("  flood events      : {}".format(flood_count))
    print("  reroute events    : {}".format(reroute_count))
    print("  risk updates      : {}".format(risk_count))
    print("  isolation events  : {}".format(isolate_count))

    print("\n" + "=" * 62)
    print("  citymind simulation finished successfully")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()