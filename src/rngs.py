# 256 stream indipendenti; PlantSeeds() una volta all'avvio, SelectStream(i)
from time import time as _time

MODULUS    = 2147483647   # 2^31 - 1
MULTIPLIER = 48271
CHECK      = 399268537    # seme atteso dopo 10000 estrazioni da seme 1
STREAMS    = 256
A256       = 22925        # jump multiplier tra stream
DEFAULT    = 123456789

_seed = [DEFAULT] * STREAMS
_stream = 0
_initialized = False


def Random():
    """Numero pseudo-casuale in (0,1) sullo stream corrente (Schrage, no overflow)."""
    Q = MODULUS // MULTIPLIER
    R = MODULUS % MULTIPLIER
    x = _seed[_stream]
    t = MULTIPLIER * (x % Q) - R * (x // Q)
    _seed[_stream] = t if t > 0 else t + MODULUS
    return _seed[_stream] / MODULUS


def PutSeed(x):
    """Imposta il seme dello stream corrente (x<0: da orologio; x==0: da input)."""
    if x > 0:
        x = x % MODULUS
    elif x < 0:
        x = int(_time()) % MODULUS
    else:
        try:
            x = int(input("seme (intero positivo) >> ")) % MODULUS
        except (ValueError, EOFError):
            x = DEFAULT
    _seed[_stream] = x


def GetSeed():
    """Seme corrente dello stream attivo (per logging/riproducibilita')."""
    return _seed[_stream]


def SelectStream(index):
    """Seleziona lo stream attivo (0..255)."""
    global _stream
    _stream = index % STREAMS
    if (not _initialized) and _stream != 0:
        PlantSeeds(DEFAULT)


def PlantSeeds(x):
    """Inizializza tutti i 256 stream a partire dal seme x. Chiamare UNA volta,
    fuori dal ciclo delle repliche (stream disgiunti -> run indipendenti)."""
    global _stream, _initialized
    Q = MODULUS // A256
    R = MODULUS % A256
    _initialized = True
    s = _stream
    SelectStream(0)
    PutSeed(x)
    _stream = s
    for j in range(1, STREAMS):
        t = A256 * (_seed[j-1] % Q) - R * (_seed[j-1] // Q)
        _seed[j] = t if t > 0 else t + MODULUS


def TestRandom():
    """Verifica del generatore: 10000 estrazioni da seme 1 -> GetSeed()==CHECK."""
    SelectStream(0)
    PutSeed(1)
    for _ in range(10000):
        Random()
    ok = GetSeed() == CHECK
    print("rngs:", "OK" if ok else "ERRORE", "(atteso", CHECK, "ottenuto", GetSeed(), ")")
    return ok


if __name__ == "__main__":
    TestRandom()
