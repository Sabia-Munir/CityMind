
import config

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

    num_floods    = min(rng.randint(0, config.MAX_FLOODS_PER_STEP), len(unblocked_edges))
    flooded_edges = rng.sample(unblocked_edges, num_floods)

    flooded = []
    for a, b in flooded_edges:
        # We don't block it here! We let the A* router block it mid-journey
        flooded.append((a, b))
    return flooded



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

