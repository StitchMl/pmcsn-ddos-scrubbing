# Contromisura 1: corsia riservata (Fast-Track).
# Confronto BASE vs FAST-TRACK sullo scenario d'attacco, stesso seed (Common
# Random Numbers): le differenze dipendono solo dall'intervento, non dal caso.

from rngs import PlantSeeds
from simulator import run_simulation, col, B, RST, DIM
from scenarios import scenario_attack, K_BUFFER

SEED = 123456789
RESERVE = 300                          # slot riservati alla Classe 1 (K2 = K - RESERVE)


def _run(cfg):
    PlantSeeds(SEED)                   # stesso seme -> stessa sequenza (CRN)
    return run_simulation(cfg)


def _fastTrack():
    base = _run(scenario_attack())                         # K2 = K (nessuna riserva)
    ft = _run(scenario_attack(K2=K_BUFFER - RESERVE))      # Fast-Track

    print(f"{B}Contromisura 1 - Fast-Track{RST}  "
          f"{DIM}(riserva {RESERVE} slot su {K_BUFFER} alla Classe 1){RST}")
    print(f"{'fase':12s} {'perdita legittimo: BASE':>26s}   {'FAST-TRACK':>12s}")
    nomi = ["Normale", "Picco", "Mitigazione"]
    for i, nome in enumerate(nomi):
        pb = base["phases"][i]["Ploss1"]
        pf = ft["phases"][i]["Ploss1"]
        print(f"  {nome:10s} {col(pb):>34s}   {col(pf):>20s}")

    print(f"\n{DIM}Throughput attacco servito (Classe 2) - base X2={base['X2']:.0f}/s, "
          f"fast-track X2={ft['X2']:.0f}/s{RST}")


if __name__ == "__main__":
    _fastTrack()
