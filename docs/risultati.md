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

## Realismo: il sistema vede un unico flusso e deve *accorgersi* del traffico
Un difensore reale non sa a priori quale richiesta è lecita: vede **un solo
flusso** e deve dedurlo da ciò che **osserva**. Nel modello ogni job porta uno
**score osservabile** (una feature comportamentale: tasso della sorgente,
impronta della richiesta, ecc.). Le distribuzioni dello score **si sovrappongono**:
legittimo ~ N(0,1), attacco ~ N(SEP,1). Il sistema vede **solo lo score** e flagga
"sospetto" se supera una **soglia θ**. Rilevamento **d** e falsi positivi **f**
**emergono** da questa sovrapposizione (curva ROC): con SEP=3 e θ=1,645 si ha
d≈0,91 e f≈0,05. Abbassando θ si rileva più attacco ma si penalizza più
legittimo — il classico compromesso. Le contromisure agiscono sul **flag**, mentre
le metriche misurano il traffico **davvero** legittimo.

## Confronto statistico delle contromisure (rigoroso)
Perdita del legittimo **al picco**, media ± IC 95% su **repliche indipendenti**,
confronto accoppiato con **Common Random Numbers**. Detector: score + soglia
(d≈0,91, f≈0,05).

| Policy | Perdita legittimo al picco | Differenza vs BASE (IC 95%) |
|---|---:|---:|
| BASE (nessuna) | 87,2 % ± 0,1 | — |
| **FAST-TRACK** (corsia riservata) | **15,8 % ± 0,3** | **−71,4 ± 0,4** ✓ significativo |
| AUTOSCALING (m→16) | 59,9 % ± 0,2 | −27,3 ± 0,2 ✓ significativo |
| RATE-LIMIT (sospetti) | 77,1 % ± 0,3 | −10,2 ± 0,3 ✓ significativo |

**Esito:** tutte migliorano in modo statisticamente significativo (IC della
differenza interamente < 0). La **corsia riservata (①)** è la più efficace;
l'**autoscaling (②)** aiuta ma non basta (capacità sotto il picco); il
**rate-limit (③)** è debole perché l'attacco *non rilevato* passa nella corsia
buona. La qualità del detector (SEP) e il punto di lavoro (θ) si regolano in
`scenarios.py`. Riproducibile con `python src/experiments.py` (rapido a singola
run: `python src/compare_fasttrack.py`).

