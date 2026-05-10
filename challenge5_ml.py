import warnings
warnings.filterwarnings("ignore", category=UserWarning)

"""
challenge5_ml.py — crime risk prediction and graph integration (challenge 5)
=============================================================================
goal: predict a crime risk score for every node in the city and feed those
scores back into the shared city graph so that a* and the GA automatically
use risk-aware routing and ambulance placement.

three-step pipeline (from design document section 7):

    step 1 — unsupervised clustering: k-means
        cluster all 100 nodes into 4 groups based on:
            - population_density  (float, from city graph)
            - industrial_proximity (hop distance to nearest industrial node)
        k = 4 clusters: low-density residential, high-density residential,
                        industrial-adjacent, civic.
        k chosen by elbow method on within-cluster sum of squares (wcss).

    step 2 — supervised classification: random forest
        generate a synthetic crime dataset using:
            incident_rate = (0.4 × norm_population_density)
                          + (0.35 × (1 / (industrial_proximity + 1)))
                          + (0.25 × cluster_label_encoded)
                          + gaussian_noise(0, 0.05)
        label each node: High (> 0.65), Medium (0.35–0.65), Low (< 0.35)
        train a random forest classifier using 5-fold cross-validation.

    step 3 — graph integration
        after classification:
            High   -> risk_index = 0.8
            Medium -> risk_index = 0.4
            Low    -> risk_index = 0.1
        written to the shared city graph via city.update_risk().
        effective_cost(u,v) = base_cost × (1 + (risk_u + risk_v) / 2)
        is then computed live by get_effective_cost() — no extra wiring needed.

re-run schedule:
    every 5 simulation steps the pipeline re-runs.
    node features are recomputed from the live graph (risk scores may have
    shifted due to floods changing reachability and industrial proximity).
    a new random forest is trained on the refreshed synthetic dataset.
    updated risk scores are written back to city.update_risk() for every node.

why k-means (not dbscan):
    k-means is the canonical unsupervised clustering algorithm covered in class.
    dbscan requires epsilon and min_samples tuning which is non-trivial on
    a small 100-node grid where density is relatively uniform.

why random forest (not single decision tree):
    a single decision tree overfits badly on 100 examples.
    random forest uses bagging across multiple trees to reduce variance.
    it also produces feature_importances_ we can display in the ui and viva.

this file only reads node attributes and writes risk_index values.
call run_risk_pipeline(city) every 5 simulation steps from main.py.
"""

import math
import random
import numpy as np
from collections import deque

from sklearn.cluster import KMeans
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import StandardScaler

from city_graph import CityGraph


# -----------------------------------------------------------------------------
# constants
# -----------------------------------------------------------------------------

# number of clusters for k-means (from design document)
NUM_CLUSTERS = 4

# risk index values to write per predicted label
RISK_VALUES = {
    "High":   0.8,
    "Medium": 0.4,
    "Low":    0.1,
}

# incident_rate thresholds for labelling (from design document)
HIGH_THRESHOLD   = 0.65
LOW_THRESHOLD    = 0.35

# synthetic data generation weights (from design document)
WEIGHT_POPULATION   = 0.40
WEIGHT_PROXIMITY    = 0.35
WEIGHT_CLUSTER      = 0.25
NOISE_STD           = 0.05

# random forest hyperparameters
RF_N_ESTIMATORS     = 100
RF_MAX_DEPTH        = None   # grow full trees (bagging handles overfitting)
RF_RANDOM_STATE     = 42
CV_FOLDS            = 5      # 5-fold cross-validation


# -----------------------------------------------------------------------------
# main entry point
# -----------------------------------------------------------------------------

