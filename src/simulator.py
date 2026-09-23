# Nodo di scrubbing DDoS (AISURU 2025) - simulatore next-event.
# REALISMO: il sistema NON conosce la vera classe. Un classificatore imperfetto
# etichetta ogni richiesta come "sospetta" o no (rilevamento d, falsi positivi f)
# e le contromisure agiscono SULL'ETICHETTA. Le metriche misurano il traffico
# DAVVERO legittimo (classe vera 1). PlantSeeds() va chiamata dal chiamante.

import heapq
from collections import deque
from rngs import SelectStream, PlantSeeds, Random
from rvgs import Exponential

S_ARR = [0, 0, 1]   # stream arrivi per classe vera (1,2)
S_SRV = [0, 2, 3]   # stream servizi per classe vera
S_CLF = 4           # stream del classificatore
INF = float("inf")


def _arr(stream, lam):
    if lam <= 0.0:
        return INF
    SelectStream(stream)
    return Exponential(1.0 / lam)


def _srv(stream, mean):
    SelectStream(stream)
    return Exponential(mean)


def single_phase(lambda1, lambda2, duration):
    return [{"dur": duration, "lambda1": lambda1, "lambda2": lambda2}]


def run_simulation(cfg):
    """Una run. cfg: m, K, Es1, Es2, phases, clf{d,f}, policy{name,...}.
    Ritorna metriche del traffico vero (Ploss1 = perdita del legittimo)."""
    K = cfg["K"]
    Es = [0.0, cfg["Es1"], cfg["Es2"]]
    phases = cfg["phases"]
    P = len(phases)
    clf = cfg.get("clf", {"d": 1.0, "f": 0.0})
    d, f = clf["d"], clf["f"]
    pol = cfg.get("policy", {"name": "base"})
    name = pol["name"]
    K_susp = pol.get("K_susp", K)          # ammissione sospetti (fast-track)
    rl_rate = pol.get("rate", INF)         # rate-limit sospetti
    rl_burst = pol.get("burst", 1.0)

    m0 = cfg["m"]
    if name == "autoscale":
        m_min, m_max = pol.get("m_min", m0), pol["m_max"]
        up, down, setup = pol["up"], pol["down"], pol.get("setup", 0.0)
    else:
        m_min = m_max = m0
        up = down = setup = 0
    M = m_max
    start_active = m_min if name == "autoscale" else m0
    active = [i < start_active for i in range(M)]
    n_active = start_active
    free_srv = [i for i in range(start_active)]   # stack serventi liberi

    # stato
    clock = 0.0
    n = [0, 0, 0]                        # job veri nel nodo per classe
    qG, qS = deque(), deque()           # code (ts, classe_vera): G=non sospetti, S=sospetti
    scls = [0] * M
    sarr = [0.0] * M
    t_c = [INF] * M
    comp = []                           # heap (t_completamento, servente)
    n_busy = 0
    tokens, last_ref = rl_burst, 0.0
    t_act = INF

    cur = 0
    lam = [0.0, phases[0]["lambda1"], phases[0]["lambda2"]]
    phase_end = phases[0]["dur"]
    t_a = [0.0, _arr(S_ARR[1], lam[1]), _arr(S_ARR[2], lam[2])]

    # accumulatori (per classe VERA)
    area_node = [0.0, 0.0, 0.0]
    sum_resp = [0.0, 0.0, 0.0]
    arr = [0, 0, 0]
    done = [0, 0, 0]
    drop = [0, 0, 0]
    ph_arr = [[0] * P, [0] * P, [0] * P]
    ph_drop = [[0] * P, [0] * P, [0] * P]
    ph_N = [0.0] * P
    ph_T = [0.0] * P
    area_srv = 0.0

    def classify(k):
        SelectStream(S_CLF)
        u = Random()
        return 1 if (u < f if k == 1 else u < d) else 0    # 1 = "sospetto"

    def start_service(s, k, ts):
        nonlocal n_busy
        scls[s] = k
        sarr[s] = ts
        tc = clock + _srv(S_SRV[k], Es[k])
        t_c[s] = tc
        heapq.heappush(comp, (tc, s))
        n_busy += 1

    def place(k, lane_s):
        n[k] += 1
        if free_srv:
            start_service(free_srv.pop(), k, clock)
        else:
            (qS if lane_s else qG).append((clock, k))

    def admit(k, susp):
        nonlocal tokens, last_ref
        ntot = n[1] + n[2]
        if name == "fasttrack":
            if ntot >= (K_susp if susp else K):
                return False
            place(k, susp)
            return True
        if name == "ratelimit" and susp:
            tokens = min(rl_burst, tokens + rl_rate * (clock - last_ref))
            last_ref = clock
            if tokens < 1.0 or ntot >= K:
                return False
            tokens -= 1.0
            place(k, False)
            return True
        if ntot >= K:
            return False
        place(k, False)
        return True

    def handle_arrival(k):
        nonlocal t_act
        arr[k] += 1
        ph_arr[k][cur] += 1
        if not admit(k, classify(k)):
            drop[k] += 1
            ph_drop[k][cur] += 1
        elif name == "autoscale" and (n[1] + n[2]) >= up and n_active < m_max and t_act == INF:
            t_act = clock + setup          # programma attivazione servente
        t_a[k] = clock + _arr(S_ARR[k], lam[k])

    def handle_completion(s):
        nonlocal n_busy, n_active
        k = scls[s]
        done[k] += 1
        n[k] -= 1
        sum_resp[k] += clock - sarr[s]
        n_busy -= 1
        t_c[s] = INF
        if qG:
            ts, kk = qG.popleft()
            start_service(s, kk, ts)
        elif qS:
            ts, kk = qS.popleft()
            start_service(s, kk, ts)
        elif name == "autoscale" and (n[1] + n[2]) <= down and n_active > m_min:
            active[s] = False              # scale-down: spegne il servente idle
            n_active -= 1
        else:
            free_srv.append(s)

    def handle_activation():
        nonlocal t_act, n_active
        t_act = INF
        for s in range(M):
            if not active[s]:
                active[s] = True
                n_active += 1
                if qG or qS:
                    q = qG if qG else qS
                    ts, kk = q.popleft()
                    start_service(s, kk, ts)
                else:
                    free_srv.append(s)
                break

    def next_completion():
        while comp and comp[0][0] != t_c[comp[0][1]]:
            heapq.heappop(comp)            # scarta entry obsolete (lazy heap)
        return comp[0] if comp else (INF, -1)

    # ciclo eventi
    while True:
        tc, cs = next_completion()
        tmin, etype, idx = phase_end, "PH", -1
        if t_a[1] < tmin:
            tmin, etype, idx = t_a[1], "A", 1
        if t_a[2] < tmin:
            tmin, etype, idx = t_a[2], "A", 2
        if t_act < tmin:
            tmin, etype, idx = t_act, "ACT", -1
        if tc < tmin:
            tmin, etype, idx = tc, "C", cs

        dt = tmin - clock
        area_node[1] += dt * n[1]
        area_node[2] += dt * n[2]
        area_srv += dt * n_busy
        ph_N[cur] += dt * (n[1] + n[2])
        ph_T[cur] += dt
        clock = tmin

        if etype == "PH":
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
        elif etype == "ACT":
            handle_activation()
        else:
            handle_completion(idx)

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
        "E_N1": rate(area_node[1], T), "E_N2": rate(area_node[2], T),
        "X1": rate(done[1], T), "X2": rate(done[2], T), "U": rate(area_srv, m_max * T),
        "Ploss1": rate(drop[1], arr[1]), "Ploss2": rate(drop[2], arr[2]),
        "T": T, "phases": per_phase,
    }


# colori ANSI
G, R, Y, B, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[2m", "\033[0m"


def col(p):
    color = G if p < 0.01 else Y if p < 0.10 else R
    return f"{color}{p * 100:5.1f}%{RST}"


def _demo():
    from scenarios import scenario_nominal, scenario_attack
    PlantSeeds(123456789)
    rn = run_simulation(scenario_nominal())
    print(f"{B}NOMINALE{RST}  E[Ts]1={rn['E_Ts1'] * 1e3:.2f}ms  "
          f"U={rn['U']:.2f}  perdita legittimo={col(rn['Ploss1'])}")

    PlantSeeds(123456789)
    ra = run_simulation(scenario_attack())
    print(f"\n{B}ATTACCO a fasce (BASE, class-blind){RST}")
    nomi = ["Normale", "Picco", "Mitigazione"]
    for i, ph in enumerate(ra["phases"]):
        print(f"  {nomi[i]:12s} lam2={ph['lambda2']:>7.0f}/s   "
              f"legittimo perso {col(ph['Ploss1'])}")


if __name__ == "__main__":
    _demo()
