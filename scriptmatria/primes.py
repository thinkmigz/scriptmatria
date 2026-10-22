"""Prime utilities. Prime indexes are 1-based: 2 is the 1st prime, 23 the 9th."""


def is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    f = 3
    while f * f <= n:
        if n % f == 0:
            return False
        f += 2
    return True


def prime_index(n: int) -> int | None:
    """Ordinal position of n among the primes, or None if n is not prime."""
    if not is_prime(n):
        return None
    return sum(1 for k in range(2, n + 1) if is_prime(k))


def nth_prime(i: int) -> int:
    if i < 1:
        raise ValueError("prime index starts at 1")
    count, n = 0, 1
    while count < i:
        n += 1
        if is_prime(n):
            count += 1
    return n


def reverse_digits(n: int) -> int:
    return int(str(abs(n))[::-1])


def is_reverse_prime(n: int) -> bool:
    """True when the digit-reversal of n is prime (n itself need not be)."""
    return is_prime(reverse_digits(n))
