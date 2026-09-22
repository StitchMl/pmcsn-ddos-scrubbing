# Risultati delle simulazioni

> Modello **base**, singola run dimostrativa (seed = 123456789). I valori con
> intervallo di confidenza arriveranno con `experiments.py` (repliche/batch means).
> Parametri (nodo rappresentativo, da `src/scenarios.py`): m=4, K=2000,
> E(S)=0,5 ms (μ_core=2000 rps), λ₁=4000 rps.

## Regime nominale (solo traffico di fondo)
| Metrica | Valore |
|---|---|
| E[Ts] legittimo | 0,58 ms |
| Utilizzo serventi U | 0,62 |
| Perdita legittimo | 0 % |

## Attacco a fasce (Normale 30 s → Picco 60 s → Mitigazione 30 s)
| Fase | λ₂ (rps) | Perdita legittimo | Perdita attacco | E[N] nel nodo |
|---|---:|---:|---:|---:|
| Normale     | 1.000  | 0 %    | 0 %    | ~3      |
| **Picco**   | 60.000 | **~88 %** | ~88 % | ~2000 (= K, saturo) |
| Mitigazione | 12.000 | ~50 %  | ~50 %  | ~2000   |

## Lettura
Durante il **picco** il buffer unico satura: la perdita colpisce **anche il traffico
legittimo (~88 %)** nonostante la priorità in servizio. Causa: lo scarto *drop-tail*
all'ingresso **non è priority-aware**. È il difetto su cui agiscono le contromisure
(schema `schema-sistema.png`, pannello B): ① corsia riservata/Fast-Track per il
legittimo, ② autoscaling dei serventi al picco, ③ rate-limit sull'attacco.
