from math import log
from rngs import Random


def Exponential(m):
    """Esponenziale di media m (interarrivi 1/lambda, servizi 1/mu)."""
    return -m * log(1.0 - Random())


def Uniform(a, b):
    """Uniforme continua su (a, b)."""
    return a + (b - a) * Random()


def Equilikely(a, b):
    """Intero equiprobabile in {a, ..., b}."""
    return a + int((b - a + 1) * Random())


def Erlang(n, b):
    """Erlang-n: somma di n esponenziali di media b (C^2 = 1/n)."""
    return sum(Exponential(b) for _ in range(n))


def Bernoulli(p):
    """1 con probabilita' p, altrimenti 0."""
    return 1 if Random() < p else 0
