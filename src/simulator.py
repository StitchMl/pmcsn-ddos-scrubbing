# simulator.py -- Nodo di scrubbing DDoS (caso AISURU 2025)
# Simulazione next-event: m serventi, buffer finito K, 2 classi
# (1=legittimo prioritario, 2=attacco), priorita' non-preemptive,
# attacco a fasce (Normale->Picco->Mitigazione). PRNG multi-stream rngs/rvgs.
# PlantSeeds() va chiamata UNA volta dal chiamante (non qui dentro).

from collections import deque
from rngs import SelectStream, PlantSeeds
from rvgs import Exponential

# stream dedicati: arrivi cl.1, arrivi cl.2, servizi cl.1, servizi cl.2
S_ARR1, S_ARR2, S_SRV1, S_SRV2 = 0, 1, 2, 3
INF = float("inf")


def _arr(stream, lam):
    if lam <= 0.0:
        return INF
    SelectStream(stream)
    return Exponential(1.0 / lam)

def _srv(stream, Es):
    SelectStream(stream)
    return Exponential(Es)


def single_phase(lambda1, lambda2, duration):
    return [{"dur": duration, "lambda1": lambda1, "lambda2": lambda2}]


def run_simulation(cfg):
    """Una run. cfg: m, K, Es1, Es2, phases[{dur,lambda1,lambda2}]. Ritorna metriche."""
    m, K, Es1, Es2 = cfg["m"], cfg["K"], cfg["Es1"], cfg["Es2"]
    phases = cfg["phases"]
    P = len(phases)

    # stato
    clock = 0.0
    n1 = n2 = 0
    q1, q2 = deque(), deque()                 # code: timestamp d'arrivo
    busy = [False] * m
    cls  = [0] * m
    tarr = [0.0] * m                          # arrivo del job in servizio

    cur = 0
    lam1, lam2 = phases[0]["lambda1"], phases[0]["lambda2"]
    phase_end = phases[0]["dur"]

    t_a1 = _arr(S_ARR1, lam1)
    t_a2 = _arr(S_ARR2, lam2)
    t_c  = [INF] * m

    # accumulatori
    aN1 = aN2 = aQ1 = aQ2 = aS = 0.0
    rR1 = rR2 = dD1 = dD2 = 0.0
    A1 = A2 = C1 = C2 = D1 = D2 = 0
    phA1 = [0]*P; phA2 = [0]*P; phD1 = [0]*P; phD2 = [0]*P
    phN = [0.0]*P; phT = [0.0]*P

    def free():
        for s in range(m):
            if not busy[s]:
                return s
        return -1

    def nbusy():
        return sum(1 for s in range(m) if busy[s])

    def nxt():
        t, ev = phase_end, ('PH', -1)
        if t_a1 < t: t, ev = t_a1, ('A1', -1)
        if t_a2 < t: t, ev = t_a2, ('A2', -1)
        for s in range(m):
            if t_c[s] < t: t, ev = t_c[s], ('C', s)
        return ev[0], ev[1], t

    while True:
        et, s_i, t_next = nxt()
        dt = t_next - clock
        aN1 += dt*n1; aN2 += dt*n2
        aQ1 += dt*len(q1); aQ2 += dt*len(q2)
        aS  += dt*nbusy()
        phN[cur] += dt*(n1+n2); phT[cur] += dt
        clock = t_next

        if et == 'PH':
            cur += 1
            if cur >= P:
                break
            lam1, lam2 = phases[cur]["lambda1"], phases[cur]["lambda2"]
            phase_end += phases[cur]["dur"]
            t_a1 = clock + _arr(S_ARR1, lam1)   # exp memoryless -> ricampiono
            t_a2 = clock + _arr(S_ARR2, lam2)
            continue

        if et == 'A1':
            A1 += 1; phA1[cur] += 1
            if n1+n2 < K:
                n1 += 1; s = free()
                if s != -1:
                    busy[s]=True; cls[s]=1; tarr[s]=clock
                    t_c[s] = clock + _srv(S_SRV1, Es1)
                else:
                    q1.append(clock)
            else:
                D1 += 1; phD1[cur] += 1
            t_a1 = clock + _arr(S_ARR1, lam1)

        elif et == 'A2':
            A2 += 1; phA2[cur] += 1
            if n1+n2 < K:
                n2 += 1; s = free()
                if s != -1:
                    busy[s]=True; cls[s]=2; tarr[s]=clock
                    t_c[s] = clock + _srv(S_SRV2, Es2)
                else:
                    q2.append(clock)
            else:
                D2 += 1; phD2[cur] += 1
            t_a2 = clock + _arr(S_ARR2, lam2)

        else:  # completamento servente s
            s = s_i; c = cls[s]
            resp = clock - tarr[s]
            if c == 1: C1 += 1; n1 -= 1; rR1 += resp
            else:      C2 += 1; n2 -= 1; rR2 += resp
            if q1:                                  # priorita' non-preemptive
                a = q1.popleft(); busy[s]=True; cls[s]=1; tarr[s]=a
                dD1 += clock - a; t_c[s] = clock + _srv(S_SRV1, Es1)
            elif q2:
                a = q2.popleft(); busy[s]=True; cls[s]=2; tarr[s]=a
                dD2 += clock - a; t_c[s] = clock + _srv(S_SRV2, Es2)
            else:
                busy[s]=False; cls[s]=0; t_c[s]=INF

    T = clock
    f = lambda a, b: a/b if b > 0 else 0.0
    per_phase = [{
        "lambda2": phases[i]["lambda2"], "dur": phT[i],
        "Ploss1": f(phD1[i], phA1[i]), "Ploss2": f(phD2[i], phA2[i]),
        "E_N": f(phN[i], phT[i]),
    } for i in range(P)]

    return {
        "E_Ts1": f(rR1, C1), "E_Ts2": f(rR2, C2),
        "E_Tq1": f(dD1, C1), "E_Tq2": f(dD2, C2),
        "E_N1": f(aN1, T), "E_N2": f(aN2, T),
        "X1": f(C1, T), "X2": f(C2, T), "U": f(aS, m*T),
        "Ploss1": f(D1, A1), "Ploss2": f(D2, A2),
        "A1": A1, "A2": A2, "C1": C1, "C2": C2, "D1": D1, "D2": D2,
        "in_end": n1+n2, "T": T, "phases": per_phase,
    }


# --- colori ANSI (output leggibile su Git Bash / terminale moderno) ---
G, R, Y, B, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[2m", "\033[0m"
def col(p):  # colora una percentuale di perdita: verde ok, giallo <10, rosso alto
    return (G if p < 0.01 else Y if p < 0.10 else R) + f"{p*100:5.1f}%" + RST


if __name__ == "__main__":
    from scenarios import scenario_nominal, scenario_attack

    PlantSeeds(123456789)
    rn = run_simulation(scenario_nominal())
    print(f"{B}NOMINALE{RST}  E[Ts]1={rn['E_Ts1']*1e3:.2f}ms  U={rn['U']:.2f}  perdita1={col(rn['Ploss1'])}")

    PlantSeeds(123456789)
    ra = run_simulation(scenario_attack())
    print(f"\n{B}ATTACCO a fasce{RST}   {DIM}(perdita = % richieste respinte){RST}")
    nomi = ["Normale", "Picco", "Mitigazione"]
    for i, ph in enumerate(ra["phases"]):
        print(f"  {nomi[i]:12s} lam2={ph['lambda2']:>7.0f}/s   "
              f"legittimo {col(ph['Ploss1'])}   attacco {col(ph['Ploss2'])}")
