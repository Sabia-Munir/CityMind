#challenge2_mst.py  road network optimization (challenge 2)

import networkx as nx
from city_graph import CityGraph

def build_road_network(city):
    #build weighted graph for kruskal
    cost_graph = _build_cost_graph(city) 

    #running kruskals on it will find the cheapest node among all 100 nodes wihotu any loops
    mst = nx.minimum_spanning_tree(cost_graph, algorithm="kruskal", weight="weight")

    #identify primary hospital and depot
    #if challenge 1 already set these, we respect them
    #if not (e.g. standalone test), we compute them here
    if city.primary_hospital is None or city.primary_depot is None: #finding primary based on the population density and proximity
        primary_hospital, primary_depot = _identify_primary_nodes(city, mst)
        city.primary_hospital = primary_hospital
        city.primary_depot    = primary_depot
    else:
        primary_hospital = city.primary_hospital
        primary_depot    = city.primary_depot

    city._log("SYSTEM", "primary hospital: {}".format(city.get_label(primary_hospital)))
    city._log("SYSTEM", "primary depot:    {}".format(city.get_label(primary_depot)))

    #ensure two independent paths between hospital and depot
    connectivity   = nx.edge_connectivity(mst, primary_hospital, primary_depot)
    redundant_edge = None

    if connectivity < 2:
        city._log("SYSTEM", "only 1 path between hospital and depot — adding redundancy edge")
        redundant_edge = _add_redundancy_edge(
            city, mst, cost_graph, primary_hospital, primary_depot
        )
        if redundant_edge is None:
            #force-add the direct grid neighbor edge if it exists
            redundant_edge = _force_redundancy_fallback(
                city, mst, cost_graph, primary_hospital, primary_depot
            )
    else:
        city._log("SYSTEM", "hospital and depot already have {} independent paths".format(
            connectivity
        ))

    #write mst edges and costs to shared city graph
    total_cost = 0.0
    mst_edges  = []

    for u, v, data in mst.edges(data=True):
        edge_cost = data["weight"]
        city.set_base_cost(u, v, edge_cost)
        total_cost += edge_cost
        mst_edges.append((u, v))

    #mark mst as built
    city.mst_built = True

    city._log("SYSTEM", "road network complete | {} roads | total cost {:.2f}".format(
        len(mst_edges), total_cost
    ))
    
    #block all non-mst edges — only mst roads are actual roads
    mst_edge_set = set()
    for u, v in mst_edges:
        mst_edge_set.add((min(u, v), max(u, v)))
    if redundant_edge:
        ru, rv = redundant_edge
        mst_edge_set.add((min(ru, rv), max(ru, rv)))

    for cell_a, cell_b, _ in city.get_all_edges():
        key = (min(cell_a, cell_b), max(cell_a, cell_b))
        if key not in mst_edge_set:
            city.graph.edges[cell_a, cell_b]["blocked"] = True

    city._log("SYSTEM", "non-mst edges blocked | {} roads active | {} edges blocked".format(
        len(mst_edge_set),
        sum(1 for _, _, d in city.get_all_edges() if d["blocked"])
    ))
    return {
        "mst_edges":        mst_edges,
        "total_cost":       total_cost,
        "primary_hospital": primary_hospital,
        "primary_depot":    primary_depot,
        "redundant_edge":   redundant_edge
    }


#build the weighted graph kruskal runs on

def _build_cost_graph(city):
    """
    create a networkx graph with all possible roads and their correct costs.
    cost rules from the project specification:
        road touching a residential zone = 0.8 all other roads  = 1.0
    """
    cost_graph = nx.Graph()

    for cell in city.all_nodes():
        cost_graph.add_node(cell)

    for cell_a, cell_b, road_data in city.get_all_edges():
        type_a = city.get_location_type(cell_a)
        type_b = city.get_location_type(cell_b)

        if type_a == "Residential" or type_b == "Residential":
            weight = 0.8
        else:
            weight = 1.0

        cost_graph.add_edge(cell_a, cell_b, weight=weight)

    return cost_graph


#identify primary hospital and primary depot


