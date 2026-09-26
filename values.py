"""Validate the demo's bounded decimal input contract."""

from decimal import Decimal, InvalidOperation


def number(value, field):
    """Preserve missing values; accept non-negative numbers with six decimal places."""
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a number, not a Boolean")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{field} must be a decimal number") from error
    if not result.is_finite() or result < 0 or result > Decimal("1e12"):
        raise ValueError(f"{field} must be finite and between 0 and 1e12")
    if result.as_tuple().exponent < -6:
        raise ValueError(f"{field} supports at most six decimal places")
    return result


def rate(value, field):
    result = number(value, field)
    if result is not None and result > 1:
        raise ValueError(f"{field} must be a fraction between 0 and 1")
    return result