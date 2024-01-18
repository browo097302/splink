from typing import List, Union

from . import comparison_level_library as cll
from .column_expression import ColumnExpression
from .comparison_creator import ComparisonCreator
from .comparison_level_creator import ComparisonLevelCreator
from .misc import ensure_is_iterable

_fuzzy_levels = {
    "damerau_levenshtein": cll.DamerauLevenshteinLevel,
    "jaro": cll.JaroLevel,
    "jaro_winkler": cll.JaroWinklerLevel,
    "levenshtein": cll.LevenshteinLevel,
}
# metric names single quoted and comma-separated for error messages
_AVAILABLE_METRICS_STRING = ", ".join(map(lambda x: f"'{x}'", _fuzzy_levels.keys()))


class DateComparison(ComparisonCreator):
    """
    A wrapper to generate a comparison for a date column the data in
    `col_name` with preselected defaults.

    The default arguments will give a comparison with comparison levels:\n
    - Exact match (1st of January only)
    - Exact match (all other dates)
    - Damerau-Levenshtein distance <= 1
    - Date difference <= 1 month
    - Date difference <= 1 year
    - Date difference <= 10 years
    - Anything else
    """

    def __init__(
        self,
        col_name: Union[str, ColumnExpression],
        *,
        date_format: str = None,
        invalid_dates_as_null: bool = False,
        include_exact_match_level: bool = True,
        separate_1st_january: bool = False,
        fuzzy_metric: str = "damerau_levenshtein",
        fuzzy_thresholds: Union[float, List[float]] = [1],
        datediff_thresholds: Union[int, List[int]] = [1, 1, 10],
        datediff_metrics: Union[str, List[str]] = ["month", "year", "year"],
    ):
        fuzzy_thresholds_as_iterable = ensure_is_iterable(fuzzy_thresholds)
        self.fuzzy_thresholds = [*fuzzy_thresholds_as_iterable]

        date_thresholds_as_iterable = ensure_is_iterable(datediff_thresholds)
        self.date_thresholds = [*date_thresholds_as_iterable]
        date_metrics_as_iterable = ensure_is_iterable(datediff_metrics)
        self.date_metrics = [*date_metrics_as_iterable]
        # TODO: check lengths match!

        self.date_format = date_format
        self.invalid_dates_as_null = invalid_dates_as_null

        self.separate_1st_january = separate_1st_january
        self.exact_match = include_exact_match_level

        if self.fuzzy_thresholds:
            try:
                self.fuzzy_level = _fuzzy_levels[fuzzy_metric]
            except KeyError:
                raise ValueError(
                    f"Invalid value for {fuzzy_metric=}.  "
                    f"Must choose one of: {_AVAILABLE_METRICS_STRING}."
                ) from None
            # store metric for description
            self.fuzzy_metric = fuzzy_metric

        super().__init__(col_name)

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        col_expression = self.col_expression

        levels = [
            # Null level accept pattern if not None, otherwise will ignore
            cll.NullLevel(
                col_expression,
                valid_string_pattern=self.date_format,
                invalid_dates_as_null=self.invalid_dates_as_null,
            ),
        ]
        if self.separate_1st_january:
            levels.append(
                cll.And(
                    cll.CustomLevel(
                        # TODO: surely this depends on date format??
                        sql_condition=(
                            f"SUBSTR({col_expression.name_l}, 6, 5) = '01-01'"
                        ),
                        label_for_charts="Match 1st Jan.",
                    ),
                    cll.ExactMatchLevel(col_expression),
                )
            )
        if self.exact_match:
            levels.append(cll.ExactMatchLevel(col_expression))

        if self.fuzzy_thresholds:
            levels.extend(
                [
                    self.fuzzy_level(col_expression, threshold)
                    for threshold in self.fuzzy_thresholds
                ]
            )
        if self.date_thresholds:
            for threshold, metric in zip(self.date_thresholds, self.date_metrics):
                levels.append(
                    cll.DatediffLevel(
                        col_expression, date_threshold=threshold, date_metric=metric
                    )
                )

        levels.append(cll.ElseLevel())
        return levels

    def create_description(self) -> str:
        comparison_desc = ""
        if self.exact_match:
            comparison_desc += "Exact match "
            if self.separate_1st_january:
                comparison_desc += "(with separate 1st Jan) "
            comparison_desc += "vs. "

        if self.fuzzy_thresholds:
            comma_separated_thresholds_string = ", ".join(
                map(str, self.fuzzy_thresholds)
            )
            plural = "s" if len(self.fuzzy_thresholds) > 1 else ""
            comparison_desc = (
                f"{self.fuzzy_metric} at threshold{plural} "
                f"{comma_separated_thresholds_string} vs. "
            )

        if self.date_thresholds:
            datediff_separated_thresholds_string = ", ".join(
                [
                    f"{m.title()}(s): {v}"
                    for v, m in zip(self.date_thresholds, self.date_metrics)
                ]
            )
            plural = "s" if len(self.date_thresholds) > 1 else ""
            comparison_desc += (
                f"dates within the following threshold{plural} "
                f"{datediff_separated_thresholds_string} vs. "
            )

        comparison_desc += "anything else"
        return comparison_desc

    def create_output_column_name(self) -> str:
        return self.col_expression.output_column_name