def _identify_primary_nodes(city, mst):
    """
    primary hospital — hospital with highest total nearby population (2 hops in mst)
    primary depot    — depot closest by path distance to the primary hospital
    """
    hospitals = city.nodes_of_type("Hospital")
    depots    = city.nodes_of_type("AmbulanceDepot")

    if not hospitals:
        city._log("SYSTEM", "warning: no hospitals in layout — using (0,0)")
        primary_hospital = (0, 0)
    else:
        best_hospital   = hospitals[0]
        best_population = 0.0
        for hospital in hospitals:
            pop = _population_within_hops(city, mst, hospital, max_hops=2)
            if pop > best_population:
                best_population = pop
                best_hospital   = hospital
        primary_hospital = best_hospital

    if not depots:
        city._log("SYSTEM", "warning: no depots in layout — using (0,0)")
        primary_depot = (0, 0)
    else:
        best_depot    = depots[0]
        best_distance = float("inf")
        for depot in depots:
            try:
                dist = nx.shortest_path_length(mst, primary_hospital, depot, weight="weight")
                if dist < best_distance:
                    best_distance = dist
                    best_depot    = depot
            except nx.NetworkXNoPath:
                continue
        primary_depot = best_depot

    return primary_hospital, primary_depot


def _population_within_hops(city, mst, start_cell, max_hops):
    """sum population density of all nodes within max_hops in the mst"""
    from collections import deque
    visited          = {start_cell}
    queue            = deque([(start_cell, 0)])
    total_population = city.get_population_density(start_cell)

    while queue:
        current, hops = queue.popleft()
        if hops >= max_hops:
            continue
        for neighbor in mst.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                total_population += city.get_population_density(neighbor)
                queue.append((neighbor, hops + 1))

    return total_population


#add cheapest redundancy edge
def _add_redundancy_edge(city, mst, cost_graph, hospital, depot):
    """
    find and add the cheapest non-mst edge that creates a second edge-disjoint path between hospital and depot
    why this works:
        the mst is a tree — exactly one path between any two nodes
        adding any edge creates exactly one new cycle
        if that cycle passes through both hospital and depot,
        a second independent path now exists between them.

    tries edges whose endpoints are on the existing
    hospital-depot path first — these are most likely to form a
    useful cycle. only falls back to non-path edges if needed.
    """
    #build set of mst edges for fast lookup
    mst_edge_set = set()
    for u, v in mst.edges():
        mst_edge_set.add((min(u, v), max(u, v)))

    # get the current unique path from hospital to depot
    try:
        current_path = nx.shortest_path(mst, hospital, depot)#it will store the very firts shoerteset path from hospitaal to depot and store it 
        path_nodes   = set(current_path)
    except nx.NetworkXNoPath:
        city._log("SYSTEM", "warning: hospital and depot not connected in mst")
        return None

    # collect all non-mst candidate edges
    candidate_edges = []
    for u, v, data in cost_graph.edges(data=True):
        edge_key = (min(u, v), max(u, v))
        if edge_key not in mst_edge_set:
            candidate_edges.append((data["weight"], u, v)) # we will store them for the backup ruote 

    candidate_edges.sort(key=lambda x: x[0])

    # try path-adjacent edges first (both endpoints on the path),
    # then single-endpoint edges, then all others
    # this prioritises edges that are most likely to form a useful cycle
    both_on_path  = [(w, u, v) for w, u, v in candidate_edges
                     if u in path_nodes and v in path_nodes]
    one_on_path   = [(w, u, v) for w, u, v in candidate_edges
                     if (u in path_nodes) != (v in path_nodes)]
    neither       = [(w, u, v) for w, u, v in candidate_edges
                     if u not in path_nodes and v not in path_nodes]

    ordered_candidates = both_on_path + one_on_path + neither

    for weight, u, v in ordered_candidates:
        mst.add_edge(u, v, weight=weight)

        if nx.edge_connectivity(mst, hospital, depot) >= 2:
            city.set_base_cost(u, v, weight)
            city._log("SYSTEM", "redundancy edge added: {} <-> {} (cost {:.2f})".format(
                city.get_label(u), city.get_label(v), weight
            ))
            return (u, v)
        else:
            mst.remove_edge(u, v)

    return None


