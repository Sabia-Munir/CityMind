"""ambulance placement via genetic algorithm (challenge 3)
==========================================================================
goal: position 3 ambulances on the city grid so that the worst-case
response time — the distance from the farthest citizen to the nearest
ambulance — is as small as possible.

this is a minimax problem: minimize the maximum distance any citizen
has to travel to reach an ambulance.

algorithm: genetic algorithm (ga)
    why ga over alternatives:
        greedy placement: places one ambulance at a time, each choice
        locks in and restricts future options. no backtracking means
        it misses globally better configurations.

        simulated annealing: improves one solution at a time. can get
        stuck in local optima because it explores one candidate at once.

        ga: keeps a population of 80 different solutions alive at once.
        good positions from different solutions are combined via crossover
        so the algorithm escapes local optima naturally.

    ga structure:
        chromosome   — a list of 3 node positions e.g. [(1,2),(5,7),(8,3)]
        fitness      — worst-case distance: max over all citizen nodes of
                       their shortest path to any ambulance. lower = better.
        selection    — tournament: pick best of 3 random chromosomes
        crossover    — randomly merge two parent chromosomes
        mutation     — with 10% probability, replace one ambulance position
        generations  — 200 max, early stop if no improvement for 20 steps
        population   — 80 chromosomes
        warm start   — previous best solution seeded into the new population
                       when re-running every 5 simulation steps

fixes applied over original version:
    fix 1 — standalone test now uses the real challenge 1 + challenge 2
             pipeline instead of a fake 14-node layout. this gives the ga
             access to all 100 nodes and all 55 residential citizen nodes.
    fix 2 — city_graph now exposes get_open_neighbors_with_cost() so the
             dijkstra inside this file works correctly without accessing
             graph internals directly.
    fix 3 — best_chromosome is now always assigned on the first generation
             (using `is None` check) so it can never remain None even when
             all fitness scores are inf (e.g. after heavy flooding isolates
             most nodes). a post-loop fallback is also added as a safety net.
    fix 4 — fitness function now properly handles unreachable citizens by
             returning a large finite penalty (1e9) instead of inf, so that
             solutions covering many citizens are comparable.
"""

import random
import math
import heapq
from city_graph import CityGraph


# -----------------------------------------------------------------------------
# ga hyperparameters
NUM_AMBULANCES   = 3    # number of ambulances to place
POPULATION_SIZE  = 80   # chromosomes per generation
MAX_GENERATIONS  = 200  # maximum generations to run
NO_IMPROVE_LIMIT = 20   # stop early if no improvement for this many generations
MUTATION_RATE    = 0.10 # probability one ambulance position is randomised
TOURNAMENT_SIZE  = 3    # contestants compared in each tournament selection

# Penalty returned for a chromosome that cannot reach ANY citizen.
# Must match the value used in _fitness() — both use 1000 so the
# fallback threshold (> 500) fires correctly
UNREACHABLE_PENALTY = 1000


