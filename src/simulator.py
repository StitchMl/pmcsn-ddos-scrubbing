# simulator.py -- Nodo di scrubbing DDoS (caso AISURU 2025)
# Simulazione next-event: m serventi, buffer finito K, 2 classi
# (1=legittimo prioritario, 2=attacco), priorita' non-preemptive,
# attacco a fasce (Normale->Picco->Mitigazione). PRNG multi-stream rngs/rvgs.
# PlantSeeds() va chiamata UNA volta dal chiamante (non qui dentro).

from collections import deque
from rngs import SelectStream, PlantSeeds
from rvgs import Exponential

# stream dedicati: arrivi cl.1, arrivi cl.2, servizi cl.1, servizi cl.2
S_ARR = [0, 0, 1]     # indice per classe (1,2); posizione 0 inutilizzata
S_SRV = [0, 2, 3]
INF = float("inf")


def _arr(stream, lam):
    """Prossimo interarrivo (INF se il flusso e' spento)."""
    if lam <= 0.0:
        return INF
    SelectStream(stream)
    return Exponential(1.0 / lam)


def _srv(stream, mean):
    """Tempo di servizio ~ Exp(media)."""
    SelectStream(stream)
    return Exponential(mean)


def single_phase(lambda1, lambda2, duration):
    """Un solo regime costante (usato per nominale e verifica)."""
    return [{"dur": duration, "lambda1": lambda1, "lambda2": lambda2}]


