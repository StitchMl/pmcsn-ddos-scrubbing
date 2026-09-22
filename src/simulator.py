# -----------------------------------------------------------------------------
# simulator.py  --  Simulatore Next-Event del nodo di scrubbing DDoS (MODELLO BASE)
# =============================================================================
# Progetto PMCSN - caso reale AISURU 2025.
#
# COSA MODELLA
#   Un nodo di "scrubbing" (mitigazione DDoS) di un PoP CDN, astratto come una
#   STAZIONE DI SERVIZIO MULTI-SERVER con BUFFER FINITO, alimentata da due classi
#   di traffico:
#       - Classe 1 = traffico legittimo  (priorita' ALTA, ha una SLA da rispettare)
#       - Classe 2 = traffico d'attacco  (priorita' BASSA)
#   I "job" sono le richieste/pacchetti da ispezionare; i "serventi" sono i
#   m moduli di ispezione (DPI/TLS). Se il nodo e' pieno (K job dentro) le nuove
#   richieste vengono SCARTATE (drop-tail): e' cio' che rende finito P_loss.
#
# DISCIPLINA DI SERVIZIO
#   Priorita' astratta NON-PREEMPTIVE: quando un servente si libera prende prima
#   i job della coda 1 (legittimi) e solo se questa e' vuota quelli della coda 2;
#   un job gia' in servizio NON viene mai interrotto (non-preemptive).
#
# METODO DI SIMULAZIONE (Leemis & Park, cap. 5 - "next-event")
#   Il tempo NON avanza a passi fissi: salta di evento in evento. Ad ogni giro:
#     1) si individua l'evento imminente (tempo minimo nella "lista eventi");
#     2) si aggiornano gli INTEGRALI D'AREA sull'intervallo appena trascorso
#        (statistiche time-averaged) -> DEVE avvenire PRIMA di cambiare lo stato;
#     3) si fa avanzare il clock e si gestisce l'evento (che puo' schedularne altri).
#
# NUMERI CASUALI
#   Libreria multi-stream rngs/rvgs (del corso). Ogni processo stocastico usa uno
#   STREAM dedicato e disgiunto (arrivi cl.1, arrivi cl.2, servizi cl.1, servizi
#   cl.2), cosi' cambiare un parametro di servizio non altera la sequenza degli
#   arrivi -> confronti "puliti" (Common Random Numbers) tra configurazioni.
#
# IMPORTANTE - RIPRODUCIBILITA'
#   PlantSeeds() (che pianta i 256 semi) va chiamata UNA SOLA VOLTA dal codice
#   chiamante (il runner delle repliche), MAI dentro run_simulation(): cosi' le
#   repliche partono da punti disgiunti del generatore e restano indipendenti.
#   Qui sotto la chiamiamo solo nel blocco __main__, per una singola run demo.
# -----------------------------------------------------------------------------

from collections import deque          # code FIFO efficienti (append a destra, pop a sinistra)
from rngs import SelectStream, PlantSeeds, GetSeed
from rvgs import Exponential

# --- Assegnazione degli STREAM ai processi stocastici (disaccoppiamento) ------
# Interi qualsiasi in 0..255, purche' DIVERSI tra loro: identificano flussi di
# numeri casuali indipendenti dentro rngs.
STREAM_ARR1 = 0   # interarrivi Classe 1 (legittimo)
STREAM_ARR2 = 1   # interarrivi Classe 2 (attacco)
STREAM_SRV1 = 2   # tempi di servizio Classe 1
STREAM_SRV2 = 3   # tempi di servizio Classe 2

INFINITY = float("inf")   # marcatore di "evento non schedulato/impossibile"


# ------------------------- Configurazione di default -------------------------
def default_config():
    """Parametri BASELINE del modello (vedi README sez. 2 - sono placeholder da tarare).
    Convenzione unita': tempi in SECONDI, frequenze in JOB/SECONDO.

    Con questi valori: rho = (lambda1*Es1 + lambda2*Es2)/m = 30000*1e-4/4 = 0.75
    quindi il sistema e' STABILE (rho < 1) e a K=50 non ci sono praticamente scarti.
    """
    return {
        "m":         4,        # numero di serventi (moduli di scrubbing)
        "K":         50,       # capacita' totale del nodo (job in servizio + in coda)
        "lambda1":   6000.0,   # frequenza arrivi Classe 1 (legittimo)  [job/s]
        "lambda2":   24000.0,  # frequenza arrivi Classe 2 (attacco)    [job/s]
        "Es1":       1.0e-4,   # tempo medio di servizio Classe 1 = 1/mu1 [s]  (0.1 ms)
        "Es2":       1.0e-4,   # tempo medio di servizio Classe 2 = 1/mu2 [s]
        "stop_time": 20.0,     # orizzonte/finestra di osservazione della run [s]
    }


