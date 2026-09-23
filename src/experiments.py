# Confronto statistico delle contromisure sullo scenario d'attacco.
# Repliche indipendenti + intervalli di confidenza al 95% (t di Student).
# Common Random Numbers: in ogni replica tutte le policy usano lo STESSO seme
# (differenze accoppiate). Metrica: perdita del traffico DAVVERO legittimo al picco.

from math import sqrt, erf
from rngs import PlantSeeds
from simulator import run_simulation, B, DIM, RST, G, Y
from scenarios import (scenario_attack, with_policy,
                       pol_base, pol_fasttrack, pol_ratelimit, pol_autoscale)

REPS = 30            # numero di repliche indipendenti
DUR_SCALE = 0.25     # accorcia le fasce per run piu' rapide (aumentalo per il report)
SEED0 = 123456789
STRIDE = 40007603    # per generare semi distinti e ben separati

POLICIES = [
    ("BASE (nessuna)", pol_base()),
    ("FAST-TRACK", pol_fasttrack(reserve=300)),
    ("RATE-LIMIT", pol_ratelimit(rate=6000.0, burst=200.0)),
    ("AUTOSCALING", pol_autoscale(m_max=16, up=200, down=20, setup=0.5)),
]


def _phi(x):
    """CDF della normale standard."""
    return 0.5 * (1 + erf(x / sqrt(2)))


def idf_student(df):
    """Quantile t di Student al 97,5% (approssimazione di Cornish-Fisher)."""
    z = 1.959963985
    return (z + (z**3 + z) / (4 * df)
            + (5 * z**5 + 16 * z**3 + 3 * z) / (96 * df**2))


def ci95(xs):
    """Media e semi-ampiezza dell'IC al 95% di un campione."""
    n = len(xs)
    mean = sum(xs) / n
    var = sum((x - mean) ** 2 for x in xs) / (n - 1)
    hw = idf_student(n - 1) * sqrt(var / n)
    return mean, hw


def peak_loss(cfg):
    """Perdita del legittimo (%) nella fascia di picco = fase 1."""
    return run_simulation(cfg)["phases"][1]["Ploss1"] * 100.0


def main():
    seeds = [(SEED0 + r * STRIDE) % 2147483647 for r in range(REPS)]
    base_cfg = scenario_attack(dur_scale=DUR_SCALE)

    # raccolta: per ogni policy la lista dei valori sulle repliche (CRN)
    samples = {name: [] for name, _ in POLICIES}
    for r in range(REPS):
        for name, pol in POLICIES:
            PlantSeeds(seeds[r])               # stesso seme -> CRN tra le policy
            samples[name].append(peak_loss(with_policy(base_cfg, pol)))

    base = samples["BASE (nessuna)"]
    mb, hb = ci95(base)

    print(f"{B}Perdita del legittimo al PICCO  (media +/- IC 95%, {REPS} repliche){RST}")
    print(f"{'policy':16s} {'perdita legittimo':>20s}   {'differenza vs BASE (IC95)':>30s}")
    for name, _ in POLICIES:
        m, h = ci95(samples[name])
        if name.startswith("BASE"):
            print(f"  {name:16s} {m:8.2f} +/- {h:4.2f} %")
            continue
        diff = [samples[name][r] - base[r] for r in range(REPS)]   # differenza accoppiata
        md, hd = ci95(diff)
        sig = (md + hd) < 0                     # IC interamente < 0 -> miglioramento certo
        mark = f"{G}significativo{RST}" if sig else f"{Y}non concl.{RST}"
        print(f"  {name:16s} {m:8.2f} +/- {h:4.2f} %   "
              f"{md:8.2f} +/- {hd:4.2f} %  {mark}")

    sep, th = base_cfg["clf"]["sep"], base_cfg["clf"]["theta"]
    d_eff, f_eff = 1 - _phi(th - sep), 1 - _phi(th)    # d,f emergono da score+soglia
    print(f"\n{DIM}BASE = class-blind. Le altre decidono su uno SCORE osservabile "
          f"(soglia): rilevamento d~={d_eff:.2f}, falsi positivi f~={f_eff:.2f}.{RST}")


if __name__ == "__main__":
    main()