def run_simulation(cfg):
    """Una run. cfg: m, K, Es1, Es2, phases[{dur,lambda1,lambda2}]. Ritorna metriche."""
    m = cfg["m"]
    K = cfg["K"]
    K2 = cfg.get("K2", K)                        # limite ammissione Classe 2 (K2<K = Fast-Track)
    phases = cfg["phases"]
    P = len(phases)
    Es = [0.0, cfg["Es1"], cfg["Es2"]]          # media di servizio per classe

    # --- stato ---
    clock = 0.0
    n = [0, 0, 0]                                # job nel nodo per classe
    queue = [None, deque(), deque()]            # code per classe (timestamp arrivo)
    busy = [False] * m
    scls = [0] * m                              # classe del job in servizio
    sarr = [0.0] * m                            # arrivo del job in servizio
    t_c = [INF] * m                             # completamenti per servente

    cur = 0                                      # fascia corrente
    lam = [0.0, phases[0]["lambda1"], phases[0]["lambda2"]]
    phase_end = phases[0]["dur"]
    t_a = [0.0, _arr(S_ARR[1], lam[1]), _arr(S_ARR[2], lam[2])]

    # --- accumulatori ---
    area_node = [0.0, 0.0, 0.0]
    area_q = [0.0, 0.0, 0.0]
    area_srv = 0.0
    sum_resp = [0.0, 0.0, 0.0]
    sum_delay = [0.0, 0.0, 0.0]
    arr = [0, 0, 0]
    done = [0, 0, 0]
    drop = [0, 0, 0]
    ph_arr = [[0] * P, [0] * P, [0] * P]
    ph_drop = [[0] * P, [0] * P, [0] * P]
    ph_N = [0.0] * P
    ph_T = [0.0] * P

    def free_server():
        for s in range(m):
            if not busy[s]:
                return s
        return -1

    def busy_count():
        return sum(1 for s in range(m) if busy[s])

    def start_service(s, k, arrival_ts):
        busy[s] = True
        scls[s] = k
        sarr[s] = arrival_ts
        t_c[s] = clock + _srv(S_SRV[k], Es[k])

    def next_event():
        tmin, ev = phase_end, ("PH", -1)
        if t_a[1] < tmin:
            tmin, ev = t_a[1], ("A", 1)
        if t_a[2] < tmin:
            tmin, ev = t_a[2], ("A", 2)
        for s in range(m):
            if t_c[s] < tmin:
                tmin, ev = t_c[s], ("C", s)
        return ev[0], ev[1], tmin

    def handle_arrival(k):
        arr[k] += 1
        ph_arr[k][cur] += 1
        limit = K if k == 1 else K2             # Classe 1 fino a K; Classe 2 solo fino a K2
        if n[1] + n[2] < limit:                 # c'e' posto (ammissione priority-aware)
            n[k] += 1
            s = free_server()
            if s != -1:
                start_service(s, k, clock)      # servizio immediato (attesa 0)
            else:
                queue[k].append(clock)          # in coda
        else:
            drop[k] += 1                        # buffer pieno -> scarto
            ph_drop[k][cur] += 1
        t_a[k] = clock + _arr(S_ARR[k], lam[k])

    def handle_completion(s):
        k = scls[s]
        done[k] += 1
        n[k] -= 1
        sum_resp[k] += clock - sarr[s]
        if queue[1]:                            # priorita': prima la coda 1
            a = queue[1].popleft()
            start_service(s, 1, a)
            sum_delay[1] += clock - a
        elif queue[2]:
            a = queue[2].popleft()
            start_service(s, 2, a)
            sum_delay[2] += clock - a
        else:
            busy[s] = False
            scls[s] = 0
            t_c[s] = INF

    # --- ciclo eventi ---
    while True:
        etype, idx, t_next = next_event()
        dt = t_next - clock                     # aree aggiornate PRIMA del cambio stato
        area_node[1] += dt * n[1]
        area_node[2] += dt * n[2]
        area_q[1] += dt * len(queue[1])
        area_q[2] += dt * len(queue[2])
        area_srv += dt * busy_count()
        ph_N[cur] += dt * (n[1] + n[2])
        ph_T[cur] += dt
        clock = t_next

        if etype == "PH":                       # cambio fascia / fine run
            cur += 1
            if cur >= P:
                break
            lam[1] = phases[cur]["lambda1"]
            lam[2] = phases[cur]["lambda2"]
            phase_end += phases[cur]["dur"]
            t_a[1] = clock + _arr(S_ARR[1], lam[1])
            t_a[2] = clock + _arr(S_ARR[2], lam[2])
        elif etype == "A":
            handle_arrival(idx)
        else:
            handle_completion(idx)

    # --- metriche (leggi operazionali) ---
    T = clock

    def rate(a, b):
        return a / b if b > 0 else 0.0

    per_phase = [{
        "lambda2": phases[i]["lambda2"], "dur": ph_T[i],
        "Ploss1": rate(ph_drop[1][i], ph_arr[1][i]),
        "Ploss2": rate(ph_drop[2][i], ph_arr[2][i]),
        "E_N": rate(ph_N[i], ph_T[i]),
    } for i in range(P)]

    return {
        "E_Ts1": rate(sum_resp[1], done[1]), "E_Ts2": rate(sum_resp[2], done[2]),
        "E_Tq1": rate(sum_delay[1], done[1]), "E_Tq2": rate(sum_delay[2], done[2]),
        "E_N1": rate(area_node[1], T), "E_N2": rate(area_node[2], T),
        "X1": rate(done[1], T), "X2": rate(done[2], T), "U": rate(area_srv, m * T),
        "Ploss1": rate(drop[1], arr[1]), "Ploss2": rate(drop[2], arr[2]),
        "T": T, "phases": per_phase,
    }


# --- colori ANSI (output leggibile su terminale moderno) ---
G, R, Y, B, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[2m", "\033[0m"


def col(p):
    """Colora una percentuale di perdita: verde ok, giallo medio, rosso alto."""
    color = G if p < 0.01 else Y if p < 0.10 else R
    return f"{color}{p * 100:5.1f}%{RST}"


def _demo():
    from scenarios import scenario_nominal, scenario_attack
    PlantSeeds(123456789)
    rn = run_simulation(scenario_nominal())
    print(f"{B}NOMINALE{RST}  E[Ts]1={rn['E_Ts1'] * 1e3:.2f}ms  "
          f"U={rn['U']:.2f}  perdita1={col(rn['Ploss1'])}")

    PlantSeeds(123456789)
    ra = run_simulation(scenario_attack())
    print(f"\n{B}ATTACCO a fasce{RST}   {DIM}(perdita = % richieste respinte){RST}")
    nomi = ["Normale", "Picco", "Mitigazione"]
    for i, ph in enumerate(ra["phases"]):
        print(f"  {nomi[i]:12s} lam2={ph['lambda2']:>7.0f}/s   "
              f"legittimo {col(ph['Ploss1'])}   attacco {col(ph['Ploss2'])}")


if __name__ == "__main__":
    _demo()