def _force_redundancy_fallback(city, mst, cost_graph, hospital, depot):
    """
    Challenge 2: If normal redundancy search fails to find a cycle-creating
    non-MST edge (which happens if all potential edges are already in the MST),
    we must strictly guarantee redundancy
    
    this function finds any neighbor of the hospital and any neighbor of the
    depot in the original 10x10 grid (ignoring blocked edges) and adds a direct
    path between them to force a cycle
    """
    # Force a direct loop connection between a neighbor of hospital and neighbor of depot
    # Using the full grid coordinates (not just current graph edges) to guarantee we find one
    hx, hy = hospital
    dx, dy = depot
    
    # Get all valid grid neighbors
    def get_grid_neighbors(x, y):
        nbs = []
        for nx_coord, ny_coord in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
            if 0 <= nx_coord < 10 and 0 <= ny_coord < 10:
                # We need the node type from the city graph to form the proper tuple
                for n in city.all_nodes():
                    if n[0] == nx_coord and n[1] == ny_coord:
                        nbs.append(n)
                        break
        return nbs

    hospital_neighbors = get_grid_neighbors(hx, hy)
    depot_neighbors = get_grid_neighbors(dx, dy)
    
    for h_nb in hospital_neighbors + [hospital]:#check neighbor of hospital to every meighbor of the depot
        for d_nb in depot_neighbors + [depot]:
            if h_nb != d_nb and not mst.has_edge(h_nb, d_nb): #if un dono ka neighbor same nhi and edge b exist krta to make a ruote
                # Force add the edge
                mst.add_edge(h_nb, d_nb, weight=1.0)
                if nx.edge_connectivity(mst, hospital, depot) >= 2:
                    city.set_base_cost(h_nb, d_nb, 1.0)
                    city.graph.add_edge(h_nb, d_nb, weight=1.0, cost=1.0, blocked=False)
                    city._log("SYSTEM", "redundancy fallback: forced edge {} <-> {} added".format(
                        city.get_label(h_nb), city.get_label(d_nb)
                    ))
                    return (h_nb, d_nb)
                else:
                    mst.remove_edge(h_nb, d_nb)
    
    city._log("SYSTEM", "warning: all redundancy attempts failed (graph may be fully connected)")
    return None


# -----------------------------------------------------------------------------
# standalone test — uses real challenge 1 layout
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import random
    from challenge1_csp import run_layout_planner

    print("=" * 55)
    print("  challenge 2 — mst road network (standalone test)")
    print("=" * 55)

    # use the real challenge 1 layout — not a fake sparse one
    # this ensures the redundancy search always has enough nodes to work with
    random.seed(42)
    city    = CityGraph(rows=10, cols=10)
    planner = run_layout_planner(city)

    if not planner:
        print("challenge 1 failed — cannot run challenge 2")
        exit(1)

    city.print_grid()

    print("\nbuilding road network...")
    result = build_road_network(city)

    print("\n-- results -----------------------------------------")
    print("  total roads built : {}".format(len(result["mst_edges"])))
    print("  total cost        : {:.2f}".format(result["total_cost"]))
    print("  primary hospital  : {}".format(city.get_label(result["primary_hospital"])))
    print("  primary depot     : {}".format(city.get_label(result["primary_depot"])))
    print("  redundancy edge   : {}".format(result["redundant_edge"]))

    # verify all 100 nodes are connected
    verify_graph = nx.Graph()
    for u, v in result["mst_edges"]:
        verify_graph.add_edge(u, v)
    if result["redundant_edge"]:
        verify_graph.add_edge(*result["redundant_edge"])
    for cell in city.all_nodes():
        verify_graph.add_node(cell)

    assert nx.is_connected(verify_graph), "ERROR: not all nodes are connected"
    print("\n  all 100 nodes are connected")

    conn = nx.edge_connectivity(
        verify_graph, result["primary_hospital"], result["primary_depot"]
    )
    assert conn >= 2, "ERROR: hospital-depot connectivity is {}".format(conn)
    print("  hospital-depot has {} independent path(s)".format(conn))

    assert hasattr(city, "mst_built") and city.mst_built
    print("  mst_built flag set correctly")

    blocked = sum(
        1 for u, v in result["mst_edges"]
        if city.get_effective_cost(u, v) == float("inf")
    )
    assert blocked == 0
    print("  all mst edges have finite effective cost")

    print("\n" + "=" * 55)
    print("  challenge 2 PASSED — ready for integration")
    print("=" * 55)