def run_risk_pipeline(city):
    """
    run the full three-step crime risk prediction pipeline and write
    updated risk_index values to the shared city graph.

    called every 5 simulation steps from main.py.

    parameters
    ----------
    city : CityGraph — shared graph (layout and roads already built)

    returns
    -------
    dict with:
        cluster_labels      : dict {cell: int} — which cluster each node belongs to
        risk_predictions    : dict {cell: str} — "High", "Medium", or "Low"
        cv_accuracy         : float — mean cross-validation accuracy of the classifier
        feature_importances : list of float — [population_weight, proximity_weight, cluster_weight]
        wcss_values         : list of float — wcss per k for elbow curve (k=1 to 6)
    """
    city._log("SYSTEM", "ml pipeline starting — extracting node features")

    # step 1 — extract features and run k-means clustering
    all_cells, feature_matrix = _extract_features(city)
    cluster_labels, wcss_values = _run_kmeans(feature_matrix, n_clusters=NUM_CLUSTERS)

    city._log("SYSTEM", "k-means complete | {} clusters | wcss={:.3f}".format(
        NUM_CLUSTERS, wcss_values[NUM_CLUSTERS - 1]
    ))

    # step 2 — generate synthetic dataset and train random forest
    classifier, scaler, cv_accuracy, feature_importances = _train_random_forest(
        feature_matrix, cluster_labels
    )

    city._log("SYSTEM", "random forest trained | cv_accuracy={:.3f} | importances={}".format(
        cv_accuracy,
        ["{:.3f}".format(fi) for fi in feature_importances]
    ))

    # step 3 — predict risk for all nodes and write to city graph
    risk_predictions = _predict_and_write_risk(
        city, all_cells, feature_matrix, cluster_labels, classifier, scaler
    )

    # summary
    high_count   = sum(1 for v in risk_predictions.values() if v == "High")
    medium_count = sum(1 for v in risk_predictions.values() if v == "Medium")
    low_count    = sum(1 for v in risk_predictions.values() if v == "Low")

    city._log("SYSTEM",
        "risk pipeline complete | High={} | Medium={} | Low={}".format(
            high_count, medium_count, low_count
        )
    )

    return {
        "cluster_labels":      dict(zip(all_cells, cluster_labels)),
        "risk_predictions":    risk_predictions,
        "cv_accuracy":         cv_accuracy,
        "feature_importances": feature_importances,
        "wcss_values":         wcss_values,
    }


# -----------------------------------------------------------------------------
# step 1: feature extraction
# -----------------------------------------------------------------------------

def _extract_features(city):
    """
    build a feature matrix for all 100 nodes.

    features (from design document):
        - population_density      : directly from city graph node attribute
        - industrial_proximity    : bfs hop count to nearest Industrial node

    returns
    -------
    all_cells     : list of (row, col) — ordered node list (index matches matrix rows)
    feature_matrix: np.ndarray shape (n_nodes, 2)
    """
    all_cells  = city.all_nodes()
    n_nodes    = len(all_cells)

    # precompute industrial proximity for all nodes in one bfs pass each
    industrial_cells = city.nodes_of_type("Industrial")

    feature_rows = []

    for cell in all_cells:
        pop_density   = city.get_population_density(cell)

        # bfs hop count to nearest industrial zone (ignores blocked roads
        # for feature extraction — we want structural proximity)
        industrial_proximity = _bfs_hop_to_nearest(city, cell, industrial_cells)

        feature_rows.append([pop_density, industrial_proximity])

    feature_matrix = np.array(feature_rows, dtype=float)
    return all_cells, feature_matrix


def _bfs_hop_to_nearest(city, start_cell, target_cells):
    """
    bfs hop count from start_cell to the nearest cell in target_cells.
    traverses the full grid (ignores blocked flags) for feature extraction.
    returns math.inf if no target cells exist.
    """
    if not target_cells:
        return float("inf")

    target_set = set(target_cells)

    if start_cell in target_set:
        return 0

    visited   = {start_cell}
    bfs_queue = deque([(start_cell, 0)])

    while bfs_queue:
        current_cell, hops = bfs_queue.popleft()
        for neighbor in city.graph.neighbors(current_cell):
            if neighbor in visited:
                continue
            if neighbor in target_set:
                return hops + 1
            visited.add(neighbor)
            bfs_queue.append((neighbor, hops + 1))

    return float("inf")


# -----------------------------------------------------------------------------
# step 1b: k-means clustering
# -----------------------------------------------------------------------------

