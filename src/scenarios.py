# -----------------------------------------------------------------------------
# scenarios.py  --  Parametri del modello DERIVATI dal caso reale AISURU 2025
# =============================================================================
# Qui si "aggancia" il modello al caso reale e si documenta la derivazione dei
# parametri, con le fonti. Serve a rendere la simulazione ADERENTE alla realta'
# (attacco impulsivo a fasce, attacco che travolge la capacita', perdita del
# legittimo) e quindi utile a IPOTIZZARE CONTROMISURE (Step 8).
#
# -------------------------- NUMERI REALI (fonti) ------------------------------
#   - Picco HTTP/L7 della botnet AISURU nel 2025: ~205 milioni di richieste/s
#     (Cloudflare, 2025 Q4 DDoS threat report).
#   - Durata degli attacchi "iper-volumetrici": 35-69 secondi (impulsivi).
#   - Rete anycast del difensore: ~330 citta'/PoP (Cloudflare) => il singolo PoP
#     vede ~ 205e6 / 330 ~= 0.62 milioni di richieste/s al picco.
#   Fonti (vedi README, sez. 4):
#     Cloudflare Q4-2025 report; SecurityAffairs; The Hacker News; GBHackers; Krebs.
#
# ------------------- DAL REALE AL MODELLO (nodo rappresentativo) --------------
#   Simuliamo UN nodo di scrubbing a scala ASSOLUTA RIDOTTA ma TRATTABILE,
#   conservando cio' che conta e che "trasferisce" alla scala reale:
#     * la DINAMICA: attacco impulsivo a fasce, attacco >> capacita', buffer finito;
#     * le grandezze ADIMENSIONALI: utilizzazione rho, probabilita' di perdita
#       P_loss, rapporti tra le classi, e la variazione percentuale delle metriche
#       introdotta dalle contromisure.
#   Giustificazione metodologica: la proprieta' del FATTORE DI SCALA vista a
#   lezione dice che riscalando (lambda, mu) -> (a*lambda, a*mu) l'utilizzazione,
#   le probabilita' e le popolazioni restano INVARIATE (cambiano solo i tempi
#   assoluti). Quindi i risultati adimensionali del nodo ridotto valgono anche a
#   scala reale; i valori assoluti vanno letti "per nodo rappresentativo".
#
# Unita': tempi in SECONDI, frequenze in richieste/secondo (rps).
# -----------------------------------------------------------------------------

# --------- Parametri strutturali del nodo (baseline, tarabili) ---------------
M_NOMINAL   = 4          # serventi (moduli di ispezione) in condizioni nominali
K_BUFFER    = 2000       # capacita' del nodo (richieste in servizio + in coda)
ES_INSPECT  = 0.5e-3     # tempo medio d'ispezione L7 per richiesta = 1/mu [s]
                         #   0.5 ms/richiesta -> mu_core = 2000 rps per servente
                         #   (parse HTTP + eventuale handshake/decifratura TLS + match regole)

# --------- Carico di traffico (rps) ------------------------------------------
LAMBDA_LEGIT   = 4000.0     # traffico legittimo (Classe 1) a regime
                            #   con m=4 e mu_core=2000 -> rho_nominale = 4000/8000 = 0.5
LAMBDA_BG      = 1000.0     # "fondo" d'attacco/scanning (Classe 2) fuori dal picco
LAMBDA_PEAK    = 60000.0    # PICCO d'attacco (Classe 2): ~15x il legittimo e ~7.5x la
                            #   capacita' totale (8000 rps) -> il nodo va in saturazione
                            #   (riproduce l'effetto DDoS: la difesa cede).
LAMBDA_MITIG   = 12000.0    # fase di mitigazione: l'attacco rientra parzialmente

# --------- Durate delle fasce (s) --------------------------------------------
DUR_NORMAL = 30.0           # regime normale prima dell'attacco
DUR_PEAK   = 60.0           # picco (coerente coi 35-69 s reali degli attacchi AISURU)
DUR_MITIG  = 30.0           # coda di mitigazione/rientro


def scenario_nominal(m=M_NOMINAL, K=K_BUFFER, duration=200.0,
                     lambda2_bg=LAMBDA_BG):
    """Regime NOMINALE stazionario (nessun picco): un solo regime costante.
       Usato per il dimensionamento a orizzonte infinito e come base per la
       verifica (mettendo lambda2=0 si ottiene un M/M/m/K mono-classe)."""
    from simulator import single_phase
    return {
        "m": m, "K": K, "Es1": ES_INSPECT, "Es2": ES_INSPECT,
        "phases": single_phase(LAMBDA_LEGIT, lambda2_bg, duration),
    }


def scenario_attack(m=M_NOMINAL, K=K_BUFFER):
    """ATTACCO AISURU a 3 FASCE (orizzonte finito): Normale -> Picco -> Mitigazione.
       E' lo scenario 'reale': serve a osservare l'impatto dinamico dell'attacco
       e a valutare le contromisure."""
    return {
        "m": m, "K": K, "Es1": ES_INSPECT, "Es2": ES_INSPECT,
        "phases": [
            {"dur": DUR_NORMAL, "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_BG},
            {"dur": DUR_PEAK,   "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_PEAK},
            {"dur": DUR_MITIG,  "lambda1": LAMBDA_LEGIT, "lambda2": LAMBDA_MITIG},
        ],
    }


def print_real_mapping():
    """Stampa la mappatura reale -> modello (da citare nella relazione)."""
    mu_core = 1.0 / ES_INSPECT
    cap = M_NOMINAL * mu_core
    print("=== CASO REALE AISURU 2025 -> MODELLO (nodo rappresentativo) ===")
    print(f"  Reale: picco HTTP ~205 Mrps globali; attacchi 35-69 s; ~330 PoP")
    print(f"         => per-PoP al picco ~ 205e6/330 ~= 0.62 Mrps  (Cloudflare Q4-2025)")
    print(f"  Modello (nodo ridotto, dinamica e grandezze adimensionali preservate):")
    print(f"    servente: Es={ES_INSPECT*1e3:.2f} ms -> mu_core={mu_core:.0f} rps; "
          f"m={M_NOMINAL} -> capacita'={cap:.0f} rps; buffer K={K_BUFFER}")
    print(f"    legittimo lambda1={LAMBDA_LEGIT:.0f} rps (rho_nominale={LAMBDA_LEGIT/cap:.2f})")
    print(f"    attacco: fondo={LAMBDA_BG:.0f}, PICCO={LAMBDA_PEAK:.0f} "
          f"(~{LAMBDA_PEAK/cap:.1f}x la capacita'), mitig={LAMBDA_MITIG:.0f} rps")
    print(f"    fasce: Normale {DUR_NORMAL:.0f}s -> Picco {DUR_PEAK:.0f}s -> Mitig {DUR_MITIG:.0f}s")
