"""Comparison operators available to the field condition presets.

A preset's Jinja2 expression is a fixed string, and Jinja has no way to dispatch on an operator chosen at
runtime. Rather than build one expression out of nested inline conditionals, the comparison is done here
and exposed to expressions as `field_matches`, which keeps the operator semantics in Python where they can
be read and tested directly.
"""

from decimal import Decimal, InvalidOperation

OPERATOR_EQUALS = "="
OPERATOR_GT = "gt"
OPERATOR_GTE = "gte"
OPERATOR_LT = "lt"
OPERATOR_LTE = "lte"
OPERATOR_IN = "in"
OPERATOR_CONTAINS = "contains"
OPERATOR_STARTSWITH = "startswith"
OPERATOR_ENDSWITH = "endswith"

#: Operator key to the label shown in the form, in the order they are offered.
FIELD_OPERATORS = (
    (OPERATOR_EQUALS, "= (equals)"),
    (OPERATOR_GT, "> (greater than)"),
    (OPERATOR_GTE, ">= (greater than or equal)"),
    (OPERATOR_LT, "< (less than)"),
    (OPERATOR_LTE, "<= (less than or equal)"),
    (OPERATOR_IN, "in (one of a comma-separated list)"),
    (OPERATOR_CONTAINS, "contains"),
    (OPERATOR_STARTSWITH, "starts with"),
    (OPERATOR_ENDSWITH, "ends with"),
)

FIELD_OPERATOR_KEYS = tuple(key for key, _ in FIELD_OPERATORS)

#: Operators that order two values, and so compare numerically when both sides look like numbers.
_ORDERING_OPERATORS = {OPERATOR_GT, OPERATOR_GTE, OPERATOR_LT, OPERATOR_LTE}


def _as_number(value):
    """Return `value` as a Decimal, or None if it is not a number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return Decimal(str(value))
    if isinstance(value, str):
        try:
            return Decimal(value.strip())
        except (InvalidOperation, ArithmeticError):
            return None
    return None


def _as_text(value):
    """Return `value` as a string for text comparison, with None becoming the empty string."""
    if value is None:
        return ""
    return str(value)


def field_matches(value, operator, target):
    """
    Compare a field's value against a target using the named operator.

    A field's value arrives from the captured change, so it can be a string, a number, or a list; the
    target arrives from a form and is always a string. That asymmetry is handled here rather than being
    pushed onto whoever writes the condition.

    Ordering operators compare numerically when both sides look like numbers, and lexicographically
    otherwise, so `mtu > 1500` behaves arithmetically while `name > 'm'` still means something.

    Args:
        value: The field's value from the captured change.
        operator (str): One of `FIELD_OPERATOR_KEYS`.
        target (str): The value to compare against.

    Returns:
        (bool): Whether the comparison holds. An unknown operator is False rather than an error, so a
            malformed condition fails its row like any other rather than breaking the rule.
    """
    if operator not in FIELD_OPERATOR_KEYS:
        return False

    if operator == OPERATOR_IN:
        wanted = [item.strip() for item in _as_text(target).split(",") if item.strip()]
        if isinstance(value, (list, tuple, set)):
            # A list field is in the wanted set if any of its entries is. `tags in critical,urgent` reads
            # as "tagged with either", which is the only useful reading. Comparing the whole list against
            # each name can never match.
            return any(_as_text(item) in wanted for item in value)
        return _as_text(value) in wanted

    if operator == OPERATOR_CONTAINS:
        # A list field contains an element; a text field contains a substring.
        if isinstance(value, (list, tuple, set)):
            return _as_text(target) in [_as_text(item) for item in value]
        return _as_text(target) in _as_text(value)

    if operator == OPERATOR_STARTSWITH:
        return _as_text(value).startswith(_as_text(target))

    if operator == OPERATOR_ENDSWITH:
        return _as_text(value).endswith(_as_text(target))

    if operator == OPERATOR_EQUALS:
        left, right = _as_number(value), _as_number(target)
        if left is not None and right is not None:
            return left == right
        return _as_text(value) == _as_text(target)

    if operator in _ORDERING_OPERATORS:
        left, right = _as_number(value), _as_number(target)
        if left is None or right is None:
            left, right = _as_text(value), _as_text(target)
        if operator == OPERATOR_GT:
            return left > right
        if operator == OPERATOR_GTE:
            return left >= right
        if operator == OPERATOR_LT:
            return left < right
        return left <= right

    return False