_VALID_POSTCODE_REGEX = "^[A-Za-z]{1,2}[0-9][A-Za-z0-9]? [0-9][A-Za-z]{2}$"


class PostcodeComparison(ComparisonCreator):
    """
    A wrapper to generate a comparison for a poscode column 'col_name'
        with preselected defaults.

    The default arguments will give a comparison with levels:\n
    - Exact match on full postcode
    - Exact match on sector
    - Exact match on district
    - Exact match on area
    - All other comparisons
    """

    SECTOR_REGEX = "^[A-Za-z]{1,2}[0-9][A-Za-z0-9]? [0-9]"
    DISTRICT_REGEX = "^[A-Za-z]{1,2}[0-9][A-Za-z0-9]?"
    AREA_REGEX = "^[A-Za-z]{1,2}"

    def __init__(
        self,
        col_name: Union[str, ColumnExpression],
        *,
        invalid_postcodes_as_null=False,
        valid_postcode_regex=_VALID_POSTCODE_REGEX,
        include_full_match_level=True,
        include_sector_match_level=True,
        include_district_match_level=True,
        include_area_match_level=True,
        lat_col: Union[str, ColumnExpression] = None,
        long_col: Union[str, ColumnExpression] = None,
        km_thresholds: Union[float, List[float]] = [],
    ):
        self.valid_postcode_regex = (
            valid_postcode_regex if invalid_postcodes_as_null else None
        )

        self.full_match = include_full_match_level
        self.sector_match = include_sector_match_level
        self.district_match = include_district_match_level
        self.area_match = include_area_match_level

        cols = {"postcode": col_name}
        if km_thresholds:
            km_thresholds_as_iterable = ensure_is_iterable(km_thresholds)
            self.km_thresholds = [*km_thresholds_as_iterable]
            cols["latitude"] = lat_col
            cols["longitude"] = long_col
        super().__init__(cols)

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        full_col_expression = self.col_expressions["postcode"]
        sector_col_expression = full_col_expression.regex_extract(self.SECTOR_REGEX)
        district_col_expression = full_col_expression.regex_extract(self.DISTRICT_REGEX)
        area_col_expression = full_col_expression.regex_extract(self.AREA_REGEX)

        levels = [
            # Null level accept pattern if not None, otherwise will ignore
            cll.NullLevel(
                full_col_expression, valid_string_pattern=self.valid_postcode_regex
            ),
        ]
        if self.full_match:
            levels.append(cll.ExactMatchLevel(full_col_expression))
        if self.sector_match:
            levels.append(cll.ExactMatchLevel(sector_col_expression))
        if self.district_match:
            levels.append(cll.ExactMatchLevel(district_col_expression))
        if self.area_match:
            levels.append(cll.ExactMatchLevel(area_col_expression))
        if self.km_thresholds:
            lat_col_expression = self.col_expressions["latitude"]
            long_col_expression = self.col_expressions["longitude"]
            levels.extend(
                [
                    cll.DistanceInKMLevel(
                        lat_col_expression, long_col_expression, km_threshold
                    )
                    for km_threshold in self.km_thresholds
                ]
            )

        levels.append(cll.ElseLevel())
        return levels

    def create_description(self) -> str:
        comparison_desc = ""
        if self.full_match:
            comparison_desc += "Exact match vs. "

        if self.sector_match:
            comparison_desc += "Exact sector match vs. "
        if self.district_match:
            comparison_desc += "Exact district match vs. "
        if self.area_match:
            comparison_desc += "Exact area match vs. "

        if self.km_thresholds:
            comma_separated_thresholds_string = ", ".join(map(str, self.km_thresholds))
            plural = "s" if len(self.km_thresholds) > 1 else ""
            comparison_desc = (
                f"km distance within threshold{plural} "
                f"{comma_separated_thresholds_string} vs. "
            )

        comparison_desc += "anything else"
        return comparison_desc

    def create_output_column_name(self) -> str:
        return self.col_expressions["postcode"].output_column_name


