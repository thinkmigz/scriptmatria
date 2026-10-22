from scriptmatria import primes


def test_audit_reference_values():
    assert primes.prime_index(23) == 9
    assert primes.prime_index(83) == 23
    assert primes.nth_prime(23) == 83
    assert primes.nth_prime(9) == 23


def test_non_primes_have_no_index():
    for n in (0, 1, 4, 9, 32, 91):
        assert primes.prime_index(n) is None


def test_reverse_prime():
    assert primes.reverse_digits(23) == 32
    assert not primes.is_reverse_prime(23)
    assert primes.is_reverse_prime(13)  # 31
    assert primes.reverse_digits(120) == 21


def test_index_and_nth_are_inverse():
    for i in range(1, 200):
        assert primes.prime_index(primes.nth_prime(i)) == i
