"""
main.py — citymind integrated 20-step simulation runner
=========================================================
single entry point for the full system.
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


# ─────────────────────────────────────────────────────────────────────────────
# simulation settings
# ─────────────────────────────────────────────────────────────────────────────

RANDOM_SEED         = 42
TOTAL_STEPS         = 20
RISK_REFRESH_EVERY  = 5
MAX_FLOODS_PER_STEP = 2
NUM_CIVILIANS       = 6


# ─────────────────────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────────────────────

def pick_civilians(city, count, rng):
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
    unblocked_edges = []
    for a, b, data in city.get_all_edges():
        if data["blocked"]:
            continue
        if (a == city.primary_hospital and b == city.primary_depot) or \
           (a == city.primary_depot and b == city.primary_hospital):
            continue
        unblocked_edges.append((a, b))

    if not unblocked_edges:
        return []

    num_floods = min(rng.randint(0, MAX_FLOODS_PER_STEP), len(unblocked_edges))
    flooded_edges = rng.sample(unblocked_edges, num_floods)

    flooded = []
    for a, b in flooded_edges:
        city.block_road(a, b)
        flooded.append((a, b))
    return flooded


def _unblock_random_roads(city, rng, max_unblocks=1):
    blocked_edges = city.get_blocked_edges()
    critical_edge = None
    if city.primary_hospital and city.primary_depot:
        if ((city.primary_hospital, city.primary_depot) in blocked_edges or
                (city.primary_depot, city.primary_hospital) in blocked_edges):
            critical_edge = (city.primary_hospital, city.primary_depot)
    available_edges = [e for e in blocked_edges if e != critical_edge and (e[1], e[0]) != critical_edge]
    if not available_edges:
        return 0
    # Always unblock at least 1 road (was 0–1, now guaranteed 1)
    # This counteracts the ~1.5 floods per step from mid-mission events
    num_unblocks = min(rng.randint(1, max(1, max_unblocks)), len(available_edges))
    for _ in range(num_unblocks):
        a, b = rng.choice(available_edges)
        city.unblock_road(a, b)
    return num_unblocks


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


# ─────────────────────────────────────────────────────────────────────────────
# main simulation
# ─────────────────────────────────────────────────────────────────────────────

def main():
    rng = random.Random(RANDOM_SEED)

    print_section("citymind — all challenges")

    # ── phase 0a: shared city graph ───────────────────────────────────────────
    print_section("phase 0a — initialising shared city graph")
    city = CityGraph(rows=10, cols=10)

    # ── phase 0b: challenge 1 — csp city layout ───────────────────────────────
    print_section("phase 0b — challenge 1: csp city layout")
    planner = run_layout_planner(city)
    if planner is None:
        print("[main] ERROR: challenge 1 failed — cannot continue")
        return
    print("[main] layout complete | primary hospital: {} | primary depot: {}".format(
        city.get_label(city.primary_hospital),
        city.get_label(city.primary_depot)
    ))

    # ── phase 0c: challenge 2 — mst road network ──────────────────────────────
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

    # ── phase 0d: challenge 5 — initial crime risk prediction ─────────────────
    print_section("phase 0d — challenge 5: initial crime risk prediction")
    ml_result = run_risk_pipeline(city)
    if ml_result is None:
        print("[main] ERROR: challenge 5 failed — cannot continue")
        return
    high, medium, low = count_risk_levels(ml_result["risk_predictions"])
    print("[main] risk complete | High={} | Medium={} | Low={} | cv={:.4f}".format(
        high, medium, low, ml_result["cv_accuracy"]
    ))

    # ── phase 0e: challenge 3 — initial ambulance placement ───────────────────
    print_section("phase 0e — challenge 3: initial ambulance placement")
    best_positions = place_ambulances(city)
    if not best_positions:
        print("[main] ERROR: challenge 3 failed — cannot continue")
        return
    city.ambulance_positions = best_positions
    print("[main] ambulances placed:")
    for i, pos in enumerate(city.ambulance_positions, 1):
        print("[main]   ambulance {}: {}".format(i, city.get_label(pos)))

    # ── initial civilian selection ─────────────────────────────────────────────
    civilians = pick_civilians(city, NUM_CIVILIANS, rng)
    print("\n[main] initial civilians selected:")
    for i, civ in enumerate(civilians, 1):
        print("  civilian {}: {}".format(i, city.get_label(civ)))

    # ── simulation counters ────────────────────────────────────────────────────
    total_visited     = 0
    total_unreachable = 0
    total_reroutes    = 0
    total_cost        = 0.0
    all_floods        = []

    team_position = city.primary_depot

    # ─────────────────────────────────────────────────────────────────────────
    # 20-step simulation loop
    # ─────────────────────────────────────────────────────────────────────────
    print_section("simulation — steps 1 to {}".format(TOTAL_STEPS))

    for step in range(1, TOTAL_STEPS + 1):
        city.set_simulation_step(step)
        print_step_header(step)

        # ── 1. flood recovery first (unblock some old roads) ──────────────────
        if step % 2 == 0:
            unblocked = _unblock_random_roads(city, rng, max_unblocks=2)
            if unblocked > 0:
                print("[main] step {:02d}: {} road(s) unblocked".format(step, unblocked))

        # ── 2. challenge 4 — mid-journey flood simulation ─────────────────────
        # We run routing civilian-by-civilian. After each civilian is reached,
        # we randomly flood a road to simulate changing conditions mid-mission.
        # If the next path is affected, A* must reroute — producing real reroutes.

        # Rescue: if team is stranded (can't reach any civilian), relocate to
        # the nearest accessible ambulance depot position.
        if civilians:
            from challenge4_astar import astar
            team_reachable = any(
                astar(city, team_position, civ) is not None
                for civ in civilians
                if city.get_node(civ)["is_accessible"]
            )
            if not team_reachable and city.ambulance_positions:
                # Find closest ambulance position reachable from the team,
                # or fall back to any accessible node near a civilian
                rescue_pos = None
                for amb in city.ambulance_positions:
                    if city.get_node(amb)["is_accessible"]:
                        rescue_pos = amb
                        break
                if rescue_pos is None:
                    # last resort: any accessible node
                    for civ in civilians:
                        if city.get_node(civ)["is_accessible"]:
                            rescue_pos = civ
                            break
                if rescue_pos and rescue_pos != team_position:
                    print("[main] step {:02d}: team stranded at {} — relocated to {}".format(
                        step, city.get_label(team_position), city.get_label(rescue_pos)
                    ))
                    team_position = rescue_pos
        if civilians:
            step_visited     = 0
            step_unreachable = 0
            step_reroutes    = 0
            step_cost        = 0.0
            step_floods      = 0
            current_pos      = team_position

            for civ_idx, target in enumerate(civilians):
                # Plan route to this civilian
                result = run_emergency_routing(
                    city           = city,
                    civilian_nodes = [target],
                    start_node     = current_pos,
                    flood_schedule = []
                )

                if not result or not result["visited"]:
                    step_unreachable += 1
                    print("[main] step {:02d}: civilian {} unreachable from {}".format(
                        step, city.get_label(target), city.get_label(current_pos)))
                    continue

                # Civilian reached — update position and cost
                step_visited += 1
                step_cost    += result["total_cost"]
                current_pos   = result["visited"][-1]

                # Now randomly flood a road mid-mission (20% chance)
                # Only count as reroute if the flood actually affects the next path
                if rng.random() < 0.20:
                    unblocked_edges = [
                        (a, b) for a, b, data in city.get_all_edges()
                        if not data["blocked"]
                        and not (a == city.primary_hospital and b == city.primary_depot)
                        and not (a == city.primary_depot and b == city.primary_hospital)
                    ]
                    if unblocked_edges:
                        a, b = rng.choice(unblocked_edges)

                        # Get cost to next civilian BEFORE flood
                        next_target = civilians[civ_idx + 1] if civ_idx + 1 < len(civilians) else None
                        if next_target:
                            pre_flood = run_emergency_routing(
                                city           = city,
                                civilian_nodes = [next_target],
                                start_node     = current_pos,
                                flood_schedule = []
                            )
                            pre_cost = pre_flood["total_cost"] if pre_flood and pre_flood["visited"] else float('inf')

                        # Apply the flood
                        city.block_road(a, b)
                        all_floods.append((a, b))
                        step_floods += 1

                        # Get cost to next civilian AFTER flood
                        if next_target:
                            post_flood = run_emergency_routing(
                                city           = city,
                                civilian_nodes = [next_target],
                                start_node     = current_pos,
                                flood_schedule = []
                            )
                            post_cost = post_flood["total_cost"] if post_flood and post_flood["visited"] else float('inf')

                            if post_cost > pre_cost or post_flood is None or not post_flood["visited"]:
                                # Flood affected the route — genuine reroute
                                step_reroutes += 1
                                print("[main] step {:02d}: FLOOD mid-mission: {} ↔ {} — rerouting (path affected)".format(
                                    step, city.get_label(a), city.get_label(b)
                                ))
                            else:
                                # Flood was irrelevant to current route
                                print("[main] step {:02d}: FLOOD mid-mission: {} ↔ {} — no reroute needed".format(
                                    step, city.get_label(a), city.get_label(b)
                                ))
                        else:
                            # No next civilian — flood still logged, no reroute counted
                            print("[main] step {:02d}: FLOOD mid-mission: {} ↔ {} — last civilian done".format(
                                step, city.get_label(a), city.get_label(b)
                            ))

            total_visited     += step_visited
            total_unreachable += step_unreachable
            total_reroutes    += step_reroutes
            total_cost        += step_cost
            team_position      = current_pos

            print("[main] step {:02d}: visited={} | unreachable={} | reroutes={} | cost={:.3f} | team at {}".format(
                step, step_visited, step_unreachable, step_reroutes, step_cost,
                city.get_label(team_position)
            ))

        # ── 3. every 5 steps: refresh civilians, risk & reposition ambulances ──
        if step % RISK_REFRESH_EVERY == 0:
            civilians = pick_civilians(city, NUM_CIVILIANS, rng)
            if civilians:
                print("[main] step {:02d}: civilians refreshed:".format(step))
                for i, civ in enumerate(civilians, 1):
                    print("[main]   civilian {}: {}".format(i, city.get_label(civ)))

            print("[main] step {:02d}: refreshing risk (challenge 5)".format(step))
            ml_result = run_risk_pipeline(city)
            if ml_result:
                high, medium, low = count_risk_levels(ml_result["risk_predictions"])
                print("[main] step {:02d}: risk done | High={} Medium={} Low={} cv={:.4f}".format(
                    step, high, medium, low, ml_result["cv_accuracy"]
                ))

            print("[main] step {:02d}: repositioning ambulances (challenge 3)".format(step))
            new_positions = place_ambulances(city, seed_chromosome=list(city.ambulance_positions))
            if new_positions:
                city.ambulance_positions = new_positions
                print("[main] step {:02d}: ambulances repositioned:".format(step))
                for i, pos in enumerate(city.ambulance_positions, 1):
                    print("[main]   ambulance {} -> {}".format(i, city.get_label(pos)))

    # ─────────────────────────────────────────────────────────────────────────
    # final summary
    # ─────────────────────────────────────────────────────────────────────────
    print_section("simulation complete — final summary")

    blocked_roads = sum(1 for _, _, data in city.get_all_edges() if data["blocked"])

    print("  total steps           : {}".format(TOTAL_STEPS))
    print("  total flood events    : {}".format(len(all_floods)))
    print("  roads blocked (final) : {}".format(blocked_roads))
    print("  civilians visited     : {}".format(total_visited))
    print("  civilians unreachable : {}".format(total_unreachable))
    print("  total reroutes        : {}".format(total_reroutes))
    print("  total routing cost    : {:.3f}".format(total_cost))

    # final graph validation
    print("\n-- final graph validation -------------------------------------------")
    validation = city.validate()
    print("  result  : {}".format("PASSED" if validation["passed"] else "FAILED"))
    for err in validation["errors"]:
        print("  ERROR   : {}".format(err))
    for warn in validation["warnings"]:
        print("  warning : {}".format(warn))

    # event log summary
    log         = city.get_log()
    flood_count = len([e for e in log if e["category"] == "FLOOD"])
    iso_count   = len([e for e in log if e["category"] == "ISOLATE"])

    print("\n-- event log summary ------------------------------------------------")
    print("  total log entries : {}".format(len(log)))
    print("  flood events      : {}".format(flood_count))
    print("  isolation events  : {}".format(iso_count))
    print("  reroute events    : {}".format(total_reroutes))  # tracked in main.py

    print("\n" + "=" * 62)
    print("  citymind — all challenges finished")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    main()





































# """
# main.py — citymind integrated 20-step simulation runner
# =========================================================
# single entry point for the full system.