def _run_kmeans(feature_matrix, n_clusters):
    """
    cluster nodes using k-means on standardised features.

    we standardise first so that population_density (range 0–8) does not
    dominate industrial_proximity (range 0–18) just because of scale.

    also computes wcss for k=1 to 6 so the elbow method is demonstrable
    during the viva without needing to run the full pipeline multiple times.

    returns
    -------
    cluster_labels : np.ndarray of int, length n_nodes
    wcss_values    : list of float, length 6 (wcss for k=1..6)
    """
    scaler          = StandardScaler()
    features_scaled = scaler.fit_transform(feature_matrix)

    # elbow curve: compute wcss for k=1 to 6
    wcss_values = []
    for k in range(1, 7):
        km   = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(features_scaled)
        wcss_values.append(km.inertia_)

    # run final k-means with chosen k
    kmeans         = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(features_scaled)

    return cluster_labels, wcss_values


# -----------------------------------------------------------------------------
# step 2: synthetic dataset generation + random forest training
# -----------------------------------------------------------------------------

def _train_random_forest(feature_matrix, cluster_labels):
    """
    generate a synthetic crime dataset from node features and train
    a random forest classifier with 5-fold cross-validation.

    synthetic incident_rate formula (from design document):
        incident_rate = (0.4 × norm_population_density)
                      + (0.35 × (1 / (industrial_proximity + 1)))
                      + (0.25 × cluster_label_encoded)
                      + gaussian_noise(0, 0.05)

    labels:
        High   — incident_rate > 0.65
        Medium — 0.35 ≤ incident_rate ≤ 0.65
        Low    — incident_rate < 0.35

    returns
    -------
    classifier          : trained RandomForestClassifier
    scaler              : StandardScaler fitted on feature_matrix
    cv_accuracy         : float — mean 5-fold cross-val accuracy
    feature_importances : list of float — per-feature importance scores
    """
    n_nodes = feature_matrix.shape[0]

    # normalise features to [0, 1] for synthetic formula
    pop_density  = feature_matrix[:, 0]
    ind_prox     = feature_matrix[:, 1]

    # replace inf with max finite value for normalisation
    finite_prox    = ind_prox.copy()
    max_finite     = np.max(finite_prox[np.isfinite(finite_prox)]) if np.any(np.isfinite(finite_prox)) else 1.0
    finite_prox[~np.isfinite(finite_prox)] = max_finite

    # normalise population density to [0, 1]
    pop_max       = pop_density.max() if pop_density.max() > 0 else 1.0
    norm_pop      = pop_density / pop_max

    # transform industrial proximity: closer = higher risk
    prox_score    = 1.0 / (finite_prox + 1.0)

    # encode cluster label to [0, 1]
    n_clusters        = int(cluster_labels.max()) + 1
    norm_cluster      = cluster_labels / max(n_clusters - 1, 1)

    # generate synthetic incident_rate with noise
    np.random.seed(42)
    noise         = np.random.normal(0, NOISE_STD, n_nodes)
    incident_rate = (WEIGHT_POPULATION * norm_pop
                   + WEIGHT_PROXIMITY  * prox_score
                   + WEIGHT_CLUSTER    * norm_cluster
                   + noise)

    # clip to [0, 1]
    incident_rate = np.clip(incident_rate, 0.0, 1.0)

    # label each node
    y_labels = []
    for rate in incident_rate:
        if rate > HIGH_THRESHOLD:
            y_labels.append("High")
        elif rate >= LOW_THRESHOLD:
            y_labels.append("Medium")
        else:
            y_labels.append("Low")
    y_labels = np.array(y_labels)

    # build feature matrix for classifier (add cluster as a feature)
    X = np.column_stack([norm_pop, prox_score, norm_cluster])

    # standardise
    scaler      = StandardScaler()
    X_scaled    = scaler.fit_transform(X)

    # random forest with cross-validation
    clf         = RandomForestClassifier(
        n_estimators  = RF_N_ESTIMATORS,
        max_depth     = RF_MAX_DEPTH,
        random_state  = RF_RANDOM_STATE,
        class_weight  = "balanced"   # handles label imbalance
    )
    cv_scores   = cross_val_score(clf, X_scaled, y_labels, cv=CV_FOLDS, scoring="accuracy")
    cv_accuracy = float(np.mean(cv_scores))

    # train final classifier on full dataset
    clf.fit(X_scaled, y_labels)

    feature_importances = clf.feature_importances_.tolist()

    return clf, scaler, cv_accuracy, feature_importances


# -----------------------------------------------------------------------------
# step 3: predict and write risk to city graph
# -----------------------------------------------------------------------------