# ------------------------- Generatori dei processi ---------------------------
# Ogni funzione: (1) seleziona il PROPRIO stream, (2) estrae un campione.
# Exponential(media) restituisce un tempo esponenziale di media data.
#   - interarrivo di media 1/lambda  (freq. lambda)
#   - tempo di servizio di media Es = 1/mu

def get_arrival1(lam):
    SelectStream(STREAM_ARR1)          # isola la sequenza degli arrivi Cl.1
    return Exponential(1.0 / lam)      # interarrivo ~ Exp(media = 1/lambda1)

def get_arrival2(lam):
    SelectStream(STREAM_ARR2)
    return Exponential(1.0 / lam)

def get_service1(Es):
    SelectStream(STREAM_SRV1)          # isola la sequenza dei servizi Cl.1
    return Exponential(Es)             # servizio ~ Exp(media = Es1)

def get_service2(Es):
    SelectStream(STREAM_SRV2)
    return Exponential(Es)


# --------------------------- Nucleo di simulazione ---------------------------
def run_simulation(cfg):
    """Esegue UNA run del modello base e restituisce un dizionario di metriche
    (medie calcolate con le leggi operazionali). NON chiama PlantSeeds: la
    sequenza di numeri casuali e' quella lasciata dal chiamante -> permette
    repliche indipendenti e Common Random Numbers."""

    # --- lettura parametri ---
    m   = cfg["m"]
    K   = cfg["K"]
    lam1, lam2 = cfg["lambda1"], cfg["lambda2"]
    Es1, Es2   = cfg["Es1"], cfg["Es2"]
    STOP = cfg["stop_time"]

    # ======================= VARIABILI DI STATO S(t) =========================
    clock = 0.0                # orologio di simulazione (tempo corrente)
    n1 = 0                     # n. job Classe 1 nel nodo (in coda + in servizio)
    n2 = 0                     # n. job Classe 2 nel nodo
    q1 = deque()              # coda d'attesa Cl.1: contiene i TIMESTAMP DI ARRIVO
    q2 = deque()              # coda d'attesa Cl.2: (servono per calcolare l'attesa)
    # stato di ciascun servente s = 0..m-1:
    srv_busy  = [False] * m    #   e' occupato?
    srv_class = [0] * m        #   classe del job che sta servendo (1 o 2; 0 = nessuno)
    srv_arr   = [0.0] * m      #   istante d'arrivo del job in servizio (per il tempo di risposta)

    # ========================= LISTA DEGLI EVENTI ============================
    # Rappresentata da: prossimo arrivo Cl.1, prossimo arrivo Cl.2, e un tempo di
    # completamento per OGNI servente (INFINITY se il servente e' libero).
    t_arr1 = get_arrival1(lam1)        # istante del primo arrivo Cl.1
    t_arr2 = get_arrival2(lam2)        # istante del primo arrivo Cl.2
    t_comp = [INFINITY] * m            # nessun completamento pendente all'avvio

    # ======================= ACCUMULATORI STATISTICI =========================
    # (A) integrali temporali (time-averaged): area sotto le curve di popolazione.
    area_node1 = area_node2 = 0.0      # integraledi n1(t) e n2(t) -> E[N] per classe
    area_q1    = area_q2    = 0.0      # integrale della lunghezza di coda -> E[Nq]
    area_srv   = 0.0                   # integrale del n. di serventi occupati -> U
    # (B) somme per job (job-averaged): per i tempi medi.
    sum_resp1  = sum_resp2  = 0.0      # somma dei tempi di RISPOSTA (uscita - arrivo)
    sum_delay1 = sum_delay2 = 0.0      # somma dei tempi di ATTESA in coda (inizio_servizio - arrivo)
    # (C) contatori di flusso.
    arr1 = arr2 = 0                    # arrivi totali generati per classe
    cmp1 = cmp2 = 0                    # completamenti (job serviti) per classe
    drp1 = drp2 = 0                    # scarti per buffer pieno per classe

    # --- piccoli helper interni ---
    def find_free_server():
        """Indice del primo servente libero, oppure -1 se tutti occupati."""
        for s in range(m):
            if not srv_busy[s]:
                return s
        return -1

    def busy_count():
        """Numero di serventi attualmente occupati (per l'integrale di utilizzazione)."""
        c = 0
        for s in range(m):
            if srv_busy[s]:
                c += 1
        return c

    def next_event():
        """Trova l'evento imminente = quello con tempo MINIMO nella lista eventi.
        Ritorna (tipo, indice_servente, tempo). tipo in {'A1','A2','C','STOP'}.
        'STOP' e' l'evento artificiale di fine osservazione (orizzonte finito)."""
        t_min = STOP                    # se nulla accade prima, ci si ferma a STOP
        ev = ('STOP', -1)
        if t_arr1 < t_min:              # e' prima un arrivo Cl.1?
            t_min, ev = t_arr1, ('A1', -1)
        if t_arr2 < t_min:              # ... o un arrivo Cl.2?
            t_min, ev = t_arr2, ('A2', -1)
        for s in range(m):              # ... o il completamento di un servente?
            if t_comp[s] < t_min:
                t_min, ev = t_comp[s], ('C', s)
        return ev[0], ev[1], t_min

    # =============================== CICLO EVENTI ============================
    while True:
        etype, s_idx, t_next = next_event()   # 1) prossimo evento

        # 2) AGGIORNAMENTO DELLE AREE sull'intervallo [clock, t_next].
        #    Va fatto PRIMA di toccare n1/n2/serventi: nell'intervallo lo stato
        #    e' ancora quello "vecchio". Invertire l'ordine introdurrebbe un bias.
        dt = t_next - clock
        area_node1 += dt * n1
        area_node2 += dt * n2
        area_q1    += dt * len(q1)
        area_q2    += dt * len(q2)
        area_srv   += dt * busy_count()
        clock = t_next                        # 3) avanza il clock all'evento

        if etype == 'STOP':                   # fine finestra di osservazione
            break

        # ------------------------- ARRIVO CLASSE 1 --------------------------
        if etype == 'A1':
            arr1 += 1                          # conta l'arrivo
            if n1 + n2 < K:                    # c'e' posto nel buffer?
                n1 += 1                        #   entra nel nodo
                s = find_free_server()
                if s != -1:                    #   servente libero -> servizio immediato
                    srv_busy[s]  = True
                    srv_class[s] = 1
                    srv_arr[s]   = clock       #   il "suo" arrivo e' adesso...
                    sum_delay1  += 0.0         #   ...quindi attesa in coda = 0
                    t_comp[s]    = clock + get_service1(Es1)   # schedula il completamento
                else:                          #   tutti occupati -> in coda Cl.1
                    q1.append(clock)           #   memorizza l'istante d'arrivo
            else:
                drp1 += 1                       # buffer pieno -> SCARTO (drop-tail)
            t_arr1 = clock + get_arrival1(lam1)  # schedula il prossimo arrivo Cl.1

        # ------------------------- ARRIVO CLASSE 2 --------------------------
        elif etype == 'A2':                     # simmetrico all'arrivo Cl.1
            arr2 += 1
            if n1 + n2 < K:
                n2 += 1
                s = find_free_server()
                if s != -1:
                    srv_busy[s]  = True
                    srv_class[s] = 2
                    srv_arr[s]   = clock
                    sum_delay2  += 0.0
                    t_comp[s]    = clock + get_service2(Es2)
                else:
                    q2.append(clock)
            else:
                drp2 += 1
            t_arr2 = clock + get_arrival2(lam2)

        # --------------------- COMPLETAMENTO SERVENTE s ---------------------
        else:  # etype == 'C'
            s = s_idx
            c = srv_class[s]                    # classe del job che esce
            resp = clock - srv_arr[s]           # tempo di risposta = uscita - suo arrivo
            if c == 1:
                cmp1 += 1; n1 -= 1; sum_resp1 += resp
            else:
                cmp2 += 1; n2 -= 1; sum_resp2 += resp

            # SCELTA DEL PROSSIMO JOB - priorita' NON-PREEMPTIVE:
            #   prima la coda 1 (legittimi); solo se vuota, la coda 2.
            if len(q1) > 0:
                arr_ts = q1.popleft()           # job legittimo piu' vecchio in coda
                srv_busy[s]  = True
                srv_class[s] = 1
                srv_arr[s]   = arr_ts           # ricorda il suo arrivo (per il response)
                sum_delay1  += clock - arr_ts   # attesa in coda = ora - suo arrivo
                t_comp[s]    = clock + get_service1(Es1)
            elif len(q2) > 0:
                arr_ts = q2.popleft()
                srv_busy[s]  = True
                srv_class[s] = 2
                srv_arr[s]   = arr_ts
                sum_delay2  += clock - arr_ts
                t_comp[s]    = clock + get_service2(Es2)
            else:                               # nessuno in attesa -> servente idle
                srv_busy[s]  = False
                srv_class[s] = 0
                t_comp[s]    = INFINITY          # nessun completamento pendente

    # ===================== METRICHE (LEGGI OPERAZIONALI) ====================
    T = clock                                   # durata effettiva della run
    def safe(a, b):                             # divisione protetta (evita 0/0)
        return a / b if b > 0 else 0.0

    metrics = {
        # --- popolazioni medie nel nodo e in coda (time-averaged) ---
        "E_N1":  safe(area_node1, T),           # E[N] Cl.1 = area_node1 / T
        "E_N2":  safe(area_node2, T),
        "E_Nq1": safe(area_q1, T),              # E[Nq] Cl.1
        "E_Nq2": safe(area_q2, T),
        # --- tempi medi (job-averaged) ---
        "E_Ts1": safe(sum_resp1, cmp1),         # E[Ts] = tempo di risposta medio
        "E_Ts2": safe(sum_resp2, cmp2),
        "E_Tq1": safe(sum_delay1, cmp1),        # E[Tq] = attesa media in coda
        "E_Tq2": safe(sum_delay2, cmp2),
        # --- throughput e utilizzazione ---
        "X1": safe(cmp1, T),                    # X = completamenti / T
        "X2": safe(cmp2, T),
        "U":  safe(area_srv, m * T),            # U = area serventi occupati / (m*T)
        # --- probabilita' di perdita per classe ---
        "Ploss1": safe(drp1, arr1),             # P_loss = scarti / arrivi
        "Ploss2": safe(drp2, arr2),
        # --- contatori grezzi (per la VERIFICA del bilancio dei flussi) ---
        "arr1": arr1, "arr2": arr2,
        "cmp1": cmp1, "cmp2": cmp2,
        "drp1": drp1, "drp2": drp2,
        "in_system_end": n1 + n2,               # job ancora nel nodo a fine run
        "T": T,
    }
    return metrics


