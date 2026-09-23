# Entry-point unico: esegue in ordine tutte le simulazioni e stampa i risultati
# in modo ordinato, minimal e leggibile.  Uso:  python src/main.py
#   1) regime nominale      2) attacco BASE (per fascia)
#   3) confronto contromisure (statistico: IC 95% + Common Random Numbers)

from rngs import PlantSeeds
from simulator import run_simulation, col, B, DIM, RST
from scenarios import scenario_nominal, scenario_attack
import experiments

SEED = 123456789
PHASE = ["Normale", "Picco", "Mitigazione"]


def _head(n, title):
    print(f"\n{B}[{n}] {title}{RST}")


def sec_nominal():
    _head(1, "Regime nominale (solo traffico di fondo)")
    PlantSeeds(SEED)
    r = run_simulation(scenario_nominal())
    print(f"  E[Ts] legittimo   {r['E_Ts1'] * 1e3:6.2f} ms")
    print(f"  Utilizzo serventi {r['U']:6.2f}")
    print(f"  Perdita legittimo {col(r['Ploss1'])}")


def sec_attack():
    _head(2, "Attacco a fasce - policy BASE (class-blind)")
    PlantSeeds(SEED)
    r = run_simulation(scenario_attack())
    print(f"  {'fase':12s} {'lambda2':>9s}  {'perd.legit':>10s}  "
          f"{'perd.attacco':>12s}  {'E[N]':>6s}")
    for i, ph in enumerate(r["phases"]):
        print(f"  {PHASE[i]:12s} {ph['lambda2']:9.0f}  {col(ph['Ploss1']):>10s}  "
              f"{col(ph['Ploss2']):>12s}  {ph['E_N']:6.0f}")


def sec_countermeasures():
    _head(3, "Contromisure - confronto statistico (IC 95%, CRN)")
    experiments.main(reps=8, dur_scale=0.15)     # tour rapido
    print(f"  {DIM}numeri report-grade (30 repliche): python src/experiments.py{RST}")


def main():
    print(f"{B}=== Simulazione nodo di scrubbing DDoS (AISURU 2025) ==={RST}")
    print(f"{DIM}Nodo rappresentativo a scala ridotta - vedi src/scenarios.py{RST}")
    sec_nominal()
    sec_attack()
    sec_countermeasures()
    print(f"\n{DIM}Fine. Dettaglio e commento in docs/risultati.md{RST}")


if __name__ == "__main__":
    main()
