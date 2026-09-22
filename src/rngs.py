# -----------------------------------------------------------------------------
# rngs.py  --  Generatore di numeri pseudo-casuali multi-stream (Lehmer)
#
# Porting Python della libreria "rngs" di Steve Park & Dave Geyer
# (Leemis & Park, "Discrete-Event Simulation: A First Course").
#
# Caratteristiche (come da corso PMCSN):
#   - Generatore di Lehmer:  x_{n+1} = (a * x_n) mod m
#         moltiplicatore a = 48271,  modulo m = 2^31 - 1 = 2147483647
#   - 256 stream indipendenti e disgiunti (jump multiplier A256 = 22925)
#   - PlantSeeds(): inizializza TUTTI i 256 stream a partire da un seme.
#     Va chiamata UNA SOLA VOLTA, all'esterno del ciclo delle repliche.
#   - SelectStream(i): seleziona lo stream attivo (0..255) per disaccoppiare
#     i diversi processi stocastici (arrivi cl.1, arrivi cl.2, servizi, ...).
#
# NOTA: questo file NON usa librerie esterne (solo modulo standard `os`/`time`
#       per il seme "casuale"); è conforme al vincolo del progetto.
# -----------------------------------------------------------------------------

from time import time as _time

MODULUS    = 2147483647   # m = 2^31 - 1 (numero primo di Mersenne)
MULTIPLIER = 48271        # a  (moltiplicatore di Lehmer, full-period)
CHECK      = 399268537    # valore di controllo dopo 10.000 chiamate da seme 1
STREAMS    = 256          # numero di stream indipendenti
A256       = 22925        # "jump multiplier" per distanziare gli stream
DEFAULT    = 123456789    # seme iniziale di default

# stato interno: un seme corrente per ciascuno dei 256 stream
_seed   = [DEFAULT] * STREAMS
_stream = 0              # indice dello stream attualmente selezionato
_initialized = False     # True dopo la prima PlantSeeds()


def Random():
    """Restituisce un numero pseudo-casuale reale in (0, 1) sullo stream corrente.

    Implementa x = (a*x) mod m con la fattorizzazione di Schrage per evitare
    overflow (tecnica del libro di Leemis & Park)."""
    global _seed
    Q = MODULUS // MULTIPLIER      # 44488
    R = MODULUS % MULTIPLIER       # 3399
    x = _seed[_stream]
    t = MULTIPLIER * (x % Q) - R * (x // Q)
    if t > 0:
        _seed[_stream] = t
    else:
        _seed[_stream] = t + MODULUS
    return _seed[_stream] / MODULUS


def PutSeed(x):
    """Imposta il seme dello stream corrente.
       x > 0  -> usa x;  x < 0 -> seme da orologio;  x == 0 -> seme da tastiera."""
    global _seed
    if x > 0:
        x = x % MODULUS
    elif x < 0:
        x = int(_time()) % MODULUS
    else:  # x == 0
        try:
            x = int(input("Enter a positive integer seed (9 digits or less) >> "))
        except (ValueError, EOFError):
            x = DEFAULT
        x = x % MODULUS
    _seed[_stream] = x


def GetSeed():
    """Restituisce il seme corrente dello stream attivo (utile per il logging/riproducibilita')."""
    return _seed[_stream]


def SelectStream(index):
    """Seleziona lo stream attivo (0..255). Tutte le successive chiamate a
       Random() useranno questo stream finche' non se ne seleziona un altro."""
    global _stream
    _stream = index % STREAMS
    # Se il generatore non e' ancora stato inizializzato e si usa uno stream
    # diverso dallo 0, si pianta il seme di default (comportamento del libro).
    if (not _initialized) and _stream != 0:
        PlantSeeds(DEFAULT)


def PlantSeeds(x):
    """Inizializza i semi di TUTTI i 256 stream a partire dal seme dello stream 0.

    Da chiamare UNA SOLA VOLTA all'inizio del programma (fuori dal ciclo delle
    repliche): distanzia ogni stream dal precedente di 2^23 estrazioni circa,
    cosi' i flussi non si sovrappongono. E' la regola anti-correlazione del corso
    (Kurkowski et al.)."""
    global _seed, _stream, _initialized
    Q = MODULUS // A256
    R = MODULUS % A256
    _initialized = True
    s = _stream
    SelectStream(0)
    PutSeed(x)
    _stream = s
    j = 1
    while j < STREAMS:
        t = A256 * (_seed[j - 1] % Q) - R * (_seed[j - 1] // Q)
        if t > 0:
            _seed[j] = t
        else:
            _seed[j] = t + MODULUS
        j += 1


def TestRandom():
    """Test di correttezza del generatore (come nel libro): dopo 10.000 chiamate
       con seme iniziale 1 sullo stream 0, il seme deve valere CHECK=399268537."""
    global _seed
    SelectStream(0)
    PutSeed(1)
    for _ in range(10000):
        Random()
    ok = (GetSeed() == CHECK)
    print("Test rngs: seme atteso =", CHECK, " ottenuto =", GetSeed(),
          " ->", "OK" if ok else "ERRORE")
    return ok


if __name__ == "__main__":
    # Esegui:  python rngs.py   per verificare il generatore
    TestRandom()
