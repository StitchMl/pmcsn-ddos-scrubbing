# -----------------------------------------------------------------------------
# simulator.py  --  Simulatore Next-Event del nodo di scrubbing DDoS
# =============================================================================
# Progetto PMCSN - caso reale AISURU 2025.
#
# COSA MODELLA
#   Un nodo di "scrubbing" (mitigazione DDoS) di un PoP CDN, astratto come una
#   STAZIONE MULTI-SERVER con BUFFER FINITO, alimentata da due classi di traffico:
#       - Classe 1 = traffico legittimo  (priorita' ALTA, ha una SLA)
#       - Classe 2 = traffico d'attacco  (priorita' BASSA)
#   I "job" sono le richieste HTTP/L7 da ispezionare; i "serventi" sono gli m
#   moduli di ispezione (DPI/TLS). Se il nodo e' pieno (K job dentro) le nuove
#   richieste vengono SCARTATE (drop-tail): e' cio' che rende finito P_loss.
#
# ADERENZA AL CASO REALE  (novita' di questa versione)
#   L'attacco DDoS reale NON e' stazionario: e' IMPULSIVO. La botnet AISURU nel
#   2025 ha prodotto picchi brevissimi (35-69 s). Per riprodurlo il simulatore
#   supporta un profilo d'attacco a FASCE temporali (es. Normale -> Picco ->
#   Mitigazione): in ogni fase i tassi lambda1(t) e lambda2(t) cambiano. Il
#   passaggio di fascia e' un EVENTO ARTIFICIALE (tecnica vista a lezione: si
#   evita cosi' il Poisson non-omogeneo NHPP, non trattato nel corso).
#   La derivazione dei parametri dai numeri reali e le fonti sono in scenarios.py.
#
# DISCIPLINA: priorita' astratta NON-PREEMPTIVE (coda 1 prima della coda 2; un
#   job in servizio non viene mai interrotto).
#
# METODO: simulazione next-event (Leemis & Park cap. 5); accumulatori d'area
#   aggiornati PRIMA di ogni cambio di stato; PRNG multi-stream rngs/rvgs con uno
#   stream dedicato per processo (Common Random Numbers per confronti puliti).
#
# RIPRODUCIBILITA': PlantSeeds() UNA sola volta nel chiamante (mai qui dentro).
# -----------------------------------------------------------------------------

from collections import deque
from rngs import SelectStream, PlantSeeds
from rvgs import Exponential

# --- Stream dedicati (disaccoppiamento dei processi stocastici) ---------------
STREAM_ARR1 = 0   # interarrivi Classe 1 (legittimo)
STREAM_ARR2 = 1   # interarrivi Classe 2 (attacco)
STREAM_SRV1 = 2   # tempi di servizio Classe 1
STREAM_SRV2 = 3   # tempi di servizio Classe 2

INFINITY = float("inf")


# --------------------------- Generatori dei processi -------------------------
def _exp_arrival(stream, lam):
    """Prossimo interarrivo per un flusso di frequenza lam (job/s).
       Se lam<=0 il flusso e' spento -> nessun arrivo (INFINITY)."""
    if lam <= 0.0:
        return INFINITY
    SelectStream(stream)
    return Exponential(1.0 / lam)

def _exp_service(stream, Es):
    """Tempo di servizio ~ Exp(media Es)."""
    SelectStream(stream)
    return Exponential(Es)


# ------------------------------ Fasce d'attacco ------------------------------
# Una "fascia" (phase) e' un intervallo in cui i tassi sono costanti.
# Formato: lista di dizionari {"dur": durata[s], "lambda1":..., "lambda2":...}.
# Esempio (attacco): Normale -> Picco -> Mitigazione.
def single_phase(lambda1, lambda2, duration):
    """Comodita': un solo regime costante per tutta la simulazione
       (usato per dimensionamento nominale e per la verifica M/M/*)."""
    return [{"dur": duration, "lambda1": lambda1, "lambda2": lambda2}]