_DEFAULT_EMAIL_REGEX = "^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+[.][a-zA-Z]{2,}$"


class EmailComparison(ComparisonCreator):

    USERNAME_REGEX = "^[^@]+"
    DOMAIN_REGEX = "@([^@]+)$"

    def __init__(
        self,
        col_name: Union[str, ColumnExpression],
        *,
        invalid_emails_as_null: bool = False,
        valid_email_regex: str = _DEFAULT_EMAIL_REGEX,
        include_exact_match_level: bool = True,
        include_username_match_level: bool = True,
        include_username_fuzzy_level: bool = True,
        include_domain_match_level: bool = False,
        # TODO: typing.Literal? enum?
        fuzzy_metric: str = "jaro_winkler",
        fuzzy_thresholds: Union[float, List[float]] = [0.88],
    ):

        thresholds_as_iterable = ensure_is_iterable(fuzzy_thresholds)
        self.fuzzy_thresholds = [*thresholds_as_iterable]

        self.valid_email_regex = valid_email_regex if invalid_emails_as_null else None

        self.exact_match = include_exact_match_level
        self.username_match = include_username_match_level
        self.username_fuzzy = include_username_fuzzy_level
        self.domain_match = include_domain_match_level

        if self.fuzzy_thresholds:
            try:
                self.fuzzy_level = _fuzzy_levels[fuzzy_metric]
            except KeyError:
                raise ValueError(
                    f"Invalid value for {fuzzy_metric=}.  "
                    f"Must choose one of: {_AVAILABLE_METRICS_STRING}."
                ) from None
            # store metric for description
            self.fuzzy_metric = fuzzy_metric

        super().__init__(col_name)

    def create_comparison_levels(self) -> List[ComparisonLevelCreator]:
        full_col_expression = self.col_expression
        username_col_expression = full_col_expression.regex_extract(self.USERNAME_REGEX)
        domain_col_expression = full_col_expression.regex_extract(self.DOMAIN_REGEX)

        levels = [
            # Null level accept pattern if not None, otherwise will ignore
            cll.NullLevel(
                full_col_expression, valid_string_pattern=self.valid_email_regex
            ),
        ]
        if self.exact_match:
            levels.append(cll.ExactMatchLevel(full_col_expression))
        if self.username_match:
            levels.append(cll.ExactMatchLevel(username_col_expression))
        if self.fuzzy_thresholds:
            levels.extend(
                [
                    self.fuzzy_level(full_col_expression, threshold)
                    for threshold in self.fuzzy_thresholds
                ]
            )
            if self.username_fuzzy:
                levels.extend(
                    [
                        self.fuzzy_level(username_col_expression, threshold)
                        for threshold in self.fuzzy_thresholds
                    ]
                )
        if self.domain_match:
            levels.append(cll.ExactMatchLevel(domain_col_expression))

        levels.append(cll.ElseLevel())
        return levels

    def create_description(self) -> str:
        comparison_desc = ""
        if self.exact_match:
            comparison_desc += "Exact match vs. "

        if self.username_match:
            comparison_desc += "Exact username match different domain vs. "

        if self.fuzzy_thresholds:
            comma_separated_thresholds_string = ", ".join(
                map(str, self.fuzzy_thresholds)
            )
            plural = "s" if len(self.fuzzy_thresholds) > 1 else ""
            comparison_desc = (
                f"{self.fuzzy_metric} at threshold{plural} "
                f"{comma_separated_thresholds_string} vs. "
            )
            if self.username_fuzzy:
                comma_separated_thresholds_string = ", ".join(
                    map(str, self.fuzzy_thresholds)
                )
                plural = "s" if len(self.fuzzy_thresholds) > 1 else ""
                comparison_desc = (
                    f"{self.fuzzy_metric} on username at threshold{plural} "
                    f"{comma_separated_thresholds_string} vs. "
                )

        if self.domain_match:
            comparison_desc += "Domain-only match vs. "

        comparison_desc += "anything else"
        return comparison_desc

    def create_output_column_name(self) -> str:
        return self.col_expression.output_column_name
