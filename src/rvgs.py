from math import log, sqrt, cos, pi
from rngs import Random


def Exponential(m):
    """Esponenziale di media m (interarrivi 1/lambda, servizi 1/mu)."""
    return -m * log(1.0 - Random())


def Normal(m, s):
    """Normale di media m e deviazione s (Box-Muller, 2 uniformi)."""
    return m + s * sqrt(-2.0 * log(1.0 - Random())) * cos(2.0 * pi * Random())
