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

## Realismo: il sistema NON conosce la vera classe
Un difensore reale non sa a priori quale richiesta è lecita. Nel modello un
**classificatore imperfetto** etichetta ogni richiesta come *sospetta* o no, con
**tasso di rilevamento d = 0,90** e **falsi positivi f = 0,05**. Le contromisure
agiscono sull'**etichetta**, mentre le metriche misurano il traffico **davvero**
legittimo. Con classificatore perfetto (d=1, f=0) il Fast-Track azzererebbe la
perdita; con quello realistico no — ed è questo che rende la simulazione utile.

## Confronto statistico delle contromisure (rigoroso)
Perdita del legittimo **al picco**, media ± IC 95% su **repliche indipendenti**,
confronto accoppiato con **Common Random Numbers** (stesso seme per tutte le
policy in ogni replica). Scenario d'attacco, classificatore d=0,90 / f=0,05.

| Policy | Perdita legittimo al picco | Differenza vs BASE (IC 95%) |
|---|---:|---:|
| BASE (nessuna) | 87,2 % ± 0,1 | — |
| **FAST-TRACK** (corsia riservata) | **22,3 % ± 0,3** | **−64,9 ± 0,2** ✓ significativo |
| AUTOSCALING (m→16) | 59,9 % ± 0,1 | −27,3 ± 0,1 ✓ significativo |
| RATE-LIMIT (sospetti) | 78,7 % ± 0,2 | −8,5 ± 0,2 ✓ significativo |

**Esito:** tutte le contromisure migliorano in modo statisticamente significativo
(IC della differenza interamente < 0). La **corsia riservata (①)** è di gran lunga
la più efficace; l'**autoscaling (②)** aiuta ma non basta da solo (la capacità
resta sotto il picco); il **rate-limit (③)** è debole perché l'attacco *non rilevato*
(10%) passa comunque. Riproducibile con `python src/experiments.py`
(confronto rapido a singola run: `python src/compare_fasttrack.py`).

