"""
test_city_graph.py — tests for phase 0
=======================================
run this file to verify city_graph.py is working correctly before
moving to phase 1.

run with:
    python test_city_graph.py
"""

from city_graph import CityGraph
import math

print("=" * 55)
print("  CityMind — Phase 0 Test Suite")
print("=" * 55)

# ─────────────────────────────────────────────────────────────
# TEST 1: basic construction
# ─────────────────────────────────────────────────────────────
print("\nTEST 1: Build the city graph")

city = CityGraph(rows=10, cols=10)

assert city.graph.number_of_nodes() == 100, "Should have 100 nodes"
# a 10x10 grid has:
#   9x10 horizontal edges + 10x9 vertical edges = 90 + 90 = 180
assert city.graph.number_of_edges() == 180, "Should have 180 edges"

print("  ✓ 100 nodes created")
print("  ✓ 180 edges created")

# ─────────────────────────────────────────────────────────────
# TEST 2: default node values
# ─────────────────────────────────────────────────────────────
print("\nTEST 2: Default node attributes")

node = city.get_node((0, 0))
assert node["location_type"]      == "Empty", "Default type should be Empty"
assert node["population_density"] == 0.0,     "Default population should be 0.0"
assert node["risk_index"]         == 0.0,     "Default risk should be 0.0"
assert node["is_accessible"]      == True,    "Default accessible should be True"

print("  ✓ location_type      = 'Empty'")
print("  ✓ population_density = 0.0")
print("  ✓ risk_index         = 0.0")
print("  ✓ is_accessible      = True")

# ─────────────────────────────────────────────────────────────
# TEST 3: setting node types and population
# ─────────────────────────────────────────────────────────────
print("\nTEST 3: Setting node attributes")

city.set_location_type((0, 0), "Hospital")
city.set_location_type((2, 3), "Residential")
city.set_population_density((0, 0), 5.0)
city.set_population_density((2, 3), 8.5)

assert city.get_location_type((0, 0))      == "Hospital",    "Should be Hospital"
assert city.get_location_type((2, 3))      == "Residential", "Should be Residential"
assert city.get_population_density((0, 0)) == 5.0,           "Should be 5.0"
assert city.get_population_density((2, 3)) == 8.5,           "Should be 8.5"

# verify label was updated automatically by set_location_type
assert city.get_label((0, 0)) == "Hospital(0,0)",    "Label should update to Hospital(0,0)"
assert city.get_label((2, 3)) == "Residential(2,3)", "Label should update to Residential(2,3)"

print("  ✓ location_type set correctly")
print("  ✓ population_density set correctly")
print("  ✓ label auto-updated to include type name")

# ─────────────────────────────────────────────────────────────
# TEST 4: edge costs — residential roads are cheaper
# ─────────────────────────────────────────────────────────────
print("\nTEST 4: Edge base costs")

# (2,3) is Residential, so its edges should cost 0.8
# edge (2,3)-(2,4): (2,3) is Residential, (2,4) is Empty → 0.8
cost_residential = city.graph.edges[(2, 3), (2, 4)]["base_cost"]
assert cost_residential == 0.8, "Road touching Residential should cost 0.8: got {}".format(cost_residential)

# (0,0) is Hospital, (0,1) is still Empty — neither is Residential → 1.0
cost_normal = city.graph.edges[(0, 0), (0, 1)]["base_cost"]
assert cost_normal == 1.0, "Road between non-Residential nodes should cost 1.0: got {}".format(cost_normal)

print("  ✓ Residential edge base_cost = 0.8")
print("  ✓ Non-residential edge base_cost = 1.0")

# ─────────────────────────────────────────────────────────────
# TEST 5: effective cost with risk
# ─────────────────────────────────────────────────────────────
print("\nTEST 5: Effective cost formula")

# set up a clean test pair of nodes with no residential involvement
# (5,5) and (5,6) are both Empty by default → base_cost = 1.0
city.update_risk((5, 5), 0.8)   # high risk node
city.update_risk((5, 6), 0.4)   # medium risk neighbor

# formula: base_cost * (1 + (risk_5_5 + risk_5_6) / 2)
#        = 1.0 * (1 + (0.8 + 0.4) / 2)
#        = 1.0 * (1 + 0.6)
#        = 1.6
expected = 1.0 * (1 + (0.8 + 0.4) / 2)
actual   = city.get_effective_cost((5, 5), (5, 6))

