# Reale: picco HTTP ~205 Mrps globali; attacchi 35-69 s.
# Modello: un nodo rappresentativo a scala ridotta.
# Unita': tempi in s, frequenze in richieste/s (rps).

M_NOMINAL  = 4          # serventi (moduli di ispezione)
K_BUFFER   = 2000       # capacita' del nodo (in servizio + in coda)
ES_INSPECT = 0.5e-3     # tempo medio ispezione L7 = 1/mu -> mu_core = 2000 rps

LAMBDA_LEGIT = 4000.0   # Classe 1 (legittimo) -> rho_nominale = 0,5
LAMBDA_BG    = 1000.0   # Classe 2 fuori dal picco (fondo)
LAMBDA_PEAK  = 60000.0  # Classe 2 al picco (~7,5x la capacita' -> saturazione)
LAMBDA_MITIG = 12000.0  # Classe 2 in mitigazione

DUR_NORMAL, DUR_PEAK, DUR_MITIG = 30.0, 60.0, 30.0   # durate delle fasce [s]


def scenario_nominal(m=M_NOMINAL, K=K_BUFFER, duration=200.0, lambda2=LAMBDA_BG):
    """Regime costante (nessun picco). Con lambda2=0 diventa un M/M/m/K mono-classe."""
    from simulator import single_phase
    return {"m": m, "K": K, "Es1": ES_INSPECT, "Es2": ES_INSPECT,
            "phases": single_phase(LAMBDA_LEGIT, lambda2, duration)}


def scenario_attack(m=M_NOMINAL, K=K_BUFFER, K2=None):
    """Attacco a 3 fasce (orizzonte finito): Normale -> Picco -> Mitigazione.
    K2 < K attiva il Fast-Track: l'attacco (Classe 2) e' ammesso solo fino a K2,
    riservando (K-K2) slot alla Classe 1 (ammissione priority-aware)."""
    return {
        "m": m, "K": K, "K2": K if K2 is None else K2,
        "Es1": ES_INSPECT, "Es2": ES_INSPECT,
        "phases": [
            {"dur": DUR_NORMAL, "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_BG},
            {"dur": DUR_PEAK,   "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_PEAK},
            {"dur": DUR_MITIG,  "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_MITIG},
        ],
    }