# NOTE: challenges 2, 3, 5 are commented out for isolated testing of 1 & 4.
# """

# import random
# import warnings

# warnings.filterwarnings("ignore", category=UserWarning)

# from city_graph       import CityGraph
# from challenge1_csp   import run_layout_planner
# # from challenge2_mst   import build_road_network
# # from challenge3_ga    import place_ambulances
# from challenge4_astar import run_emergency_routing
# # from challenge5_ml    import run_risk_pipeline


# # ─────────────────────────────────────────────────────────────────────────────
# # simulation settings
# # ─────────────────────────────────────────────────────────────────────────────

# RANDOM_SEED         = 42
# TOTAL_STEPS         = 20
# RISK_REFRESH_EVERY  = 5
# MAX_FLOODS_PER_STEP = 2
# NUM_CIVILIANS       = 6


# # ─────────────────────────────────────────────────────────────────────────────
# # helpers
# # ─────────────────────────────────────────────────────────────────────────────

# def pick_civilians(city, count, rng):
#     residential_accessible = [
#         cell for cell in city.nodes_of_type("Residential")
#         if city.get_node(cell)["is_accessible"]
#     ]
#     if len(residential_accessible) >= count:
#         return rng.sample(residential_accessible, count)
#     any_accessible = [
#         cell for cell in city.all_nodes()
#         if city.get_node(cell)["is_accessible"]
#     ]
#     return rng.sample(any_accessible, min(count, len(any_accessible)))


