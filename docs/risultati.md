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

## Contromisura ① — Corsia riservata / Fast-Track
Ammissione *priority-aware*: l'attacco (Classe 2) è ammesso solo fino a **K₂ = 1700**,
riservando **300 slot su 2000** alla Classe 1. Confronto base vs Fast-Track a parità
di seed (Common Random Numbers), scenario d'attacco.

| Fase | Perdita legittimo — BASE | Perdita legittimo — FAST-TRACK |
|---|---:|---:|
| Normale     | 0 %      | 0 % |
| **Picco**   | **87,5 %** | **0 %** |
| Mitigazione | 49,9 %   | 0 % |

**Esito:** riservare appena il 15 % del buffer azzera la perdita del traffico
legittimo durante l'attacco, a costo di servire un po' meno traffico d'attacco
(che è l'effetto desiderato). Riproducibile con `python src/compare_fasttrack.py`.

