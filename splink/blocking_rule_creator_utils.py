from __future__ import annotations

from typing import Any, List, Union

from .blocking_rule_creator import BlockingRuleCreator
from .blocking_rule_library import CustomRule
from .misc import ensure_is_iterable


def to_blocking_rule_creator(
    blocking_rule_creator: Union[dict[str, Any], str, BlockingRuleCreator],
):
    if isinstance(blocking_rule_creator, dict):
        return CustomRule(**blocking_rule_creator)
    if isinstance(blocking_rule_creator, str):
        return CustomRule(blocking_rule_creator)
    return blocking_rule_creator


def blocking_rule_args_to_list_of_blocking_rules(
    blocking_rule_args: Union[
        str, BlockingRuleCreator, List[Union[str, BlockingRuleCreator]]
    ],
    sql_dialect: str,
):
    """In functions such as `linker.estimate_probability_two_random_records_match`
    the user may have passed in strings or BlockingRuleCreator objects.

    Additionally, they may have passed in a single string or a single
    BlockingRuleCreator object instead of a list.

    This function converts the input to a list of BlockingRule objects
    """
    rules_as_creators = [
        to_blocking_rule_creator(br) for br in ensure_is_iterable(blocking_rule_args)
    ]
    rules_as_brs = [br.get_blocking_rule(sql_dialect) for br in rules_as_creators]
    return rules_as_brs