# def generate_flood_events(city, rng):
#     unblocked_edges = []
#     for a, b, data in city.get_all_edges():
#         if data["blocked"]:
#             continue
#         if (a == city.primary_hospital and b == city.primary_depot) or \
#            (a == city.primary_depot and b == city.primary_hospital):
#             continue
#         unblocked_edges.append((a, b))

#     if not unblocked_edges:
#         return []

#     num_floods = min(rng.randint(0, MAX_FLOODS_PER_STEP), len(unblocked_edges))
#     flooded_edges = rng.sample(unblocked_edges, num_floods)

#     flooded = []
#     for a, b in flooded_edges:
#         city.block_road(a, b)
#         flooded.append((a, b))
#     return flooded


# def _unblock_random_roads(city, rng, max_unblocks=1):
#     blocked_edges = city.get_blocked_edges()
#     critical_edge = None
#     if city.primary_hospital and city.primary_depot:
#         if ((city.primary_hospital, city.primary_depot) in blocked_edges or
#                 (city.primary_depot, city.primary_hospital) in blocked_edges):
#             critical_edge = (city.primary_hospital, city.primary_depot)
#     available_edges = [e for e in blocked_edges if e != critical_edge and (e[1], e[0]) != critical_edge]
#     if not available_edges:
#         return 0
#     num_unblocks = min(rng.randint(0, max_unblocks), len(available_edges))
#     for _ in range(num_unblocks):
#         a, b = rng.choice(available_edges)
#         city.unblock_road(a, b)
#     return num_unblocks