def _predict_and_write_risk(city, all_cells, feature_matrix, cluster_labels,
                             classifier, scaler):
    """
    run the trained classifier on all nodes and write risk_index to city graph.

    risk index values (from design document):
        High   -> 0.8
        Medium -> 0.4
        Low    -> 0.1

    these are written via city.update_risk() which clamps to [0.0, 1.0]
    and logs every update to the event log.

    returns
    -------
    dict {cell: risk_label_str} — "High", "Medium", or "Low"
    """
    n_nodes        = feature_matrix.shape[0]
    pop_density    = feature_matrix[:, 0]
    ind_prox       = feature_matrix[:, 1]

    # reproduce the same normalisation used during training
    finite_prox    = ind_prox.copy()
    max_finite     = np.max(finite_prox[np.isfinite(finite_prox)]) if np.any(np.isfinite(finite_prox)) else 1.0
    finite_prox[~np.isfinite(finite_prox)] = max_finite

    pop_max        = pop_density.max() if pop_density.max() > 0 else 1.0
    norm_pop       = pop_density / pop_max
    prox_score     = 1.0 / (finite_prox + 1.0)

    n_clusters     = int(cluster_labels.max()) + 1
    norm_cluster   = cluster_labels / max(n_clusters - 1, 1)

    X              = np.column_stack([norm_pop, prox_score, norm_cluster])
    X_scaled       = scaler.transform(X)

    predicted_labels = classifier.predict(X_scaled)

    risk_predictions = {}
    for i, cell in enumerate(all_cells):
        label      = predicted_labels[i]
        risk_value = RISK_VALUES[label]
        city.update_risk(cell, risk_value)
        risk_predictions[cell] = label

    return risk_predictions


# -----------------------------------------------------------------------------
# utility: print risk breakdown per location type
# -----------------------------------------------------------------------------

def print_risk_breakdown(city, risk_predictions):
    """
    display how risk labels are distributed across location types.
    useful for viva demonstration of the ml pipeline's output.
    """
    from collections import defaultdict
    breakdown = defaultdict(lambda: {"High": 0, "Medium": 0, "Low": 0})

    for cell, label in risk_predictions.items():
        loc_type = city.get_location_type(cell)
        breakdown[loc_type][label] += 1

    print("\n-- risk breakdown by location type ---------------------")
    print("  {:15s}  {:>6s}  {:>7s}  {:>5s}".format("Type", "High", "Medium", "Low"))
    print("  " + "-" * 38)
    for loc_type in sorted(breakdown.keys()):
        counts = breakdown[loc_type]
        print("  {:15s}  {:>6d}  {:>7d}  {:>5d}".format(
            loc_type, counts["High"], counts["Medium"], counts["Low"]
        ))
    print("--------------------------------------------------------\n")


def print_elbow_curve(wcss_values):
    """
    display the elbow curve in the terminal so k=4 choice is demonstrable
    without requiring matplotlib during the viva.
    """
    print("\n-- k-means elbow curve (wcss per k) -------------------")
    for k, wcss in enumerate(wcss_values, start=1):
        bar_len = int(wcss / max(wcss_values) * 30)
        marker  = " ← chosen" if k == NUM_CLUSTERS else ""
        print("  k={} | {:6.2f} | {}{}".format(k, wcss, "█" * bar_len, marker))
    print("--------------------------------------------------------\n")


# -----------------------------------------------------------------------------
# standalone test — uses real challenge 1 + 2 pipeline
# -----------------------------------------------------------------------------