# ============================== DEMO (singola run) ==========================
if __name__ == "__main__":
    cfg = default_config()

    # PlantSeeds UNA sola volta: qui e' una singola run dimostrativa.
    # (Nel runner degli esperimenti si chiamera' una volta e poi si faranno n repliche.)
    PlantSeeds(123456789)

    r = run_simulation(cfg)

    rho = (cfg['lambda1']*cfg['Es1'] + cfg['lambda2']*cfg['Es2']) / cfg['m']
    print("=== MODELLO BASE - singola run ===")
    print(f" m={cfg['m']}  K={cfg['K']}  lambda1={cfg['lambda1']}  "
          f"lambda2={cfg['lambda2']}  Es={cfg['Es1']}s  STOP={cfg['stop_time']}s")
    print(f" rho (nominale) = {rho:.4f}")
    print("-" * 52)
    print(f" Classe 1 (legittimo): E[Ts]={r['E_Ts1']*1e3:.4f} ms  "
          f"E[Tq]={r['E_Tq1']*1e3:.4f} ms  E[N]={r['E_N1']:.4f}  "
          f"Ploss={r['Ploss1']*100:.4f}%")
    print(f" Classe 2 (attacco):   E[Ts]={r['E_Ts2']*1e3:.4f} ms  "
          f"E[Tq]={r['E_Tq2']*1e3:.4f} ms  E[N]={r['E_N2']:.4f}  "
          f"Ploss={r['Ploss2']*100:.4f}%")
    print(f" Utilizzazione U = {r['U']:.4f}   X1={r['X1']:.1f} j/s   X2={r['X2']:.1f} j/s")
    print("-" * 52)
    # VERIFICA "bilancio dei flussi": per ogni classe deve valere
    #   arrivi = completamenti + scarti + (job rimasti nel nodo a fine run).
    bal1 = r['arr1'] - r['cmp1'] - r['drp1']    # deve = job Cl.1 residui nel nodo
    bal2 = r['arr2'] - r['cmp2'] - r['drp2']    # deve = job Cl.2 residui nel nodo
    print(" Bilancio flussi (arrivi - completamenti - scarti = residui nel nodo):")
    print(f"   Cl.1: {r['arr1']} - {r['cmp1']} - {r['drp1']} = {bal1}")
    print(f"   Cl.2: {r['arr2']} - {r['cmp2']} - {r['drp2']} = {bal2}")
    print(f"   (job totali ancora nel nodo a fine run = {r['in_system_end']}; "
          f"deve essere bal1+bal2 = {bal1+bal2})")