# def count_risk_levels(risk_predictions):
#     high   = sum(1 for v in risk_predictions.values() if v == "High")
#     medium = sum(1 for v in risk_predictions.values() if v == "Medium")
#     low    = sum(1 for v in risk_predictions.values() if v == "Low")
#     return high, medium, low


# def print_section(title):
#     width = 62
#     print("\n" + "=" * width)
#     print("  {}".format(title))
#     print("=" * width)


# def print_step_header(step):
#     print("\n-- step {:02d} / {:02d} ---------------------------------------------------".format(
#         step, TOTAL_STEPS
#     ))


# # ─────────────────────────────────────────────────────────────────────────────
# # main simulation
# # ─────────────────────────────────────────────────────────────────────────────

# def main():
#     rng = random.Random(RANDOM_SEED)

#     print_section("citymind — challenges 1 & 4 only")

#     # ── phase 0a: shared city graph ───────────────────────────────────────────
#     print_section("phase 0a — initialising shared city graph")
#     city = CityGraph(rows=10, cols=10)

#     # ── phase 0b: challenge 1 — csp city layout ───────────────────────────────
#     print_section("phase 0b — challenge 1: csp city layout")
#     planner = run_layout_planner(city)
#     if planner is None:
#         print("[main] ERROR: challenge 1 failed — cannot continue")
#         return
#     print("[main] layout complete | primary hospital: {} | primary depot: {}".format(
#         city.get_label(city.primary_hospital),
#         city.get_label(city.primary_depot)
#     ))

#     # ── challenge 2 skipped ───────────────────────────────────────────────────
#     # print_section("phase 0c — challenge 2: mst road network")
#     # road_result = build_road_network(city)
#     # if not road_result:
#     #     print("[main] ERROR: challenge 2 failed — cannot continue")
#     #     return
#     # print("[main] road network complete | roads: {} | cost: {:.2f} | redundancy: {}".format(
#     #     len(road_result["mst_edges"]),
#     #     road_result["total_cost"],
#     #     road_result["redundant_edge"] is not None
#     # ))
#     # redundancy_ok, conn, msg = city.verify_hospital_depot_redundancy()
#     # print("[main] redundancy verification: {}".format(msg))

#     # ── challenge 5 skipped ───────────────────────────────────────────────────
#     # print_section("phase 0d — challenge 5: initial crime risk prediction")
#     # ml_result = run_risk_pipeline(city)
#     # if ml_result is None:
#     #     print("[main] ERROR: challenge 5 failed — cannot continue")
#     #     return
#     # high, medium, low = count_risk_levels(ml_result["risk_predictions"])
#     # print("[main] risk complete | High={} | Medium={} | Low={} | cv={:.4f}".format(
#     #     high, medium, low, ml_result["cv_accuracy"]
#     # ))

#     # ── challenge 3 skipped ───────────────────────────────────────────────────
#     # print_section("phase 0e — challenge 3: initial ambulance placement")
#     # best_positions = place_ambulances(city)
#     # if not best_positions:
#     #     print("[main] ERROR: challenge 3 failed — cannot continue")
#     #     return
#     # city.ambulance_positions = best_positions
#     # print("[main] ambulances placed:")
#     # for i, pos in enumerate(city.ambulance_positions, 1):
#     #     print("[main]   ambulance {}: {}".format(i, city.get_label(pos)))

#     # ── initial civilian selection ─────────────────────────────────────────────
#     civilians = pick_civilians(city, NUM_CIVILIANS, rng)
#     print("\n[main] initial civilians selected:")
#     for i, civ in enumerate(civilians, 1):
#         print("  civilian {}: {}".format(i, city.get_label(civ)))

#     # ── simulation counters ────────────────────────────────────────────────────
#     total_visited     = 0
#     total_unreachable = 0
#     total_reroutes    = 0
#     total_cost        = 0.0
#     all_floods        = []

#     team_position = city.primary_depot

#     # ─────────────────────────────────────────────────────────────────────────
#     # 20-step simulation loop
#     # ─────────────────────────────────────────────────────────────────────────
#     print_section("simulation — steps 1 to {}".format(TOTAL_STEPS))

#     for step in range(1, TOTAL_STEPS + 1):
#         city.set_simulation_step(step)
#         print_step_header(step)

#         # ── 1. flood recovery first (unblock some old roads) ──────────────────
#         if step % 3 == 0:
#             unblocked = _unblock_random_roads(city, rng, max_unblocks=1)
#             if unblocked > 0:
#                 print("[main] step {:02d}: {} road(s) unblocked".format(step, unblocked))

#         # ── 2. challenge 4 — mid-journey flood simulation ─────────────────────
#         # We run routing civilian-by-civilian. After each civilian is reached,
#         # we randomly flood a road to simulate changing conditions mid-mission.
#         # If the next path is affected, A* must reroute — producing real reroutes.
#         if civilians:
#             step_visited     = 0
#             step_unreachable = 0
#             step_reroutes    = 0
#             step_cost        = 0.0
#             step_floods      = 0
#             current_pos      = team_position