assert abs(actual - expected) < 0.0001, "Effective cost formula incorrect: got {:.4f}".format(actual)
print("  ✓ effective_cost = base × (1 + avg_risk) = {:.2f}".format(actual))

# ─────────────────────────────────────────────────────────────
# TEST 6: blocking a road
# ─────────────────────────────────────────────────────────────
print("\nTEST 6: Blocking roads (flood events)")

# block the road between (5,5) and (5,6)
city.block_road((5, 5), (5, 6))

# effective cost should now be infinity
cost_blocked = city.get_effective_cost((5, 5), (5, 6))
assert cost_blocked == math.inf, "Blocked road should return infinity: got {}".format(cost_blocked)

# (5,6) still has neighbors (5,7), (4,6), (6,6) — so it stays accessible
assert city.get_node((5, 6))["is_accessible"] == True, "Node with open roads should stay accessible"

# now test full isolation on a small grid.
# (1,1) in a 3x3 grid has exactly 4 neighbors: (0,1),(2,1),(1,0),(1,2)
# blocking all 4 should mark (1,1) as inaccessible.
small = CityGraph(rows=3, cols=3)
small.block_road((1, 1), (0, 1))
small.block_road((1, 1), (2, 1))
small.block_road((1, 1), (1, 0))
small.block_road((1, 1), (1, 2))
assert small.get_node((1, 1))["is_accessible"] == False, "Fully isolated node should be inaccessible"

print("  ✓ Blocked edge returns math.inf")
print("  ✓ Partially blocked node stays accessible")
print("  ✓ Fully isolated node marked inaccessible")

# ─────────────────────────────────────────────────────────────
# TEST 7: bfs hop count
# ─────────────────────────────────────────────────────────────
print("\nTEST 7: BFS hop counting")

fresh = CityGraph(rows=5, cols=5)

# from (0,0) to (0,2) = 2 hops (right, right)
assert fresh.bfs_hops((0, 0), (0, 2)) == 2, "Should be 2 hops"

# from (0,0) to (2,2) = 4 hops (2 right + 2 down, or any combination)
assert fresh.bfs_hops((0, 0), (2, 2)) == 4, "Should be 4 hops"

# same node = 0 hops
assert fresh.bfs_hops((1, 1), (1, 1)) == 0, "Same node = 0 hops"

# block both roads out of (0,0) so it becomes a dead end —
# bfs from (0,0) cannot reach (0,2)
fresh.block_road((0, 0), (0, 1))
fresh.block_road((0, 0), (1, 0))
assert fresh.bfs_hops((0, 0), (0, 2)) == math.inf, "Isolated source should return inf hops"

print("  ✓ 2-hop path found correctly")
print("  ✓ 4-hop diagonal path found correctly")
print("  ✓ Same node returns 0")
print("  ✓ Blocked path returns infinity")

# ─────────────────────────────────────────────────────────────
# TEST 8: nodes of type
# ─────────────────────────────────────────────────────────────
print("\nTEST 8: Filtering nodes by type")

city2 = CityGraph(rows=5, cols=5)
city2.set_location_type((0, 0), "Hospital")
city2.set_location_type((1, 1), "Hospital")
city2.set_location_type((2, 2), "School")

hospitals = city2.nodes_of_type("Hospital")
assert len(hospitals) == 2, "Should find 2 hospitals"
assert (0, 0) in hospitals and (1, 1) in hospitals, "Both hospital nodes should be returned"

schools = city2.nodes_of_type("School")
assert len(schools) == 1, "Should find 1 school"
assert (2, 2) in schools, "School node (2,2) should be returned"

print("  ✓ Found {} hospitals: {}".format(len(hospitals), hospitals))
print("  ✓ Found {} school:   {}".format(len(schools),   schools))

# ─────────────────────────────────────────────────────────────
# TEST 9: euclidean distance
# ─────────────────────────────────────────────────────────────
print("\nTEST 9: Euclidean distance helper")