def place_ambulances(city, seed_chromosome=None):
    """
    run the genetic algorithm to place NUM_AMBULANCES ambulances on the grid

    the fitness function minimizes the worst-case response distance —
    the maximum shortest-path distance from any citizen node to its
    nearest ambulance.

    risk scores from challenge 5 are automatically included because
    dijkstra uses get_open_neighbors_with_cost() which reads effective_cost
    live from the shared graph. no extra wiring needed.
    """
    # collect all accessible nodes (nodes with at least one open road)
    all_accessible_nodes = [
        cell for cell in city.all_nodes()
        if city.get_node(cell)["is_accessible"]
    ]

    if len(all_accessible_nodes) < NUM_AMBULANCES:
        city._log("SYSTEM", "warning: fewer accessible nodes than ambulances")
        city.ambulance_positions = all_accessible_nodes[:NUM_AMBULANCES]
        return city.ambulance_positions

    # pre-compute all-pairs shortest paths once before the ga loop
    # recomputing inside every fitness call across 200 generations x 80
    # chromosomes would be far too slow.
    city._log("SYSTEM", "pre-computing all-pairs shortest paths for ga fitness...")
    distance_map = _compute_all_distances(city, all_accessible_nodes)

    # citizen nodes: nodes with population > 0 that ambulances must cover
    # uses real population values set by challenge 1  not a hardcoded list
    citizen_nodes = [
        cell for cell in all_accessible_nodes
        if city.get_population_density(cell) > 0
    ]

    if not citizen_nodes:
        citizen_nodes = all_accessible_nodes

    # After heavy flooding, many citizens may be in disconnected components.
    # Filter to only citizens that are reachable from AT LEAST ONE accessible node
    # so the GA optimises over the connected portion of the city.
    reachable_citizens = _filter_reachable_citizens(citizen_nodes, all_accessible_nodes, distance_map)
    if reachable_citizens:
        citizen_nodes = reachable_citizens
        city._log("SYSTEM", "ga: {} of {} citizens are reachable (network fragmentation detected)".format(
            len(reachable_citizens),
            len([c for c in all_accessible_nodes if city.get_population_density(c) > 0])
        ))

    city._log("SYSTEM", "ga starting | {} accessible nodes | {} citizen nodes".format(
        len(all_accessible_nodes), len(citizen_nodes)
    ))

    # initialise population
    population        = _initialise_population(all_accessible_nodes, seed_chromosome)
    best_chromosome   = None
    best_score        = float("inf")
    no_improve_count  = 0

    for generation in range(MAX_GENERATIONS):

        # score every chromosome
        scored_population = []
        for chromosome in population:
            score = _fitness(chromosome, citizen_nodes, distance_map)
            scored_population.append((score, chromosome))

        scored_population.sort(key=lambda x: x[0])

        # update best found so far.
        generation_best_score, generation_best = scored_population[0]
        if best_chromosome is None or generation_best_score < best_score:
            best_score       = generation_best_score
            best_chromosome  = generation_best[:]
            no_improve_count = 0
        else:
            no_improve_count += 1

        # early stop
        if no_improve_count >= NO_IMPROVE_LIMIT:
            city._log("SYSTEM", "ga early stop at generation {} — no improvement for {} generations".format(
                generation, NO_IMPROVE_LIMIT
            ))
            break

        # build next generation
        next_population = []

        # elitism: carry top 2 chromosomes unchanged so best is never lost
        next_population.append(scored_population[0][1][:])
        next_population.append(scored_population[1][1][:])

        chromosomes_only = [chrom for score, chrom in scored_population]
        while len(next_population) < POPULATION_SIZE:
            parent_a = _tournament_select(chromosomes_only, scored_population)
            parent_b = _tournament_select(chromosomes_only, scored_population)
            child    = _crossover(parent_a, parent_b, all_accessible_nodes)
            child    = _mutate(child, all_accessible_nodes)
            next_population.append(child)

        population = next_population

    #if the loop never ran (MAX_GENERATIONS=0) or population
    # was empty, fall back to the first accessible nodes.
    if best_chromosome is None:
        city._log("SYSTEM", "warning: ga produced no result — using fallback positions")
        best_chromosome = all_accessible_nodes[:NUM_AMBULANCES]

    #if the GA found no valid placement (e.g. population was empty)
    if best_chromosome is None:
        city._log("SYSTEM", "ga warning: no valid placement found — using strategic fallback")
        # Fallback: spread ambulances across connected components using BFS.
        # Start from primary hospital/depot then add diverse accessible nodes.
        fallback_positions = []
        if city.primary_hospital and city.get_node(city.primary_hospital)["is_accessible"]:
            fallback_positions.append(city.primary_hospital)
        if city.primary_depot and city.get_node(city.primary_depot)["is_accessible"] \
                and city.primary_depot not in fallback_positions:
            fallback_positions.append(city.primary_depot)

        # Spread remaining slots across accessible nodes, preferring ones
        # distant from already-chosen positions for maximum coverage.
        for candidate in all_accessible_nodes:
            if len(fallback_positions) >= NUM_AMBULANCES:
                break
            if candidate not in fallback_positions:
                fallback_positions.append(candidate)

        # Pad with any accessible node if still short
        for candidate in all_accessible_nodes:
            if len(fallback_positions) >= NUM_AMBULANCES:
                break
            if candidate not in fallback_positions:
                fallback_positions.append(candidate)

        best_chromosome = fallback_positions[:NUM_AMBULANCES]
        best_score = _fitness(best_chromosome, citizen_nodes, distance_map)
        city._log("SYSTEM", "ga using fallback positions | worst-case score: {:.4f}".format(best_score))

    city._log("SYSTEM", "ga complete | best score: {:.4f}".format(best_score))

    # write final positions to shared city graph
    city.ambulance_positions = best_chromosome
    for position in best_chromosome:
        city._log("SYSTEM", "ambulance placed at {}".format(city.get_label(position)))

    return best_chromosome