#             for civ_idx, target in enumerate(civilians):
#                 # Plan route to this civilian
#                 result = run_emergency_routing(
#                     city           = city,
#                     civilian_nodes = [target],
#                     start_node     = current_pos,
#                     flood_schedule = []
#                 )

#                 if not result or not result["visited"]:
#                     step_unreachable += 1
#                     print("[main] step {:02d}: civilian {} unreachable from {}".format(
#                         step, city.get_label(target), city.get_label(current_pos)))
#                     continue

#                 # Civilian reached — update position and cost
#                 step_visited += 1
#                 step_cost    += result["total_cost"]
#                 current_pos   = result["visited"][-1]

#                 # Now randomly flood a road mid-mission (30% chance)
#                 # Only count as reroute if the flood actually affects the next path
#                 if rng.random() < 0.30:
#                     unblocked_edges = [
#                         (a, b) for a, b, data in city.get_all_edges()
#                         if not data["blocked"]
#                         and not (a == city.primary_hospital and b == city.primary_depot)
#                         and not (a == city.primary_depot and b == city.primary_hospital)
#                     ]
#                     if unblocked_edges:
#                         a, b = rng.choice(unblocked_edges)

#                         # Get cost to next civilian BEFORE flood
#                         next_target = civilians[civ_idx + 1] if civ_idx + 1 < len(civilians) else None
#                         if next_target:
#                             pre_flood = run_emergency_routing(
#                                 city           = city,
#                                 civilian_nodes = [next_target],
#                                 start_node     = current_pos,
#                                 flood_schedule = []
#                             )
#                             pre_cost = pre_flood["total_cost"] if pre_flood and pre_flood["visited"] else float('inf')

#                         # Apply the flood
#                         city.block_road(a, b)
#                         all_floods.append((a, b))
#                         step_floods += 1

#                         # Get cost to next civilian AFTER flood
#                         if next_target:
#                             post_flood = run_emergency_routing(
#                                 city           = city,
#                                 civilian_nodes = [next_target],
#                                 start_node     = current_pos,
#                                 flood_schedule = []
#                             )
#                             post_cost = post_flood["total_cost"] if post_flood and post_flood["visited"] else float('inf')

#                             if post_cost > pre_cost or post_flood is None or not post_flood["visited"]:
#                                 # Flood affected the route — genuine reroute
#                                 step_reroutes += 1
#                                 print("[main] step {:02d}: FLOOD mid-mission: {} ↔ {} — rerouting (path affected)".format(
#                                     step, city.get_label(a), city.get_label(b)
#                                 ))
#                             else:
#                                 # Flood was irrelevant to current route
#                                 print("[main] step {:02d}: FLOOD mid-mission: {} ↔ {} — no reroute needed".format(
#                                     step, city.get_label(a), city.get_label(b)
#                                 ))
#                         else:
#                             # No next civilian — flood still logged, no reroute counted
#                             print("[main] step {:02d}: FLOOD mid-mission: {} ↔ {} — last civilian done".format(
#                                 step, city.get_label(a), city.get_label(b)
#                             ))

#             total_visited     += step_visited
#             total_unreachable += step_unreachable
#             total_reroutes    += step_reroutes
#             total_cost        += step_cost
#             team_position      = current_pos

#             print("[main] step {:02d}: visited={} | unreachable={} | reroutes={} | cost={:.3f} | team at {}".format(
#                 step, step_visited, step_unreachable, step_reroutes, step_cost,
#                 city.get_label(team_position)
#             ))

#         # ── 3. every 5 steps: refresh civilians only (risk & ambulances skipped)
#         if step % RISK_REFRESH_EVERY == 0:
#             civilians = pick_civilians(city, NUM_CIVILIANS, rng)
#             if civilians:
#                 print("[main] step {:02d}: civilians refreshed:".format(step))
#                 for i, civ in enumerate(civilians, 1):
#                     print("[main]   civilian {}: {}".format(i, city.get_label(civ)))

#             # ── challenge 5 refresh skipped ───────────────────────────────────
#             # print("[main] step {:02d}: refreshing risk (challenge 5)".format(step))
#             # ml_result = run_risk_pipeline(city)
#             # if ml_result:
#             #     high, medium, low = count_risk_levels(ml_result["risk_predictions"])
#             #     print("[main] step {:02d}: risk done | High={} Medium={} Low={} cv={:.4f}".format(
#             #         step, high, medium, low, ml_result["cv_accuracy"]
#             #     ))

#             # ── challenge 3 reposition skipped ───────────────────────────────
#             # print("[main] step {:02d}: repositioning ambulances (challenge 3)".format(step))
#             # new_positions = place_ambulances(city, seed_chromosome=list(city.ambulance_positions))
#             # if new_positions:
#             #     city.ambulance_positions = new_positions
#             #     print("[main] step {:02d}: ambulances repositioned:".format(step))
#             #     for i, pos in enumerate(city.ambulance_positions, 1):
#             #         print("[main]   ambulance {} -> {}".format(i, city.get_label(pos)))

#     # ─────────────────────────────────────────────────────────────────────────
#     # final summary
#     # ─────────────────────────────────────────────────────────────────────────
#     print_section("simulation complete — final summary")

#     blocked_roads = sum(1 for _, _, data in city.get_all_edges() if data["blocked"])

