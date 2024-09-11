import pytest

from splink.comparison_library import ArrayIntersectAtSizes
from tests.decorator import mark_with_dialects_excluding
from tests.literal_utils import run_comparison_vector_value_tests


@mark_with_dialects_excluding("sqlite", "spark")
def test_array_comparison_1(test_helpers, dialect):
    helper = test_helpers[dialect]
    db_api = helper.extra_linker_args()["db_api"]

    test_cases = [
        {
            "comparison": ArrayIntersectAtSizes("arr", [4, 3, 2, 1]),
            "inputs": [
                {
                    "arr_l": ["A", "B", "C", "D"],
                    "arr_r": ["A", "B", "C", "D"],
                    "expected_value": 4,
                    "expected_label": "Array intersection size >= 4",
                },
                {
                    "arr_l": ["A", "B", "C", "D"],
                    "arr_r": ["A", "B", "C", "Z"],
                    "expected_value": 3,
                    "expected_label": "Array intersection size >= 3",
                },
                {
                    "arr_l": ["A", "B"],
                    "arr_r": ["A", "B", "C", "D"],
                    "expected_value": 2,
                    "expected_label": "Array intersection size >= 2",
                },
                {
                    "arr_l": ["A", "B", "C", "D"],
                    "arr_r": ["X", "Y", "Z"],
                    "expected_value": 0,
                    "expected_label": "All other comparisons",
                },
            ],
        },
        {
            "comparison": ArrayIntersectAtSizes("arr", [4, 1]),
            "inputs": [
                {
                    "arr_l": ["A", "B", "C", "D"],
                    "arr_r": ["A", "B", "C", "D"],
                    "expected_value": 2,
                    "expected_label": "Array intersection size >= 4",
                },
                {
                    "arr_l": ["A", "B", "C", "D"],
                    "arr_r": ["A", "B", "C", "Z"],
                    "expected_value": 1,
                    "expected_label": "Array intersection size >= 1",
                },
                {
                    "arr_l": ["A", "B"],
                    "arr_r": ["A", "B", "C", "D"],
                    "expected_value": 1,
                    "expected_label": "Array intersection size >= 1",
                },
                {
                    "arr_l": ["A"],
                    "arr_r": ["X", "Y", "Z"],
                    "expected_value": 0,
                    "expected_label": "All other comparisons",
                },
            ],
        },
    ]

    run_comparison_vector_value_tests(test_cases, db_api)

    # Test for ValueError with negative sizes
    with pytest.raises(ValueError):
        ArrayIntersectAtSizes("postcode", [-1, 2]).get_comparison(
            db_api.sql_dialect.sqlglot_name
        )


# No SQLite - no array comparisons in library
@mark_with_dialects_excluding("sqlite")
def test_array_subset(test_helpers, dialect):
    helper = test_helpers[dialect]
    db_api = helper.extra_linker_args()["db_api"]

    test_spec = ComparisonLevelTestSpec(
        cll.ArraySubsetLevel("arr"),
        tests=[
            LiteralTestValues(
                {"arr_l": ["A", "B", "C", "D"], "arr_r": ["A", "B", "C", "D"]},
                expected_in_level=True,
            ),
            LiteralTestValues(
                {"arr_l": ["A", "B", "C", "D"], "arr_r": ["A", "B", "C", "Z"]},
                expected_in_level=False,
            ),
            LiteralTestValues(
                {"arr_l": ["A", "B"], "arr_r": ["A", "B", "C", "D"]},
                expected_in_level=True,
            ),
            LiteralTestValues(
                {"arr_l": ["A", "B", "C", "D"], "arr_r": ["X", "Y", "Z"]},
                expected_in_level=False,
            ),
            LiteralTestValues(
                {"arr_l": [], "arr_r": ["X", "Y", "Z"]},
                expected_in_level=False,
            ),
        ],
    )
    run_tests_with_args(test_spec, db_api)