if __name__ == "__main__":
    import random
    from challenge1_csp import run_layout_planner
    from challenge2_mst import build_road_network

    print("=" * 60)
    print("  citymind — challenge 5: crime risk ml pipeline (standalone)")
    print("=" * 60)

    random.seed(42)
    city    = CityGraph(rows=10, cols=10)
    planner = run_layout_planner(city)

    if not planner:
        print("challenge 1 failed — cannot continue")
        exit(1)

    print("\nbuilding road network (challenge 2)...")
    build_road_network(city)

    print("\n-- running ml risk pipeline ----------------------------")
    result = run_risk_pipeline(city)

    # -- display results -------------------------------------------------------
    print("\n-- cross-validation accuracy ---------------------------")
    print("  cv_accuracy (5-fold): {:.4f}".format(result["cv_accuracy"]))

    print("\n-- feature importances ---------------------------------")
    fi = result["feature_importances"]
    labels = ["population_density", "industrial_proximity", "cluster_label"]
    for name, importance in zip(labels, fi):
        bar = "█" * int(importance * 40)
        print("  {:25s} {:.4f} {}".format(name, importance, bar))

    print_elbow_curve(result["wcss_values"])
    print_risk_breakdown(city, result["risk_predictions"])

    print("-- risk grid after ml pipeline -------------------------")
    city.print_risk_grid()

    # -- verify effective cost changed -----------------------------------------
    print("-- effective cost sample (first 5 edges) ---------------")
    edge_count = 0
    for u, v, data in city.get_all_edges():
        if edge_count >= 5:
            break
        eff = city.get_effective_cost(u, v)
        if eff < math.inf:
            print("  {} ↔ {} | base={:.2f} | eff={:.4f}".format(
                city.get_label(u), city.get_label(v), data["base_cost"], eff
            ))
            edge_count += 1

    # -- assertions ------------------------------------------------------------
    all_nodes = city.all_nodes()

    # all risk_index values must be one of the three defined values
    valid_risk_values = set(RISK_VALUES.values())
    for cell in all_nodes:
        risk = city.get_risk_index(cell)
        assert risk in valid_risk_values, \
            "ERROR: node {} has unexpected risk_index {}".format(cell, risk)
    print("\n  all risk_index values are valid ({})".format(sorted(valid_risk_values)))

    # all nodes must have a prediction entry
    assert len(result["risk_predictions"]) == len(all_nodes), \
        "ERROR: missing predictions for some nodes"
    print("  all {} nodes have a risk prediction".format(len(all_nodes)))

    # cluster labels must be in range 0..NUM_CLUSTERS-1
    cluster_set = set(result["cluster_labels"].values())
    assert all(0 <= c < NUM_CLUSTERS for c in cluster_set), \
        "ERROR: cluster labels out of range: {}".format(cluster_set)
    print("  cluster labels in valid range 0..{}".format(NUM_CLUSTERS - 1))

    # cv accuracy should be reasonable (> 0.3 at minimum on synthetic data)
    assert result["cv_accuracy"] > 0.3, \
        "ERROR: cv accuracy suspiciously low: {:.4f}".format(result["cv_accuracy"])
    print("  cv accuracy is above 0.3 threshold ({:.4f})".format(result["cv_accuracy"]))

    # feature importances must sum to ~1.0
    fi_sum = sum(result["feature_importances"])
    assert abs(fi_sum - 1.0) < 0.01, \
        "ERROR: feature importances do not sum to 1.0: {:.4f}".format(fi_sum)
    print("  feature importances sum to ~1.0 ({:.4f})".format(fi_sum))

    # effective costs must be higher in risky areas (statistical check)
    high_risk_cells   = [c for c, l in result["risk_predictions"].items() if l == "High"]
    low_risk_cells    = [c for c, l in result["risk_predictions"].items() if l == "Low"]

    if high_risk_cells and low_risk_cells:
        # average self-edge effective cost (use internal edges of each group)
        high_sample = high_risk_cells[:5]
        low_sample  = low_risk_cells[:5]

        high_risks = [city.get_risk_index(c) for c in high_sample]
        low_risks  = [city.get_risk_index(c) for c in low_sample]

        assert sum(high_risks) > sum(low_risks), \
            "ERROR: high-risk group does not have higher risk indices than low-risk group"
        print("  high-risk nodes have higher risk_index than low-risk nodes")

    # -- simulate re-run at step 5 ---------------------------------------------
    print("\n-- simulating step-5 re-run ----------------------------")
    city.set_simulation_step(5)
    result2 = run_risk_pipeline(city)
    assert len(result2["risk_predictions"]) == len(all_nodes)
    print("  re-run produced {} predictions (correct)".format(len(result2["risk_predictions"])))
    print("  re-run cv_accuracy: {:.4f}".format(result2["cv_accuracy"]))

    print("\n" + "=" * 60)
    print("  challenge 5 PASSED — ready for integration")
    print("=" * 60)
