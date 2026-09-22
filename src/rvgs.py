# -----------------------------------------------------------------------------
# rvgs.py  --  Random Variate GeneratorS
#
# Porting Python della libreria "rvgs" di Steve Park & Dave Geyer
# (Leemis & Park, "Discrete-Event Simulation: A First Course").
#
# Genera campioni da distribuzioni di probabilita' a partire da Random() di rngs.
# Usiamo SOLO le distribuzioni viste a lezione (vincolo di progetto):
#   - Exponential  -> interarrivi e tempi di servizio (memoryless)
#   - Uniform      -> selezione dei rami / usi generici
#   - Equilikely   -> variabile discreta equiprobabile
#   - Erlang       -> alternativa a bassa/variabilita' controllata (C^2 = 1/n)
#   - (Hyperexponential H2 la costruiamo nel simulatore combinando Uniform+Exponential)
#
# NOTA: tutte le funzioni consumano numeri casuali dallo STREAM attualmente
# selezionato in rngs (usare SelectStream() prima di chiamarle).
# -----------------------------------------------------------------------------

from math import log
from rngs import Random


def Exponential(m):
    """Campione da una Esponenziale di media m (m > 0).
       Metodo dell'inversa:  x = -m * ln(1 - u).
       Usata per interarrivi (m = 1/lambda) e tempi di servizio (m = 1/mu)."""
    return -m * log(1.0 - Random())


def Uniform(a, b):
    """Campione da una Uniforme continua su (a, b), con a < b."""
    return a + (b - a) * Random()


def Equilikely(a, b):
    """Campione intero equiprobabile in {a, a+1, ..., b}, con a <= b."""
    return a + int((b - a + 1) * Random())


def Geometric(p):
    """Campione da una Geometrica su {0, 1, 2, ...} con parametro p (0 < p < 1)."""
    return int(log(1.0 - Random()) / log(p))


def Erlang(n, b):
    """Campione da una Erlang-n: somma di n Esponenziali i.i.d. di media b.
       Media = n*b, coefficiente di variazione al quadrato C^2 = 1/n."""
    x = 0.0
    for _ in range(n):
        x += Exponential(b)
    return x


# --- Extra utili per verifiche/estensioni (tutti standard di Leemis & Park) ---

def Bernoulli(p):
    """1 con probabilita' p, 0 con probabilita' 1-p."""
    return 1 if Random() < p else 0


def Binomial(n, p):
    """Numero di successi su n prove indipendenti di probabilita' p."""
    x = 0
    for _ in range(n):
        if Random() < p:
            x += 1
    return x
