"""The five canonical ciphers: English Ordinal, Full Reduction, Reverse Ordinal,
Reverse Reduction and Chaldean.

Phrases are normalized to letters only (case-insensitive); digits, spaces and
punctuation contribute nothing.
"""

import string

LETTERS = string.ascii_lowercase


def _reduce(n: int) -> int:
    """Digit-sum reduction to a single digit (1-9)."""
    return (n - 1) % 9 + 1


ENGLISH_ORDINAL = {c: i + 1 for i, c in enumerate(LETTERS)}
FULL_REDUCTION = {c: _reduce(v) for c, v in ENGLISH_ORDINAL.items()}
REVERSE_ORDINAL = {c: 26 - i for i, c in enumerate(LETTERS)}
REVERSE_REDUCTION = {c: _reduce(v) for c, v in REVERSE_ORDINAL.items()}
CHALDEAN = dict(zip(LETTERS, [1, 2, 3, 4, 5, 8, 3, 5, 1, 1, 2, 3, 4,
                              5, 7, 8, 1, 2, 3, 4, 6, 6, 6, 5, 1, 7]))

# Order is fixed so every decode lists ciphers identically.
CIPHERS = {
    "EO": ("English Ordinal", ENGLISH_ORDINAL),
    "FR": ("Full Reduction", FULL_REDUCTION),
    "RO": ("Reverse Ordinal", REVERSE_ORDINAL),
    "RR": ("Reverse Reduction", REVERSE_REDUCTION),
    "CH": ("Chaldean", CHALDEAN),
}


def normalize(phrase: str) -> str:
    return "".join(c for c in phrase.lower() if c in LETTERS)


def value(phrase: str, cipher: str) -> int:
    table = CIPHERS[cipher][1]
    return sum(table[c] for c in normalize(phrase))


def all_values(phrase: str) -> dict[str, int]:
    return {code: value(phrase, code) for code in CIPHERS}
