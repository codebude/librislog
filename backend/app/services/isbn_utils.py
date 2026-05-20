import re

_ISBN10_RE = re.compile(r"^\d{9}[\dX]$")
_ISBN13_RE = re.compile(r"^\d{13}$")


def normalize_isbn(isbn: str) -> str:
    compact = re.sub(r"[^0-9Xx]", "", isbn).upper()
    if _ISBN13_RE.fullmatch(compact):
        return compact
    if not _ISBN10_RE.fullmatch(compact):
        raise ValueError("Invalid ISBN format")
    core = compact[:-1]
    isbn13_core = f"978{core}"
    checksum_sum = sum(int(digit) * (1 if idx % 2 == 0 else 3) for idx, digit in enumerate(isbn13_core))
    checksum_digit = (10 - (checksum_sum % 10)) % 10
    return f"{isbn13_core}{checksum_digit}"


def isbn13_to_isbn10(isbn13: str) -> str | None:
    if not _ISBN13_RE.fullmatch(isbn13):
        return None
    if not isbn13.startswith("978"):
        return None
    core9 = isbn13[3:-1]
    weighted_sum = sum(int(digit) * (10 - idx) for idx, digit in enumerate(core9))
    remainder = weighted_sum % 11
    check_value = 11 - remainder
    if check_value == 10:
        check_digit = "X"
    elif check_value == 11:
        check_digit = "0"
    else:
        check_digit = str(check_value)
    return f"{core9}{check_digit}"
