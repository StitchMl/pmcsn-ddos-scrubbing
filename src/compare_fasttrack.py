# Confronto rapido BASE vs FAST-TRACK (singola run, classificatore realistico).
# Per il confronto rigoroso con intervalli di confidenza usare experiments.py.

from rngs import PlantSeeds
from simulator import run_simulation, col, B, RST, DIM
from scenarios import scenario_attack, with_policy, pol_base, pol_fasttrack

SEED = 123456789


def _run(cfg):
    PlantSeeds(SEED)                   # stesso seme -> CRN
    return run_simulation(cfg)


def _fastTrack():
    atk = scenario_attack()
    base = _run(with_policy(atk, pol_base()))
    ft = _run(with_policy(atk, pol_fasttrack(reserve=300)))
    print(f"{B}BASE vs FAST-TRACK{RST}  {DIM}(perdita legittimo per fascia){RST}")
    nomi = ["Normale", "Picco", "Mitigazione"]
    for i, nome in enumerate(nomi):
        pb = base["phases"][i]["Ploss1"]
        pf = ft["phases"][i]["Ploss1"]
        print(f"  {nome:12s} base {col(pb)}   fast-track {col(pf)}")


if __name__ == "__main__":
    _fastTrack()