#     print("  total steps           : {}".format(TOTAL_STEPS))
#     print("  total flood events    : {}".format(len(all_floods)))
#     print("  roads blocked (final) : {}".format(blocked_roads))
#     print("  civilians visited     : {}".format(total_visited))
#     print("  civilians unreachable : {}".format(total_unreachable))
#     print("  total reroutes        : {}".format(total_reroutes))
#     print("  total routing cost    : {:.3f}".format(total_cost))

#     # final graph validation
#     print("\n-- final graph validation -------------------------------------------")
#     validation = city.validate()
#     print("  result  : {}".format("PASSED" if validation["passed"] else "FAILED"))
#     for err in validation["errors"]:
#         print("  ERROR   : {}".format(err))
#     for warn in validation["warnings"]:
#         print("  warning : {}".format(warn))

#     # event log summary
#     log         = city.get_log()
#     flood_count = len([e for e in log if e["category"] == "FLOOD"])
#     iso_count   = len([e for e in log if e["category"] == "ISOLATE"])

#     print("\n-- event log summary ------------------------------------------------")
#     print("  total log entries : {}".format(len(log)))
#     print("  flood events      : {}".format(flood_count))
#     print("  isolation events  : {}".format(iso_count))
#     print("  reroute events    : {}".format(total_reroutes))  # tracked in main.py

#     print("\n" + "=" * 62)
#     print("  citymind — challenges 1 & 4 test finished")
#     print("=" * 62 + "\n")


# if __name__ == "__main__":
#     main()













































# """
# main.py — citymind integrated 20-step simulation runner
# =========================================================
# single entry point for the full system.
# """

# import random
# import warnings

# warnings.filterwarnings("ignore", category=UserWarning)

# from city_graph       import CityGraph
# from challenge1_csp   import run_layout_planner
# from challenge2_mst   import build_road_network
# from challenge3_ga    import place_ambulances
# from challenge4_astar import run_emergency_routing
# from challenge5_ml    import run_risk_pipeline


# # ─────────────────────────────────────────────────────────────────────────────
# # simulation settings
# # ─────────────────────────────────────────────────────────────────────────────

# RANDOM_SEED         = 42
# TOTAL_STEPS         = 20
# RISK_REFRESH_EVERY  = 5
# MAX_FLOODS_PER_STEP = 2      # max 2 roads flood per step (from design doc)
# NUM_CIVILIANS       = 6


# # ─────────────────────────────────────────────────────────────────────────────
# # helpers
# # ─────────────────────────────────────────────────────────────────────────────

# def pick_civilians(city, count, rng):
#     """
#     randomly select `count` accessible residential nodes as trapped civilians.
#     """
#     residential_accessible = [
#         cell for cell in city.nodes_of_type("Residential")
#         if city.get_node(cell)["is_accessible"]
#     ]

#     if len(residential_accessible) >= count:
#         return rng.sample(residential_accessible, count)

#     any_accessible = [
#         cell for cell in city.all_nodes()
#         if city.get_node(cell)["is_accessible"]
#     ]
#     return rng.sample(any_accessible, min(count, len(any_accessible)))


# def generate_flood_events(city, rng):
#     """
#     FIXED: randomly block up to MAX_FLOODS_PER_STEP edges.
#     Does NOT use per-edge probability — selects specific random edges.
#     """
#     # Build list of unblocked edges (excluding the critical redundancy edge)
#     unblocked_edges = []
#     for a, b, data in city.get_all_edges():
#         if data["blocked"]:
#             continue
#         # Never block the critical redundancy edge
#         if (a == city.primary_hospital and b == city.primary_depot) or \
#            (a == city.primary_depot and b == city.primary_hospital):
#             continue
#         unblocked_edges.append((a, b))
    
#     if not unblocked_edges:
#         return []
    
#     # Select up to MAX_FLOODS_PER_STEP random edges to flood
#     num_floods = min(rng.randint(0, MAX_FLOODS_PER_STEP), len(unblocked_edges))
#     flooded_edges = rng.sample(unblocked_edges, num_floods)
    
#     flooded = []
#     for a, b in flooded_edges:
#         city.block_road(a, b)
#         flooded.append((a, b))
    
#     return flooded


# def _unblock_random_roads(city, rng, max_unblocks=1):
#     """
#     Randomly unblock some flooded roads to simulate flood waters receding.
#     This helps prevent permanent isolation of large areas.
#     """
#     blocked_edges = city.get_blocked_edges()
    
#     # Don't unblock the critical redundancy edge if it's the only one
#     critical_edge = None
#     if city.primary_hospital and city.primary_depot:
#         if ((city.primary_hospital, city.primary_depot) in blocked_edges or
#             (city.primary_depot, city.primary_hospital) in blocked_edges):
#             critical_edge = (city.primary_hospital, city.primary_depot)
    
#     # Filter out critical edge if needed
#     available_edges = [e for e in blocked_edges if e != critical_edge and (e[1], e[0]) != critical_edge]
    
#     if not available_edges:
#         return 0
    
#     num_unblocks = min(rng.randint(0, max_unblocks), len(available_edges))
#     for _ in range(num_unblocks):
#         a, b = rng.choice(available_edges)
#         city.unblock_road(a, b)
    
