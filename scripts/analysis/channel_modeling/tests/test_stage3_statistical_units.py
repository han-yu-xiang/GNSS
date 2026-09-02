import sys
from pathlib import Path


HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from audit_stage3_statistical_units import (  # noqa: E402
    classify_association_edge,
    connected_components,
    parse_match_pattern_support,
    normalized_cluster_weights,
)


def test_parse_match_pattern_maps_existing_offsets_to_window_ids():
    support = parse_match_pattern_support("10101", center_window_id=100)
    assert support == {"98", "100", "102"}


def test_reciprocal_same_position_match_is_a_definite_algorithm_link():
    left = {"center_window_id": "100", "multipath_id": "1", "selected_L": "3"}
    right = {"center_window_id": "102", "multipath_id": "1", "selected_L": "3"}
    result = classify_association_edge(
        left,
        right,
        left_support={"98", "100", "102"},
        right_support={"100", "102", "104"},
    )
    assert result["edge_class"] == "DEFINITE_ALGORITHM_LINK"
    assert result["merge_allowed"] is True
    assert result["reciprocal_direct_match"] is True


def test_overlapping_footprints_are_not_merged_when_path_positions_differ():
    left = {"center_window_id": "100", "multipath_id": "1", "selected_L": "3"}
    right = {"center_window_id": "102", "multipath_id": "2", "selected_L": "3"}
    result = classify_association_edge(
        left,
        right,
        left_support={"98", "100", "102"},
        right_support={"100", "102", "104"},
    )
    assert result["edge_class"] == "AMBIGUOUS"
    assert result["merge_allowed"] is False


def test_no_shared_existing_support_is_no_link():
    left = {"center_window_id": "100", "multipath_id": "1", "selected_L": "3"}
    right = {"center_window_id": "104", "multipath_id": "1", "selected_L": "3"}
    result = classify_association_edge(
        left,
        right,
        left_support={"98", "100"},
        right_support={"104", "106"},
    )
    assert result["edge_class"] == "NO_LINK"
    assert result["merge_allowed"] is False


def test_connected_components_use_only_explicit_merge_edges():
    nodes = ["a", "b", "c", "d"]
    edges = [("a", "b"), ("b", "c")]
    components = connected_components(nodes, edges)
    assert sorted(sorted(component) for component in components) == [["a", "b", "c"], ["d"]]


def test_normalized_cluster_weights_sum_to_one_per_cluster():
    weights = normalized_cluster_weights(
        [("track-1", "a"), ("track-1", "b"), ("track-2", "c")]
    )
    assert weights == {"a": 0.5, "b": 0.5, "c": 1.0}
