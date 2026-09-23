# Nodo di scrubbing DDoS (AISURU 2025) - simulatore next-event.
# REALISMO: il sistema vede UN solo flusso; ogni job porta uno score osservabile
# (legittimo ~ N(0,1), attacco ~ N(sep,1), distribuzioni sovrapposte) e viene
# flaggato "sospetto" se score > soglia. Le contromisure agiscono sul flag; le
# metriche misurano il traffico DAVVERO legittimo. PlantSeeds() dal chiamante.

import heapq
from collections import deque
from rngs import SelectStream
from rvgs import Exponential, Normal

S_ARR = [0, 0, 1]   # stream arrivi per classe vera (1,2)
S_SRV = [0, 2, 3]   # stream servizi per classe vera
S_CLF = 4           # stream del classificatore
INF = float("inf")


def _interarrival(stream, lam):
    if lam <= 0.0:
        return INF
    SelectStream(stream)
    return Exponential(1.0 / lam)


def _service(stream, mean):
    SelectStream(stream)
    return Exponential(mean)


def single_phase(lambda1, lambda2, duration):
    return [{"dur": duration, "lambda1": lambda1, "lambda2": lambda2}]


class Simulation:
    """Una run dello scenario cfg. Usare run_simulation(cfg) come scorciatoia."""

    def __init__(self, cfg):
        self.K = cfg["K"]
        self.Es = [0.0, cfg["Es1"], cfg["Es2"]]
        self.phases = cfg["phases"]
        self.P = len(self.phases)
        clf = cfg.get("clf", {"sep": 10.0, "theta": 5.0})
        self.sep, self.theta = clf["sep"], clf["theta"]
        pol = cfg.get("policy", {"name": "base"})
        self.name = pol["name"]
        self.K_susp = pol.get("K_susp", self.K)
        self.rl_rate = pol.get("rate", INF)
        self.rl_burst = pol.get("burst", 1.0)

        m0 = cfg["m"]
        if self.name == "autoscale":
            self.m_min, self.m_max = pol.get("m_min", m0), pol["m_max"]
            self.up, self.down, self.setup = pol["up"], pol["down"], pol.get("setup", 0.0)
            start = self.m_min
        else:
            self.m_min = self.m_max = m0
            self.up = self.down = self.setup = 0
            start = m0
        self.M = self.m_max
        self.active = [i < start for i in range(self.M)]
        self.n_active = start
        self.free = list(range(start))

        self.clock = 0.0
        self.n = [0, 0, 0]
        self.qG, self.qS = deque(), deque()
        self.scls = [0] * self.M
        self.sarr = [0.0] * self.M
        self.t_c = [INF] * self.M
        self.comp = []
        self.n_busy = 0
        self.tokens, self.last_ref = self.rl_burst, 0.0
        self.t_act = INF

        self.cur = 0
        self.lam = [0.0, self.phases[0]["lambda1"], self.phases[0]["lambda2"]]
        self.phase_end = self.phases[0]["dur"]
        self.t_a = [0.0, _interarrival(S_ARR[1], self.lam[1]),
                    _interarrival(S_ARR[2], self.lam[2])]

        P = self.P
        self.area_node = [0.0, 0.0, 0.0]
        self.sum_resp = [0.0, 0.0, 0.0]
        self.arr = [0, 0, 0]
        self.done = [0, 0, 0]
        self.drop = [0, 0, 0]
        self.ph_arr = [[0] * P, [0] * P, [0] * P]
        self.ph_drop = [[0] * P, [0] * P, [0] * P]
        self.ph_N = [0.0] * P
        self.ph_T = [0.0] * P
        self.area_srv = 0.0

    # --- classificatore: decide sul solo score osservabile ---
    def _suspect(self, k):
        SelectStream(S_CLF)
        return Normal(0.0 if k == 1 else self.sep, 1.0) > self.theta

    # --- serventi / code ---
    def _start(self, s, k, ts):
        self.scls[s] = k
        self.sarr[s] = ts
        tc = self.clock + _service(S_SRV[k], self.Es[k])
        self.t_c[s] = tc
        heapq.heappush(self.comp, (tc, s))
        self.n_busy += 1

    def _place(self, k, lane_s):
        self.n[k] += 1
        if self.free:
            self._start(self.free.pop(), k, self.clock)
        else:
            (self.qS if lane_s else self.qG).append((self.clock, k))

    def _admit(self, k, susp):
        ntot = self.n[1] + self.n[2]
        if self.name == "fasttrack":
            if ntot >= (self.K_susp if susp else self.K):
                return False
            self._place(k, susp)
            return True
        if self.name == "ratelimit" and susp:
            self.tokens = min(self.rl_burst,
                              self.tokens + self.rl_rate * (self.clock - self.last_ref))
            self.last_ref = self.clock
            if self.tokens < 1.0 or ntot >= self.K:
                return False
            self.tokens -= 1.0
            self._place(k, False)
            return True
        if ntot >= self.K:
            return False
        self._place(k, False)
        return True

    # --- gestori di evento ---
    def _on_arrival(self, k):
        self.arr[k] += 1
        self.ph_arr[k][self.cur] += 1
        if not self._admit(k, self._suspect(k)):
            self.drop[k] += 1
            self.ph_drop[k][self.cur] += 1
        elif (self.name == "autoscale" and (self.n[1] + self.n[2]) >= self.up
              and self.n_active < self.m_max and self.t_act == INF):
            self.t_act = self.clock + self.setup
        self.t_a[k] = self.clock + _interarrival(S_ARR[k], self.lam[k])

    def _on_completion(self, s):
        k = self.scls[s]
        self.done[k] += 1
        self.n[k] -= 1
        self.sum_resp[k] += self.clock - self.sarr[s]
        self.n_busy -= 1
        self.t_c[s] = INF
        if self.qG or self.qS:
            ts, kk = (self.qG if self.qG else self.qS).popleft()
            self._start(s, kk, ts)
        elif (self.name == "autoscale" and (self.n[1] + self.n[2]) <= self.down
              and self.n_active > self.m_min):
            self.active[s] = False
            self.n_active -= 1
        else:
            self.free.append(s)

    def _on_activation(self):
        self.t_act = INF
        for s in range(self.M):
            if not self.active[s]:
                self.active[s] = True
                self.n_active += 1
                if self.qG or self.qS:
                    ts, kk = (self.qG if self.qG else self.qS).popleft()
                    self._start(s, kk, ts)
                else:
                    self.free.append(s)
                return

    def _advance_phase(self):
        self.cur += 1
        if self.cur >= self.P:
            return False
        self.lam[1] = self.phases[self.cur]["lambda1"]
        self.lam[2] = self.phases[self.cur]["lambda2"]
        self.phase_end += self.phases[self.cur]["dur"]
        self.t_a[1] = self.clock + _interarrival(S_ARR[1], self.lam[1])
        self.t_a[2] = self.clock + _interarrival(S_ARR[2], self.lam[2])
        return True

    def _next_completion(self):
        comp = self.comp
        while comp and comp[0][0] != self.t_c[comp[0][1]]:
            heapq.heappop(comp)                 # scarta entry obsolete (lazy heap)
        return comp[0] if comp else (INF, -1)

    def _select_event(self):
        tc, cs = self._next_completion()
        tmin, etype, idx = self.phase_end, "PH", -1
        if self.t_a[1] < tmin:
            tmin, etype, idx = self.t_a[1], "A", 1
        if self.t_a[2] < tmin:
            tmin, etype, idx = self.t_a[2], "A", 2
        if self.t_act < tmin:
            tmin, etype, idx = self.t_act, "ACT", -1
        if tc < tmin:
            tmin, etype, idx = tc, "C", cs
        return tmin, etype, idx

    def _accumulate(self, tmin):
        dt = tmin - self.clock
        self.area_node[1] += dt * self.n[1]
        self.area_node[2] += dt * self.n[2]
        self.area_srv += dt * self.n_busy
        self.ph_N[self.cur] += dt * (self.n[1] + self.n[2])
        self.ph_T[self.cur] += dt

    def run(self):
        while True:
            tmin, etype, idx = self._select_event()
            self._accumulate(tmin)
            self.clock = tmin
            if etype == "PH":
                if not self._advance_phase():
                    break
            elif etype == "A":
                self._on_arrival(idx)
            elif etype == "ACT":
                self._on_activation()
            else:
                self._on_completion(idx)
        return self._metrics()

    def _metrics(self):
        T = self.clock

        def rate(a, b):
            return a / b if b > 0 else 0.0

        per_phase = [{
            "lambda2": self.phases[i]["lambda2"], "dur": self.ph_T[i],
            "Ploss1": rate(self.ph_drop[1][i], self.ph_arr[1][i]),
            "Ploss2": rate(self.ph_drop[2][i], self.ph_arr[2][i]),
            "E_N": rate(self.ph_N[i], self.ph_T[i]),
        } for i in range(self.P)]

        return {
            "E_Ts1": rate(self.sum_resp[1], self.done[1]),
            "E_Ts2": rate(self.sum_resp[2], self.done[2]),
            "E_N1": rate(self.area_node[1], T), "E_N2": rate(self.area_node[2], T),
            "X1": rate(self.done[1], T), "X2": rate(self.done[2], T),
            "U": rate(self.area_srv, self.m_max * T),
            "Ploss1": rate(self.drop[1], self.arr[1]),
            "Ploss2": rate(self.drop[2], self.arr[2]),
            "T": T, "phases": per_phase,
        }


def run_simulation(cfg):
    return Simulation(cfg).run()


# colori ANSI
G, R, Y, B, DIM, RST = "\033[32m", "\033[31m", "\033[33m", "\033[34m", "\033[2m", "\033[0m"


def col(p):
    color = G if p < 0.01 else Y if p < 0.10 else R
    return f"{color}{p * 100:5.1f}%{RST}"


if __name__ == "__main__":
    from main import main
    main()