#     return num_unblocks


# def count_risk_levels(risk_predictions):
#     high   = sum(1 for v in risk_predictions.values() if v == "High")
#     medium = sum(1 for v in risk_predictions.values() if v == "Medium")
#     low    = sum(1 for v in risk_predictions.values() if v == "Low")
#     return high, medium, low


# def print_section(title):
#     width = 62
#     print("\n" + "=" * width)
#     print("  {}".format(title))
#     print("=" * width)


# def print_step_header(step):
#     print("\n-- step {:02d} / {:02d} ---------------------------------------------------".format(
#         step, TOTAL_STEPS
#     ))


# # ─────────────────────────────────────────────────────────────────────────────
# # main simulation
# # ─────────────────────────────────────────────────────────────────────────────

# def main():
#     rng = random.Random(RANDOM_SEED)

#     print_section("citymind — integrated 20-step simulation")

#     # ── phase 0a: ONE shared city graph ───────────────────────────────────────
#     print_section("phase 0a — initialising shared city graph")
#     city = CityGraph(rows=10, cols=10)

#     # ── phase 0b: challenge 1 — csp city layout ───────────────────────────────
#     print_section("phase 0b — challenge 1: csp city layout")
#     planner = run_layout_planner(city)
#     if planner is None:
#         print("[main] ERROR: challenge 1 failed — cannot continue")
#         return
#     print("[main] layout complete | primary hospital: {} | primary depot: {}".format(
#         city.get_label(city.primary_hospital),
#         city.get_label(city.primary_depot)
#     ))

#     # ── phase 0c: challenge 2 — mst road network ──────────────────────────────
#     print_section("phase 0c — challenge 2: mst road network")
#     road_result = build_road_network(city)
#     if not road_result:
#         print("[main] ERROR: challenge 2 failed — cannot continue")
#         return
#     print("[main] road network complete | roads: {} | cost: {:.2f} | redundancy: {}".format(
#         len(road_result["mst_edges"]),
#         road_result["total_cost"],
#         road_result["redundant_edge"] is not None
#     ))
#     redundancy_ok, conn, msg = city.verify_hospital_depot_redundancy()
#     print("[main] redundancy verification: {}".format(msg))
#     if not redundancy_ok:
#         print("[main] WARNING: Hospital-depot path redundancy not satisfied!")

#     # ── phase 0d: challenge 5 — initial risk prediction ───────────────────────
#     print_section("phase 0d — challenge 5: initial crime risk prediction")
#     ml_result = run_risk_pipeline(city)
#     if ml_result is None:
#         print("[main] ERROR: challenge 5 failed — cannot continue")
#         return
#     high, medium, low = count_risk_levels(ml_result["risk_predictions"])
#     print("[main] risk complete | High={} | Medium={} | Low={} | cv={:.4f}".format(
#         high, medium, low, ml_result["cv_accuracy"]
#     ))

#     # ── phase 0e: challenge 3 — initial ambulance placement ───────────────────
#     print_section("phase 0e — challenge 3: initial ambulance placement")
#     best_positions = place_ambulances(city)
#     if not best_positions:
#         print("[main] ERROR: challenge 3 failed — cannot continue")
#         return
#     city.ambulance_positions = best_positions
#     print("[main] ambulances placed:")
#     for i, pos in enumerate(city.ambulance_positions, 1):
#         print("[main]   ambulance {}: {}".format(i, city.get_label(pos)))

#     # ── initial civilian selection ─────────────────────────────────────────────
#     civilians = pick_civilians(city, NUM_CIVILIANS, rng)
#     print("\n[main] initial civilians selected:")
#     for i, civ in enumerate(civilians, 1):
#         print("  civilian {}: {}".format(i, city.get_label(civ)))

#     # ── simulation state counters ──────────────────────────────────────────────
#     total_visited     = 0
#     total_unreachable = 0
#     total_reroutes    = 0
#     total_cost        = 0.0
#     risk_refreshes    = 0
#     amb_repositions   = 0
#     all_floods        = []
    
#     # Track team position for challenge 4 — starts at primary depot
#     team_position = city.primary_depot

#     # ─────────────────────────────────────────────────────────────────────────
#     # 20-step simulation loop
#     # ─────────────────────────────────────────────────────────────────────────
#     print_section("simulation — steps 1 to {}".format(TOTAL_STEPS))

#     for step in range(1, TOTAL_STEPS + 1):
#         city.set_simulation_step(step)
#         print_step_header(step)

#         # ── 1. flood events ────────────────────────────────────────────────────
#         flooded_this_step = generate_flood_events(city, rng)
#         all_floods.extend(flooded_this_step)
#         print("[main] step {:02d}: {} road(s) flooded".format(step, len(flooded_this_step)))

#         # ── 1a. flood recovery — unblock some roads ────────────────────────────
#         # Unblock 0-1 roads per step to prevent permanent isolation
#         # This helps the GA find better placements in later steps
#         if step % 3 == 0:  # Every 3 steps, try to unblock a road
#             unblocked = _unblock_random_roads(city, rng, max_unblocks=1)
#             if unblocked > 0:
#                 print("[main] step {:02d}: {} road(s) unblocked".format(step, unblocked))