# -----------------------------------------------------------------------------
# shortest path computation (dijkstra using effective_cost)

def _compute_all_distances(city, nodes):
    """
    run dijkstra from every node and store all pairwise distances

    uses effective_cost (not base_cost) so risk scores from challenge 5
    are automatically factored into ambulance placement

    parameters
    ----------
    city  : CityGraph
    nodes : list of (row, col)

    returns
    -------
    dict: distance_map[source][target] = shortest cost (float)
          unreachable pairs get float("inf")
    """
    node_set     = set(nodes)
    distance_map = {}
    for source in nodes:
        distance_map[source] = _dijkstra(city, source, node_set)
    return distance_map


def _dijkstra(city, source, node_set):
    """
    dijkstra from source to all nodes in node_set
    uses get_open_neighbors_with_cost() from the shared city graph
    so risk-weighted effective costs are used automatically

    parameters
    ----------
    city     : CityGraph
    source   : (row, col)
    node_set : set of (row, col) — nodes to compute distances for

    returns
    -------
    dict: {node: distance} — float("inf") for unreachable nodes
    """
    dist = {node: float("inf") for node in node_set}
    dist[source] = 0.0
    heap = [(0.0, source)]

    while heap:
        current_dist, current_node = heapq.heappop(heap)

        if current_dist > dist[current_node]:
            continue

        for neighbor, edge_cost in city.get_open_neighbors_with_cost(current_node):
            if neighbor not in dist:
                continue
            new_dist = current_dist + edge_cost
            if new_dist < dist[neighbor]:
                dist[neighbor] = new_dist
                heapq.heappush(heap, (new_dist, neighbor))

    return dist


# -----------------------------------------------------------------------------
# ga operators
# -----------------------------------------------------------------------------

def _initialise_population(all_nodes, seed_chromosome):
    """
    create the initial population of POPULATION_SIZE chromosomes.
    each chromosome is NUM_AMBULANCES distinct node positions.
    seed_chromosome is inserted at index 0 if provided (warm start).
    """
    population = []

    if seed_chromosome is not None:
        valid_seed = [pos for pos in seed_chromosome if pos in all_nodes]
        if len(valid_seed) == NUM_AMBULANCES:
            population.append(valid_seed)

    while len(population) < POPULATION_SIZE:
        chromosome = random.sample(all_nodes, NUM_AMBULANCES)
        population.append(chromosome)

    return population


def _fitness(chromosome, citizen_nodes, distance_map):
    """
    Evaluate a chromosome (list of ambulance positions) by worst-case
    response distance — the maximum shortest-path from any citizen node
    to its nearest ambulance.

    Unreachable citizens add a cumulative UNREACHABLE_PENALTY (1000) so that
    chromosomes covering more citizens always score better than those
    that leave citizens completely isolated.
    """
    citizen_distances = []
    unreachable_count = 0

    for citizen in citizen_nodes:
        nearest_dist = float("inf")

        for ambulance_pos in chromosome:
            dist = distance_map.get(ambulance_pos, {}).get(citizen, float("inf"))
            if dist < nearest_dist:
                nearest_dist = dist

        if nearest_dist == float("inf"):
            unreachable_count += 1
        else:
            citizen_distances.append(nearest_dist)

    base_dist = max(citizen_distances) if citizen_distances else 0.0
    return base_dist + (unreachable_count * UNREACHABLE_PENALTY)


def _filter_reachable_citizens(citizen_nodes, all_accessible_nodes, distance_map):
    """
    Return the subset of citizen_nodes that are reachable from at least
    one accessible node in the distance map.  Called before the GA loop
    so that after heavy flooding the GA still optimises over citizens it
    CAN reach rather than always returning UNREACHABLE_PENALTY.
    """
    reachable = []
    for citizen in citizen_nodes:
        for source in all_accessible_nodes:
            d = distance_map.get(source, {}).get(citizen, float("inf"))
            if d < float("inf"):
                reachable.append(citizen)
                break
    return reachable if reachable else citizen_nodes


