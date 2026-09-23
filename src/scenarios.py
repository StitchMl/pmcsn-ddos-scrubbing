# Reale: picco HTTP ~205 Mrps globali; attacchi 35-69 s.
# Modello: un nodo rappresentativo a scala ridotta.
# Unita': tempi in s, frequenze in richieste/s (rps).

M_NOMINAL  = 4          # serventi (moduli di ispezione)
K_BUFFER   = 2000       # capacita' del nodo (in servizio + in coda)
ES_INSPECT = 0.5e-3     # tempo medio ispezione L7 = 1/mu -> mu_core = 2000 rps

LAMBDA_LEGIT = 4000.0   # legittimo (classe vera 1) -> rho_nominale = 0,5
LAMBDA_BG    = 1000.0   # attacco di fondo (classe vera 2)
LAMBDA_PEAK  = 60000.0  # attacco al picco (~7,5x la capacita')
LAMBDA_MITIG = 12000.0  # attacco in mitigazione

DUR_NORMAL, DUR_PEAK, DUR_MITIG = 30.0, 60.0, 30.0   # durate delle fasce [s]

# detector: il sistema vede solo uno SCORE osservabile per job (non la classe).
# legittimo ~ N(0,1), attacco ~ N(SEP,1); flag se score > THETA.
# rilevamento d e falsi positivi f EMERGONO dalla sovrapposizione (curva ROC):
# con SEP=3, THETA=1.645  ->  f~=0.05, d~=0.91.
CLF_SEP   = 3.0         # separazione lecito/attacco nello spazio delle feature (qualita')
CLF_THETA = 1.645       # soglia di decisione (punto di lavoro / operating point)


def scenario_nominal(m=M_NOMINAL, K=K_BUFFER, duration=200.0, lambda2=LAMBDA_BG):
    from simulator import single_phase
    return {"m": m, "K": K, "Es1": ES_INSPECT, "Es2": ES_INSPECT,
            "clf": {"sep": CLF_SEP, "theta": CLF_THETA}, "policy": {"name": "base"},
            "phases": single_phase(LAMBDA_LEGIT, lambda2, duration)}


def scenario_attack(m=M_NOMINAL, K=K_BUFFER, dur_scale=1.0):
    """Attacco a 3 fasce, policy BASE (class-blind). dur_scale accorcia le fasce
    per esperimenti piu' rapidi."""
    phases = [
        {"dur": DUR_NORMAL * dur_scale, "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_BG},
        {"dur": DUR_PEAK * dur_scale,   "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_PEAK},
        {"dur": DUR_MITIG * dur_scale,  "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_MITIG},
    ]
    return {"m": m, "K": K, "Es1": ES_INSPECT, "Es2": ES_INSPECT,
            "clf": {"sep": CLF_SEP, "theta": CLF_THETA}, "policy": {"name": "base"},
            "phases": phases}


def with_policy(cfg, policy):
    """Copia lo scenario cambiando solo la policy di mitigazione."""
    c = dict(cfg)
    c["policy"] = policy
    return c


# costruttori di policy (agiscono sull'ETICHETTA del classificatore)
def pol_base():
    return {"name": "base"}


def pol_fasttrack(reserve=300):
    return {"name": "fasttrack", "K_susp": K_BUFFER - reserve}


def pol_ratelimit(rate=6000.0, burst=200.0):
    return {"name": "ratelimit", "rate": rate, "burst": burst}


def pol_autoscale(m_max=16, up=200, down=20, setup=0.5):
    return {"name": "autoscale", "m_min": M_NOMINAL, "m_max": m_max,
            "up": up, "down": down, "setup": setup}
