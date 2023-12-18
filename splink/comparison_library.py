from typing import Iterable, List, Union

from . import comparison_level_library as cll
from .comparison_creator import ComparisonCreator
from .comparison_level_creator import ComparisonLevelCreator
from .comparison_level_library import CustomLevel
from .misc import ensure_is_iterable


class CustomComparison(ComparisonCreator):
    def __init__(
        self,
        output_column_name: str,
        comparison_levels: list[Union[ComparisonLevelCreator, dict]],
        description: str = None,
    ):
        """
        Represents a comparison of the data with custom supplied levels.

        Args:
            output_col_name (str): The column name to use to refer to this comparison
            comparison_levels (list): A list of some combination of
                `ComparisonLevelCreator` objects, or dicts. These represent the
                similarity levels assessed by the comparison, in order of decreasing
                specificity
            description (str, optional): An optional description of the comparison
        """

        self._output_column_name = output_column_name
        self._comparison_levels = comparison_levels
        self._description = description

    @staticmethod
    def _convert_to_creator(cl: Union[ComparisonLevelCreator, dict]):
        if isinstance(cl, ComparisonLevelCreator):
            return cl
        if isinstance(cl, dict):
            # TODO: swap this if we develop a more uniform approach to (de)serialising
            return CustomLevel(**cl)
        raise ValueError(
            "`comparison_levels` entries must be `dict` or `ComparisonLevelCreator, "
            f"but found type {type(cl)} for entry {cl}"
        )

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        comparison_level_creators = [
            self._convert_to_creator(cl) for cl in self._comparison_levels
        ]
        return comparison_level_creators

    def create_description(self) -> str:
        # TODO: fleshed out default description?
        return (
            self._description
            if self._description is not None
            else f"Comparison for {self._output_column_name}"
        )

    def create_output_column_name(self) -> str:
        return self._output_column_name


class ExactMatch(ComparisonCreator):
    """
    Represents a comparison of the data in `col_name` with two levels:
        - Exact match in `col_name`
        - Anything else

    Args:
        col_name (str): The name of the column to compare
    """

    def __init__(
        self,
        col_name: str,
        term_frequency_adjustments=False,
    ):
        self.term_frequency_adjustments = term_frequency_adjustments
        super().__init__(col_name)

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        return [
            cll.NullLevel(self.col_expression),
            cll.ExactMatchLevel(
                self.col_expression,
                term_frequency_adjustments=self.term_frequency_adjustments,
            ),
            cll.ElseLevel(),
        ]

    def create_description(self) -> str:
        return f"Exact match '{self.col_expression.label}' vs. anything else"

    def create_output_column_name(self) -> str:
        return self.col_expression.output_column_name


class LevenshteinAtThresholds(ComparisonCreator):
    def __init__(
        self,
        col_name: str,
        distance_threshold_or_thresholds: Union[Iterable[int], int] = [1, 2],
    ):
        """
        Represents a comparison of the data in `col_name` with three or more levels:
            - Exact match in `col_name`
            - Levenshtein levels at specified distance thresholds
            - ...
            - Anything else

        For example, with distance_threshold_or_thresholds = [1, 3] the levels are
            - Exact match in `col_name`
            - Levenshtein distance in `col_name` <= 1
            - Levenshtein distance in `col_name` <= 3
            - Anything else

        Args:
            col_name (str): The name of the column to compare
            distance_threshold_or_thresholds (Union[int, list], optional): The
                threshold(s) to use for the levenshtein similarity level(s).
                Defaults to [1, 2].
        """

        thresholds_as_iterable = ensure_is_iterable(distance_threshold_or_thresholds)
        # unpack it to a list so we can repeat iteration if needed
        self.thresholds = [*thresholds_as_iterable]
        super().__init__(col_name)

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        return [
            cll.NullLevel(self.col_expression),
            cll.ExactMatchLevel(self.col_expression),
            *[
                cll.LevenshteinLevel(self.col_expression, threshold)
                for threshold in self.thresholds
            ],
            cll.ElseLevel(),
        ]

    def create_description(self) -> str:
        comma_separated_thresholds_string = ", ".join(map(str, self.thresholds))
        return (
            f"Exact match '{self.col_expression.label}' vs. "
            f"Levenshtein distance at thresholds "
            f"{comma_separated_thresholds_string} vs. "
            "anything else"
        )

    def create_output_column_name(self) -> str:
        return self.col_expression.output_column_name


class DatediffAtThresholds(ComparisonCreator):
    def __init__(
        self,
        col_name: str,
        *,
        date_metrics: Union[str, list[str]],
        date_thresholds: Union[int, list[int]],
        cast_strings_to_dates: bool = False,
        date_format: str = None,
        term_frequency_adjustments=False,
        invalid_dates_as_null=True,
    ):
        date_metrics_as_iterable = ensure_is_iterable(date_metrics)
        # unpack it to a list so we can repeat iteration if needed
        self.date_metrics = [*date_metrics_as_iterable]

        date_thresholds_as_iterable = ensure_is_iterable(date_thresholds)
        self.date_thresholds = [*date_thresholds_as_iterable]

        self.cast_strings_to_dates = cast_strings_to_dates
        self.date_format = date_format

        self.term_frequency_adjustments = term_frequency_adjustments

        self.invalid_dates_as_null = invalid_dates_as_null

        super().__init__(col_name)

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        col = self.col_expression
        if self.invalid_dates_as_null:
            null_col = col.try_parse_date(self.date_format)
        else:
            null_col = col

        if self.cast_strings_to_dates:
            date_diff_col = col.try_parse_date(self.date_format)
        else:
            date_diff_col = col

        return [
            cll.NullLevel(null_col),
            cll.ExactMatchLevel(
                self.col_expression,
                term_frequency_adjustments=self.term_frequency_adjustments,
            ),
            *[
                cll.DatediffLevel(
                    date_diff_col,
                    date_threshold=date_threshold,
                    date_metric=date_metric,
                )
                for (date_threshold, date_metric) in zip(
                    self.date_thresholds, self.date_metrics
                )
            ],
            cll.ElseLevel(),
        ]

    def create_description(self) -> str:
        return (
            f"Exact match '{self.col_expression.label}' vs. "
            f"date difference at thresholds "
            f"{self.date_thresholds} "
            f"with metrics {self.date_metrics} vs. "
            "anything else"
        )

    def create_output_column_name(self) -> str:
        return self.col_expression.output_column_name