def _tournament_select(chromosomes_only, scored_population):
    """
    tournament selection: pick TOURNAMENT_SIZE random chromosomes and
    return the one with the lowest fitness score.
    uses index-based lookup to avoid id() memory-aliasing bugs between generations.
    keeps the same tournament semantics described in the design document.
    """
    indices  = random.sample(range(len(scored_population)), min(TOURNAMENT_SIZE, len(scored_population)))
    best_idx = min(indices, key=lambda i: scored_population[i][0])
    return scored_population[best_idx][1][:]


def _crossover(parent_a, parent_b, all_nodes):
    """
    combine two parents to produce one child chromosome.
    for each slot randomly picks from parent_a or parent_b.
    duplicates are replaced with random unused nodes.
    """
    child      = []
    used_nodes = set()

    for i in range(NUM_AMBULANCES):
        candidate = parent_a[i] if random.random() < 0.5 else parent_b[i]

        if candidate not in used_nodes:
            child.append(candidate)
            used_nodes.add(candidate)
        else:
            available = [n for n in all_nodes if n not in used_nodes]
            if available:
                replacement = random.choice(available)
                child.append(replacement)
                used_nodes.add(replacement)
            else:
                child.append(candidate)

    return child


def _mutate(chromosome, all_nodes):
    """
    with probability MUTATION_RATE, replace one random ambulance position
    with a random unused node. prevents premature convergence.
    """
    if random.random() < MUTATION_RATE:
        slot_to_mutate    = random.randint(0, NUM_AMBULANCES - 1)
        current_positions = set(chromosome)
        available         = [n for n in all_nodes if n not in current_positions]

        if available:
            chromosome                 = chromosome[:]
            chromosome[slot_to_mutate] = random.choice(available)

    return chromosome


# -----------------------------------------------------------------------------
# standalone test — uses real challenge 1 + challenge 2 pipeline
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    from challenge1_csp import run_layout_planner
    from challenge2_mst import build_road_network

    print("=" * 55)
    print("  challenge 3 — ga ambulance placement (standalone test)")
    print("=" * 55)

    # use real challenge 1 layout — not a fake sparse layout
    # this gives the ga all 100 nodes and all 55 residential citizen nodes
    random.seed(42)
    city    = CityGraph(rows=10, cols=10)
    planner = run_layout_planner(city)

    if not planner:
        print("challenge 1 failed — cannot continue")
        exit(1)

    print("\nstep 1: building road network (challenge 2)...")
    build_road_network(city)

    print("\nstep 2: running genetic algorithm...")
    best_positions = place_ambulances(city)

    print("\n-- results -----------------------------------------")
    for i, pos in enumerate(best_positions):
        print("  ambulance {}: {}".format(i + 1, city.get_label(pos)))

    # verify correct number of ambulances
    assert len(best_positions) == NUM_AMBULANCES, \
        "ERROR: expected {} positions, got {}".format(NUM_AMBULANCES, len(best_positions))
    print("\n  correct number of ambulances placed ({})".format(NUM_AMBULANCES))

    # verify all positions are distinct
    assert len(set(best_positions)) == NUM_AMBULANCES, \
        "ERROR: duplicate ambulance positions found"
    print("  all positions are distinct")

    # verify all positions are valid grid nodes
    all_nodes = city.all_nodes()
    for pos in best_positions:
        assert pos in all_nodes, "ERROR: {} is not a valid node".format(pos)
    print("  all positions are valid grid nodes")

    # verify written to city.ambulance_positions
    assert city.ambulance_positions == best_positions
    print("  positions written to city.ambulance_positions")

    # verify citizen node count is correct (should be ~100 since all nodes have pop > 0)
    citizen_count = len([c for c in city.all_nodes() if city.get_population_density(c) > 0])
    print("  citizen nodes covered: {}".format(citizen_count))

    # test warm start re-run
    print("\nstep 3: testing warm start re-run...")
    new_positions = place_ambulances(city, seed_chromosome=best_positions)
    assert len(new_positions) == NUM_AMBULANCES
    print("  warm start re-run completed successfully")
    print("  new positions: {}".format([city.get_label(p) for p in new_positions]))

    print("\n" + "=" * 55)
    print("  challenge 3 PASSED — ready for integration")
    print("=" * 55)