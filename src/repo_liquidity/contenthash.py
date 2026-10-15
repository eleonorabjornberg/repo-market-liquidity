"""The content hash of a release's extracted values (#89; finding #40).

A saved page's SHA-256 identifies a fetch: the archive injects per-request tokens, so two fetches of one release
differ. The content hash identifies the values read from the release, and can be recomputed from the tracked extract
alone, with no page.

The canonical form, fixed here and nowhere else:
- a header line of the column names, then one line per row, the rows **sorted** by their text;
- fields joined by `,`, lines ended by `\\n`, the whole encoded as UTF-8;
- a numeric column (named in `places`) is written with a **fixed number of decimal places**, so `2`, `2.0` and
  `2.00` are one value; a value with more places than the column fixes is refused, never rounded;
- any other column is written as given, and may not contain `,`, `\\n` or `\\r`.

Standard library only.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from typing import Iterable, Mapping, Sequence


def _field(column: str, value, places: Mapping[str, int]) -> str:
    if column in places:
        try:
            number = Decimal(str(value))
        except InvalidOperation:
            raise ValueError(f"{column}: {value!r} is not a number") from None
        if not number.is_finite():
            raise ValueError(f"{column}: {value!r} is not finite")
        fixed = number.quantize(Decimal(1).scaleb(-places[column]))
        if fixed != number:
            raise ValueError(f"{column}: {value!r} has more than {places[column]} decimal place(s)")
        return format(fixed, "f")
    text = str(value)
    if any(mark in text for mark in (",", "\n", "\r")):
        raise ValueError(f"{column}: {text!r} holds a separator or a line break")
    return text


def canonical(columns: Sequence[str], rows: Iterable[Sequence], places: Mapping[str, int]) -> bytes:
    """The canonical bytes of `rows` under `columns`.

    Raises:
        ValueError: if a row is not as wide as `columns`, a numeric value is not a number or would need rounding, or
            a text value holds a separator or a line break.
    """
    lines = []
    for row in rows:
        if len(row) != len(columns):
            raise ValueError(f"a row of {len(row)} fields under {len(columns)} columns: {tuple(row)!r}")
        lines.append(",".join(_field(column, value, places) for column, value in zip(columns, row)))
    return ("\n".join([",".join(columns)] + sorted(lines)) + "\n").encode("utf-8")


def content_sha256(columns: Sequence[str], rows: Iterable[Sequence], places: Mapping[str, int]) -> str:
    """The SHA-256 of `canonical(columns, rows, places)`."""
    return hashlib.sha256(canonical(columns, rows, places)).hexdigest()