# --------------------------- Nucleo di simulazione ---------------------------
def run_simulation(cfg):
    """Esegue UNA run e restituisce un dizionario di metriche (leggi operazionali).

    cfg deve contenere:
        m, K, Es1, Es2              -> serventi, buffer, tempi medi di servizio
        phases                      -> lista di fasce (vedi sopra); la durata
                                       totale della run e' la somma delle durate.
    NON chiama PlantSeeds: la sequenza casuale e' quella lasciata dal chiamante
    (permette repliche indipendenti e Common Random Numbers).
    """
    m   = cfg["m"]
    K   = cfg["K"]
    Es1 = cfg["Es1"]
    Es2 = cfg["Es2"]
    phases = cfg["phases"]
    P = len(phases)
    STOP = sum(ph["dur"] for ph in phases)     # orizzonte totale (fine ultima fascia)

    # ======================= VARIABILI DI STATO S(t) =========================
    clock = 0.0
    n1 = 0                     # job Classe 1 nel nodo (coda + servizio)
    n2 = 0                     # job Classe 2 nel nodo
    q1 = deque()              # coda Cl.1: timestamp d'arrivo dei job in attesa
    q2 = deque()              # coda Cl.2
    srv_busy  = [False] * m    # servente occupato?
    srv_class = [0] * m        # classe del job in servizio (1/2; 0 = nessuno)
    srv_arr   = [0.0] * m      # istante d'arrivo del job in servizio (per il response)

    # --- fascia corrente e tassi attivi ---
    cur = 0                                     # indice della fascia in corso
    lam1 = phases[0]["lambda1"]
    lam2 = phases[0]["lambda2"]
    phase_end = phases[0]["dur"]               # istante di fine della fascia 0

    # ========================= LISTA DEGLI EVENTI ============================
    t_arr1 = _exp_arrival(STREAM_ARR1, lam1)   # primo arrivo Cl.1
    t_arr2 = _exp_arrival(STREAM_ARR2, lam2)   # primo arrivo Cl.2
    t_comp = [INFINITY] * m                     # completamenti (uno per servente)
    # (l'evento artificiale "cambio fascia" e' rappresentato da phase_end;
    #  l'evento STOP coincide con la fine dell'ultima fascia.)

    # ======================= ACCUMULATORI STATISTICI =========================
    area_node1 = area_node2 = 0.0
    area_q1    = area_q2    = 0.0
    area_srv   = 0.0
    sum_resp1  = sum_resp2  = 0.0
    sum_delay1 = sum_delay2 = 0.0
    arr1 = arr2 = 0
    cmp1 = cmp2 = 0
    drp1 = drp2 = 0
    # --- per-fascia: arrivi/scarti (per calcolare P_loss DURANTE il picco) ---
    ph_arr1 = [0]*P; ph_arr2 = [0]*P
    ph_drp1 = [0]*P; ph_drp2 = [0]*P
    ph_areaN = [0.0]*P                          # integrale popolazione totale per fascia
    ph_time  = [0.0]*P                           # tempo trascorso in ciascuna fascia

    # --- helper interni ---
    def find_free_server():
        for s in range(m):
            if not srv_busy[s]:
                return s
        return -1

    def busy_count():
        c = 0
        for s in range(m):
            if srv_busy[s]:
                c += 1
        return c

    def next_event():
        """Evento imminente = tempo minimo tra: arrivi, completamenti, fine-fascia.
           Ritorna (tipo, indice, tempo). tipo in {'A1','A2','C','PH'}."""
        t_min = phase_end                       # la fine della fascia e' sempre schedulata
        ev = ('PH', -1)
        if t_arr1 < t_min:
            t_min, ev = t_arr1, ('A1', -1)
        if t_arr2 < t_min:
            t_min, ev = t_arr2, ('A2', -1)
        for s in range(m):
            if t_comp[s] < t_min:
                t_min, ev = t_comp[s], ('C', s)
        return ev[0], ev[1], t_min

    # =============================== CICLO EVENTI ============================
    while True:
        etype, s_idx, t_next = next_event()

        # (1) integrali d'area su [clock, t_next] PRIMA del cambio di stato
        dt = t_next - clock
        area_node1 += dt * n1
        area_node2 += dt * n2
        area_q1    += dt * len(q1)
        area_q2    += dt * len(q2)
        area_srv   += dt * busy_count()
        ph_areaN[cur] += dt * (n1 + n2)         # popolazione integrata nella fascia
        ph_time[cur]  += dt
        clock = t_next

        # ----------------------- CAMBIO FASCIA / STOP -----------------------
        if etype == 'PH':
            cur += 1
            if cur >= P:                        # era l'ultima fascia -> fine run
                break
            # nuova fascia: aggiorna i tassi ed (essendo esponenziali, memoryless)
            # ricampiona i prossimi arrivi col nuovo tasso.
            lam1 = phases[cur]["lambda1"]
            lam2 = phases[cur]["lambda2"]
            phase_end += phases[cur]["dur"]
            t_arr1 = clock + _exp_arrival(STREAM_ARR1, lam1)
            t_arr2 = clock + _exp_arrival(STREAM_ARR2, lam2)
            continue

        # ------------------------- ARRIVO CLASSE 1 --------------------------
        if etype == 'A1':
            arr1 += 1; ph_arr1[cur] += 1
            if n1 + n2 < K:                     # c'e' posto?
                n1 += 1
                s = find_free_server()
                if s != -1:                    # servizio immediato
                    srv_busy[s]  = True
                    srv_class[s] = 1
                    srv_arr[s]   = clock
                    sum_delay1  += 0.0
                    t_comp[s]    = clock + _exp_service(STREAM_SRV1, Es1)
                else:                          # in coda (prioritaria)
                    q1.append(clock)
            else:
                drp1 += 1; ph_drp1[cur] += 1    # buffer pieno -> scarto
            t_arr1 = clock + _exp_arrival(STREAM_ARR1, lam1)

        # ------------------------- ARRIVO CLASSE 2 --------------------------
        elif etype == 'A2':
            arr2 += 1; ph_arr2[cur] += 1
            if n1 + n2 < K:
                n2 += 1
                s = find_free_server()
                if s != -1:
                    srv_busy[s]  = True
                    srv_class[s] = 2
                    srv_arr[s]   = clock
                    sum_delay2  += 0.0
                    t_comp[s]    = clock + _exp_service(STREAM_SRV2, Es2)
                else:
                    q2.append(clock)
            else:
                drp2 += 1; ph_drp2[cur] += 1
            t_arr2 = clock + _exp_arrival(STREAM_ARR2, lam2)

        # --------------------- COMPLETAMENTO SERVENTE s ---------------------
        else:  # etype == 'C'
            s = s_idx
            c = srv_class[s]
            resp = clock - srv_arr[s]           # response = uscita - suo arrivo
            if c == 1:
                cmp1 += 1; n1 -= 1; sum_resp1 += resp
            else:
                cmp2 += 1; n2 -= 1; sum_resp2 += resp
            # priorita' NON-PREEMPTIVE: prima la coda 1, poi la coda 2
            if len(q1) > 0:
                arr_ts = q1.popleft()
                srv_busy[s]=True; srv_class[s]=1; srv_arr[s]=arr_ts
                sum_delay1 += clock - arr_ts
                t_comp[s] = clock + _exp_service(STREAM_SRV1, Es1)
            elif len(q2) > 0:
                arr_ts = q2.popleft()
                srv_busy[s]=True; srv_class[s]=2; srv_arr[s]=arr_ts
                sum_delay2 += clock - arr_ts
                t_comp[s] = clock + _exp_service(STREAM_SRV2, Es2)
            else:
                srv_busy[s]=False; srv_class[s]=0; t_comp[s]=INFINITY

    # ===================== METRICHE (LEGGI OPERAZIONALI) ====================
    T = clock
    def safe(a, b): return a / b if b > 0 else 0.0

    # P_loss per fascia (utile per leggere la perdita DURANTE il picco d'attacco)
    per_phase = []
    for i in range(P):
        per_phase.append({
            "dur": ph_time[i],
            "lambda1": phases[i]["lambda1"], "lambda2": phases[i]["lambda2"],
            "Ploss1": safe(ph_drp1[i], ph_arr1[i]),
            "Ploss2": safe(ph_drp2[i], ph_arr2[i]),
            "E_N":    safe(ph_areaN[i], ph_time[i]),
        })

    return {
        "E_N1":  safe(area_node1, T), "E_N2": safe(area_node2, T),
        "E_Nq1": safe(area_q1, T),    "E_Nq2": safe(area_q2, T),
        "E_Ts1": safe(sum_resp1, cmp1), "E_Ts2": safe(sum_resp2, cmp2),
        "E_Tq1": safe(sum_delay1, cmp1), "E_Tq2": safe(sum_delay2, cmp2),
        "X1": safe(cmp1, T), "X2": safe(cmp2, T),
        "U":  safe(area_srv, m * T),
        "Ploss1": safe(drp1, arr1), "Ploss2": safe(drp2, arr2),
        "arr1": arr1, "arr2": arr2, "cmp1": cmp1, "cmp2": cmp2,
        "drp1": drp1, "drp2": drp2, "in_system_end": n1 + n2, "T": T,
        "phases": per_phase,
    }


