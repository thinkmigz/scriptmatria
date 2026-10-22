"""Prime utilities. Prime indexes are 1-based: 2 is the 1st prime, 23 the 9th.

Backed by a cached, growable sieve so index lookups are fast and exact."""

from bisect import bisect_left

_limit = 1
_primes: list[int] = []


def _ensure(limit: int) -> None:
    """Sieve all primes up to at least `limit`."""
    global _limit, _primes
    if limit <= _limit:
        return
    limit = max(limit, _limit * 2, 1024)
    sieve = bytearray([1]) * (limit + 1)
    sieve[0:2] = b"\x00\x00"
    for i in range(2, int(limit ** 0.5) + 1):
        if sieve[i]:
            sieve[i * i::i] = bytearray(len(range(i * i, limit + 1, i)))
    _primes = [i for i in range(limit + 1) if sieve[i]]
    _limit = limit


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    _ensure(n)
    i = bisect_left(_primes, n)
    return i < len(_primes) and _primes[i] == n


def prime_index(n: int) -> int | None:
    """Ordinal position of n among the primes, or None if n is not prime."""
    if not is_prime(n):
        return None
    return bisect_left(_primes, n) + 1


def nth_prime(i: int) -> int:
    if i < 1:
        raise ValueError("prime index starts at 1")
    while len(_primes) < i:
        _ensure(_limit * 2)
    return _primes[i - 1]


def reverse_digits(n: int) -> int:
    """Base-10 digit reversal; leading zeros drop (100 -> 1). Not the Reverse Ordinal cipher."""
    return int(str(abs(n))[::-1])


def is_reverse_prime(n: int) -> bool:
    """True when the digit-reversal of n is prime (n itself need not be)."""
    return is_prime(reverse_digits(n))