d = CityGraph(rows=5, cols=5).euclidean_distance((0, 0), (3, 4))
expected_d = math.sqrt(3**2 + 4**2)   # = 5.0
assert abs(d - expected_d) < 0.0001, "Distance should be 5.0: got {:.4f}".format(d)
print("  ✓ Distance (0,0)→(3,4) = {:.2f}  (expected {:.2f})".format(d, expected_d))

# ─────────────────────────────────────────────────────────────
# TEST 10: get_open_neighbors_with_cost
# ─────────────────────────────────────────────────────────────
print("\nTEST 10: get_open_neighbors_with_cost")

nc = CityGraph(rows=3, cols=3)
# center node (1,1) has 4 neighbors: (0,1),(2,1),(1,0),(1,2)
# all edges default to base_cost=1.0 and risk=0.0 → effective_cost=1.0
result = nc.get_open_neighbors_with_cost((1, 1))

assert len(result) == 4, "Center node should have 4 neighbors: got {}".format(len(result))

# verify each returned cost is correct: 1.0 * (1 + (0.0+0.0)/2) = 1.0
for neighbor, cost in result:
    assert abs(cost - 1.0) < 0.0001, "Cost should be 1.0 for zero-risk nodes: got {:.4f}".format(cost)

# block one road and check that it disappears from the result
nc.block_road((1, 1), (0, 1))
result_after_block = nc.get_open_neighbors_with_cost((1, 1))
assert len(result_after_block) == 3, "After blocking one road, 3 neighbors should remain"
neighbor_nodes = [n for n, c in result_after_block]
assert (0, 1) not in neighbor_nodes, "Blocked neighbor (0,1) should not appear in results"

print("  ✓ Center node returns 4 neighbors with correct cost 1.0")
print("  ✓ After blocking one road, 3 neighbors remain")
print("  ✓ Blocked neighbor excluded from results")

# ─────────────────────────────────────────────────────────────
# TEST 11: mst_built guard prevents base_cost overwrite
# ─────────────────────────────────────────────────────────────
print("\nTEST 11: mst_built guard on set_location_type")

guard = CityGraph(rows=3, cols=3)

# manually set a custom base cost on an edge — simulating what challenge 2 does
guard.graph.edges[(0, 0), (0, 1)]["base_cost"] = 2.5
guard.mst_built = True  # simulate challenge 2 having finished

# now call set_location_type on a node adjacent to that edge
# without the guard, this would reset base_cost back to 1.0 or 0.8
guard.set_location_type((0, 0), "Residential")

# the custom cost of 2.5 must survive because mst_built is True
preserved_cost = guard.graph.edges[(0, 0), (0, 1)]["base_cost"]
assert abs(preserved_cost - 2.5) < 0.0001, \
    "mst_built guard failed — base_cost was overwritten: got {:.2f}".format(preserved_cost)

print("  ✓ mst_built=True prevents set_location_type from overwriting base costs")
print("  ✓ Custom cost 2.5 preserved after set_location_type call")

# ─────────────────────────────────────────────────────────────
# TEST 12: visual output
# ─────────────────────────────────────────────────────────────
print("\nTEST 12: Visual grid printout")

demo = CityGraph(rows=5, cols=5)
demo.set_location_type((0, 0), "Hospital")
demo.set_location_type((0, 4), "AmbulanceDepot")
demo.set_location_type((2, 2), "School")
demo.set_location_type((4, 0), "Industrial")
demo.set_location_type((4, 4), "PowerPlant")
demo.set_location_type((1, 1), "Residential")
demo.set_location_type((1, 2), "Residential")
demo.set_location_type((3, 3), "Residential")

demo.update_risk((4, 0), 0.8)   # industrial is high risk
demo.update_risk((2, 2), 0.4)   # school is medium risk

demo.print_grid()
demo.print_risk_grid()
demo.summary()

# verify summary validation passes with no errors
validation = demo.validate()
assert validation["passed"] == True, \
    "Demo graph should pass validation. Errors: {}".format(validation["errors"])
print("  ✓ Validation passes on demo graph with no errors")

# ─────────────────────────────────────────────────────────────
# all done
# ─────────────────────────────────────────────────────────────
print("=" * 55)
print("  ALL TESTS PASSED — Phase 0 complete!")
print("  You can now move to Phase 1 (challenge1_csp.py)")
print("=" * 55)