# ============================== DEMO (singola run) ==========================
if __name__ == "__main__":
    # Import locale per non creare dipendenze circolari nei moduli di calcolo.
    from scenarios import scenario_nominal, scenario_attack, print_real_mapping

    print_real_mapping()

    # ---- 1) Regime NOMINALE (nessun attacco, costante) ----
    PlantSeeds(123456789)
    rn = run_simulation(scenario_nominal())
    print("\n=== REGIME NOMINALE (solo fondo, costante) ===")
    print(f" E[Ts] legittimo = {rn['E_Ts1']*1e3:.3f} ms   U = {rn['U']:.3f}   "
          f"Ploss1 = {rn['Ploss1']*100:.3f}%")

    # ---- 2) ATTACCO a 3 fasce (Normale -> Picco -> Mitigazione) ----
    PlantSeeds(123456789)
    ra = run_simulation(scenario_attack())
    print("\n=== ATTACCO AISURU a fasce (orizzonte finito) ===")
    print(f" GLOBALE: E[Ts]1={ra['E_Ts1']*1e3:.2f} ms  Ploss1={ra['Ploss1']*100:.2f}%  "
          f"Ploss2={ra['Ploss2']*100:.2f}%  U={ra['U']:.3f}")
    nomi = ["Normale", "Picco", "Mitigazione"]
    for i, ph in enumerate(ra["phases"]):
        nome = nomi[i] if i < len(nomi) else f"fase{i}"
        print(f"  [{nome:11s}] dur={ph['dur']:5.1f}s  lambda2={ph['lambda2']:8.0f}/s  "
              f"Ploss1={ph['Ploss1']*100:6.2f}%  Ploss2={ph['Ploss2']*100:6.2f}%  E[N]={ph['E_N']:7.1f}")
    print("\n Interpretazione: durante il PICCO la coda satura e il legittimo (Cl.1)")
    print(" inizia a subire perdita nonostante la priorita' -> qui si ipotizzano le")
    print(" contromisure (piu' serventi / autoscaling / K maggiore): vedi Step 8.")