#         # ── 2. challenge 4 — a* emergency routing ─────────────────────────────
#         # FIXED: Use current team_position as starting point, not always depot
#         if civilians:
#             routing_result = run_emergency_routing(
#                 city           = city,
#                 civilian_nodes = civilians,
#                 start_node     = team_position,  # FIXED: starts from current team position
#                 flood_schedule = []   # floods already applied above
#             )

#             if routing_result:
#                 step_visited     = len(routing_result["visited"])
#                 step_unreachable = len(routing_result["unreachable"])
#                 step_reroutes    = routing_result["reroutes"]
#                 step_cost        = routing_result["total_cost"]

#                 total_visited     += step_visited
#                 total_unreachable += step_unreachable
#                 total_reroutes    += step_reroutes
#                 total_cost        += step_cost
                
#                 # FIXED: Update team position to the last civilian visited (or last position)
#                 if routing_result["visited"]:
#                     team_position = routing_result["visited"][-1]
#                 elif routing_result["full_path"]:
#                     team_position = routing_result["full_path"][-1]

#                 print("[main] step {:02d}: visited={} | unreachable={} | reroutes={} | cost={:.3f} | team at {}".format(
#                     step, step_visited, step_unreachable, step_reroutes, step_cost,
#                     city.get_label(team_position)
#                 ))
#             else:
#                 print("[main] step {:02d}: routing failed".format(step))

#         # ── 3. every 5 steps: update civilians, risk, and ambulances ──────────
#         if step % RISK_REFRESH_EVERY == 0:

#             # 3a. re-select civilians for the next cycle
#             civilians = pick_civilians(city, NUM_CIVILIANS, rng)
#             if civilians:
#                 print("[main] step {:02d}: civilians refreshed:".format(step))
#                 for i, civ in enumerate(civilians, 1):
#                     print("[main]   civilian {}: {}".format(i, city.get_label(civ)))

#             # 3b. refresh crime risk scores (challenge 5)
#             print("[main] step {:02d}: refreshing risk (challenge 5)".format(step))
#             ml_result = run_risk_pipeline(city)
#             if ml_result:
#                 risk_refreshes += 1
#                 high, medium, low = count_risk_levels(ml_result["risk_predictions"])
#                 print("[main] step {:02d}: risk done | High={} Medium={} Low={} cv={:.4f}".format(
#                     step, high, medium, low, ml_result["cv_accuracy"]
#                 ))

#             # 3c. reposition ambulances (challenge 3) with warm start
#             print("[main] step {:02d}: repositioning ambulances (challenge 3)".format(step))
#             new_positions = place_ambulances(city, seed_chromosome=list(city.ambulance_positions))
#             if new_positions:
#                 amb_repositions += 1
#                 city.ambulance_positions = new_positions
#                 print("[main] step {:02d}: ambulances repositioned:".format(step))
#                 for i, pos in enumerate(city.ambulance_positions, 1):
#                     print("[main]   ambulance {} -> {}".format(i, city.get_label(pos)))

#     # ─────────────────────────────────────────────────────────────────────────
#     # final summary
#     # ─────────────────────────────────────────────────────────────────────────
#     print_section("simulation complete — final summary")

#     blocked_roads = sum(1 for _, _, data in city.get_all_edges() if data["blocked"])

#     print("  total steps           : {}".format(TOTAL_STEPS))
#     print("  total flood events    : {}".format(len(all_floods)))
#     print("  roads blocked (final) : {}".format(blocked_roads))
#     print("  civilians visited     : {}".format(total_visited))
#     print("  civilians unreachable : {}".format(total_unreachable))
#     print("  total reroutes        : {}".format(total_reroutes))
#     print("  total routing cost    : {:.3f}".format(total_cost))
#     print("  risk refreshes        : {}".format(risk_refreshes))
#     print("  ambulance repositions : {}".format(amb_repositions))

#     # final graph validation
#     print("\n-- final graph validation -------------------------------------------")
#     validation = city.validate()
#     print("  result  : {}".format("PASSED" if validation["passed"] else "FAILED"))
#     for err in validation["errors"]:
#         print("  ERROR   : {}".format(err))
#     for warn in validation["warnings"]:
#         print("  warning : {}".format(warn))

#     city.print_risk_grid()

#     print("-- final ambulance positions ----------------------------------------")
#     for i, pos in enumerate(city.ambulance_positions, 1):
#         print("  ambulance {} : {}".format(i, city.get_label(pos)))

#     # event log breakdown by category
#     log           = city.get_log()
#     flood_count   = len([e for e in log if e["category"] == "FLOOD"])
#     reroute_count = len([e for e in log if e["category"] == "REROUTE"])
#     risk_count    = len([e for e in log if e["category"] == "RISK_UPDATE"])
#     isolate_count = len([e for e in log if e["category"] == "ISOLATE"])

#     print("\n-- event log summary ------------------------------------------------")
#     print("  total log entries : {}".format(len(log)))
#     print("  flood events      : {}".format(flood_count))
#     print("  reroute events    : {}".format(reroute_count))
#     print("  risk updates      : {}".format(risk_count))
#     print("  isolation events  : {}".format(isolate_count))

#     print("\n" + "=" * 62)
#     print("  citymind simulation finished successfully")
#     print("=" * 62 + "\n")


# if __name__ == "__main__":
#     main()