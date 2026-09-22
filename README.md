# Registro di progetto — PMCSN

**Corso:** Performance Modeling of Computer Systems and Networks (Prof.ssa V. de Nitto Personè)
**Studente:** Matteo Lagioia
**Titolo di lavoro:** Dimensionamento di un nodo di scrubbing DDoS di un PoP CDN sotto attacco della botnet AISURU (2025)
**Ultimo aggiornamento:** 2026-09-22

> Registro vivo: annota ogni parametro, fonte/articolo e decisione presa, con la data. Aggiornato a ogni passo del progetto.
> Repo GitHub: **pmcsn-ddos-scrubbing** (pubblica). Questo README è il registro ufficiale del progetto.

---

## 0. Stato di avanzamento (9 step della Guida)

| Step | Descrizione | Stato |
|---|---|---|
| 1 | Scelta del sistema + obiettivi | ✅ deciso, sezione redatta |
| 2 | Modello concettuale & specifiche | ✅ deciso (stato, eventi, distrib., scheduling); sezione da finalizzare |
| 3 | Simulatore Next-Event (Python) | ✅ impostazione decisa; **implementazione da fare** |
| 4 | Verifica & validazione | ✅ impostazione decisa (baseline analitici + criterio CI) |
| 5 | Analisi del transitorio (obbligatoria) | ✅ impostazione decisa (Welch + finestre a fasce) |
| 6 | Disegno esperimenti / orizzonte | ✅ impostazione decisa (repliche + batch means + CRN) |
| 7 | Analisi output & decisione | ✅ impostazione decisa (criteri m*, λ₂*, confronto CRN) |
| 8 | Modello migliorativo (obbligatorio in gruppo) | ✅ impostazione decisa (candidato: autoscaling) |
| 9 | Relazione + presentazione orale | ⬜ da fare |

---

## 1. Sintesi del caso reale

Botnet **AISURU** (variante Mirai/TurboMirai), 2025. Recluta dispositivi IoT sfruttando vulnerabilità note e zero-day; con 1–4 milioni di dispositivi ha generato i DDoS più grandi mai registrati. Il progetto modella l'infrastruttura di **mitigazione/scrubbing** di un PoP CDN come sistema a coda, per dimensionarla in modo che il traffico legittimo rispetti la QoS durante l'attacco.

### Vulnerabilità sfruttate (angolo cyber)
| CVE / vettore | Dispositivo | Note |
|---|---|---|
| CVE-2017-5259 | Cambium Networks | N-day |
| CVE-2023-28771 | Zyxel | N-day |
| CVE-2023-50381 | Realtek Jungle SDK | N-day |
| Zero-day cnPilot | Cambium cnPilot routers | osservato da giugno 2024 |
| Supply-chain | server aggiornamento firmware Totolink | aprile 2025, script malevolo |

### Numeri reali dell'attacco (da confermare/citare in relazione)
- Picchi volumetrici: **22,2 → 29,7 → 31,4 Tbps**
- Picco pacchetti: **14,1 miliardi pps** (Bpps)
- Picco HTTP: **205 milioni rps** (Mrps)
- Durata attacchi lampo: **35–69 s**
- Dispositivi infetti: **1–4 milioni** (router, DVR, Android TV); ~300.000 router iniziali
- Cloudflare: **47,1 milioni** di attacchi mitigati nel 2025 (autonomamente)

---

## 1-bis. Requisiti ufficiali del progetto (dalla Guida PMCSN)

Struttura in 9 step basata sull'Algoritmo di sviluppo del modello (Leemis & Park):
- **Step 0** — Individuale o gruppo ≤ 3. I **gruppi devono** progettare anche un **modello migliorativo** (Step 8). Deliverable: relazione (PDF), **codice sorgente del simulatore**, presentazione orale (10 min/componente in gruppo, 20 min individuale).
- **Step 1** — Scelta caso + **Obiettivi**: Capacity Planning, Bottleneck Identification, System Tuning, SLA/QoS Compliance. Metriche: R/E(T_S), E(T_Q), N/E(N), U, **percentili** sui tempi.
- **Step 2** — **Modello Concettuale e delle Specifiche**: definizione **stato S(t)**; topologia e componenti (centri, capacità code finita/infinita, single/multi/infinite server, matrice di routing); **eventi** (arrivi esterni, completamenti, eventi artificiali); **caratterizzazione del carico** (processi + classi); **distribuzioni** (Esponenziale, Bounded Pareto, Iperesponenziale, Uniforme, o trace-driven); **scheduling** (FIFO, Priorità astratta/Size-Based, PS, preemptive/non-preemptive).
- **Step 3** — **Simulatore a eventi discreti (Next-Event)** in linguaggio general-purpose (C/C++/Java/Python): clock, event list, accumulatori statistici (sum.area, sum.service, departures), **PRNG a stream indipendenti**, gestione seed (plantseed/putseed fuori dal ciclo repliche).
- **Step 4** — **Verifica & Validazione**: punto di controllo su versione semplificata (M/M/1 o MVA) confrontata con soluzioni analitiche; consistency checks (più serventi → meno coda; λ↑ → R↑ monotono).
- **Step 5** — **Analisi del transitorio (obbligatoria)**: dallo stato iniziale (vuoto), 4–5 repliche indipendenti (seed diversi), media cumulativa, individuazione grafica del **warm-up**.
- **Step 6** — **Orizzonte**: finito (64–96 repliche indip.) oppure infinito/steady-state (**batch means**, K≥32/64 batch di dimensione B). **Intervalli di confidenza 95%** (t di Student, α=0,05) per medie e percentili.
- **Step 7** — Esecuzione run, analisi output (grafici + tabelle con IC), **fase decisionale** rispetto agli obiettivi.
- **Step 8** — **Modello migliorativo** (obbligatorio per gruppi): autoscaling dinamico, servizi Fast-Track, routing intelligente, code di priorità aggiuntive; confronto sistematico base vs migliorativo (variazione % degli indici).
- **Step 9** — Relazione (struttura = passi dell'algoritmo) + orale sintetico.

> ⚠️ **Implicazione chiave:** il cuore del progetto è un **simulatore**, non solo formule. Gli strumenti analitici (M/M/1, Erlang, ecc.) servono soprattutto come **benchmark di validazione** (Step 4). Il caso DDoS/AISURU è coerente: transitorio rilevante (attacchi 35–69 s), multi-classe, priorità, buffer finito.

---

## 2. Parametri del modello (baseline provvisoria — SINTETICA, da validare)

> ⚠️ Valori scelti per avere numeri comodi e stabilità per m ≥ 4. Sono **sintetici**: da giustificare combinando report pubblici 2025 + benchmark di letteratura (non tracce reali del PoP).

| Simbolo | Significato | Valore baseline | Fonte/nota |
|---|---|---|---|
| E(S) | tempo medio di ispezione per richiesta | 0,1 ms | assunto (ispezione L7) |
| μ | capacità di un core | 10.000 req/s | = 1/E(S) |
| λ_L | frequenza traffico legittimo | 6.000 req/s | assunto (ρ=0,6 a 1 core in condizioni normali) |
| λ_A | frequenza traffico d'attacco | 24.000 req/s | assunto (4× il legittimo) |
| λ = λ_L+λ_A | carico totale sotto attacco | 30.000 req/s | → ρ = 3/m, stabile per m ≥ 4 |
| m | n. core/serventi scrubbing | ≥ 4 (da dimensionare) | incognita di progetto |
| K | capacità buffer (finita) | da definire | per calcolo P_loss |
| p1, p2 | frazione arrivi classe legittima/sospetta | 0,2 / 0,8 | = λ_L/λ, λ_A/λ |

### Requisiti QoS (target di progetto — provvisori)
- Tempo di risposta medio complessivo sotto attacco: **E(T_S) ≤ 0,5 ms**
- Tempo di risposta medio traffico legittimo (con priorità): **E(T_S,legittimo) ≤ 0,3 ms**
- Perdita traffico legittimo: **≤ 1%**

---

## 3. Decisioni di modellazione (log)

| Data | Decisione | Motivazione | Stato |
|---|---|---|---|
| 2026-09-22 | Caso scelto: scrubbing DDoS / AISURU | Recente, reale, cyber/vulnerabilità; mappa su code, Erlang, perdita, scheduling | confermata |
| 2026-09-22 | Workload multi-classe: legittimo vs attacco | Serve per scheduling a priorità e per P_loss del legittimo | confermata |
| 2026-09-22 | Nodo scrubbing = risorsa critica (bottleneck) | Astrazione: si isola il collo di bottiglia, non tutto il PoP | confermata |
| 2026-09-22 | Arrivi Poisson (legittimo); attacco heavy-load/eventualmente NHPP in ramp-up | Sovrapposizione molti utenti indip. → Poisson (Palm-Khinchin) | da validare |
| 2026-09-22 | Buffer finito M/M/m/K per gestire ρ≥1 e calcolare P_loss | Senza loss il sistema aperto diverge sotto attacco | confermata |
| 2026-09-22 | Valutare ANCHE il transitorio (attacchi 35–69 s) | L'attacco è impulsivo/non stazionario: steady-state da solo sottostima i ritardi iniziali | da approfondire |
| 2026-09-22 | **Gruppo di 2 persone** | → **modello migliorativo (Step 8) obbligatorio**; comunicare i componenti al docente via e-mail prima dell'inizio | confermata |
| 2026-09-22 | **Linguaggio simulatore: Python** | Scelta per lo Step 3 (Next-Event); attenzione a PRNG con stream indipendenti e gestione seed (plantseed/putseed) | confermata |
| 2026-09-22 | **VINCOLO: usare solo distribuzioni/discipline/metodi visti a lezione** | Evitare tecniche non trattate nel corso (rischio all'esame/relazione) | confermata |

### Step 2 — Modello concettuale e delle specifiche (decisioni)
| Elemento | Scelta | Nota / da verificare |
|---|---|---|
| Stato analitico S(t) | vettore popolazione (n₁,n₂), 0≤n₁+n₂≤K | catena di Markov multi-classe |
| Stato simulatore | l₁,l₂, servers[m] (idle/busy+classe), code per classe Q₁,Q₂ | + timestamp arrivo/servizio |
| Topologia | 1 centro **multi-server m**, buffer **finito K**, sistema aperto | opzione a 2 stadi (ingress→scrubbing) solo se serve |
| Eventi | arrivo cl.1, arrivo cl.2, completamento servente s; artificiali: cambio fase, campionamento, stop | |
| Carico cl.1 (legittimo) | Poisson omogeneo λ₁ | Palm–Khinchin |
| Carico cl.2 (attacco) | Poisson a **carico costante elevato**; picco via **evento artificiale** che cambia λ₂ | ⚠️ **NHPP: verificare se fatto a lezione; se no, NON usarlo** → usare fasce/evento artificiale |
| Interarrivi | **Esponenziale** | visto a lezione ✓ |
| Tempi di servizio | **Esponenziale** (modello analitico/validazione) + variante ad alta variabilità **Iperesponenziale H₂** | H₂ ✓ nel corso. ⚠️ **Bounded Pareto: verificare se trattata; se no, usare H₂ (o Erlang) al suo posto** |
| Scheduling | **FIFO**, **priorità astratta NP/P**, **size-based**, **PS** (per confronto slowdown) | tutti ✓ nel corso (cfr. formulario). SRPT solo se richiesto |
| Criticità chiave | priorità multi-classe + buffer finito ⇒ **niente forma prodotto** ⇒ simulatore obbligatorio; transitorio obbligatorio | |

### Step 3 — Modello computazionale / simulatore (decisioni)
| Elemento | Scelta | Nota |
|---|---|---|
| Paradigma | **Next-Event** (event-scheduling), Python nativo | fedele a `ssq3`/`msq` di Leemis & Park; **no SimPy/librerie di simulazione** |
| Libreria PRNG | **`rngs.py` / `rvgs.py`** di Leemis & Park | multi-stream Lehmer |
| Stream (SelectStream) | 0=arrivi cl.1, 1=arrivi cl.2, 2=servizio cl.1, 3=servizio cl.2, 4=eventi artificiali | stream separati e disgiunti |
| Seed | **`PlantSeeds()` UNA volta, FUORI dal ciclo repliche** | run i.i.d., no correlazione (Kurkowski) |
| Event list | ARR1, ARR2, m completamenti (uno per servente), evento fase, STOP; idle ⇒ `t=INFINITY` | |
| Stato | `number_c1,number_c2`, `servers[m]` (busy+classe), `queue_c1`,`queue_c2` (timestamp arrivo) | |
| Scheduling nel sim. | **priorità astratta non-preemptive** (coda 1 prima della coda 2) | coerente con Step 2 |
| Accumulatori | `area.node/queue/service` (integrali d'area, aggiornati PRIMA di cambiare stato), `sum.delay`, `sum.service`, conteggi arrivi/completamenti/**dropped** per classe | metriche via leggi operazionali |
| Metriche | E(N_c)=area.node/T, E(N_Q,c)=area.queue/T, E(T_Q,c)=sum.delay/C_c, E(T_S,c)=E(T_Q,c)+E(S_c), U=area.service/(m·T), X_c=C_c/T, P_loss,c=dropped/arrivi | |
| Picco d'attacco | **evento artificiale a fasce** (Normale→Picco→Mitigazione) che cambia λ₂ | invece di NHPP ✓ |
| Variabilità servizio | **Esponenziale** nel base; **H₂/Erlang** come variante ad alta variabilità | Bounded Pareto evitata ✓ |
| Predisposizione Step 4 | riducibile a **M/M/1** (λ₂=0, m=1, K=∞) e **M/M/m/K** (λ₂=0) per confronto analitico | |
| Predisposizione Step 5 | registrare **media cumulativa** N̄(t) a intervalli per il warm-up | |

> ⚠️ Note tecniche da tenere presenti in fase di implementazione: (a) lo pseudocodice Python della risposta ha refusi da correggere (indici `event_list[0]/[1]`, `[0]*SERVERS`, `event_type.split('_')[1]`); (b) `sum.service` va accumulato per **tutti** i job serviti (anche quelli presi in servizio all'arrivo, non solo dalla coda), altrimenti E(T_S) è sottostimato; (c) i valori `SERVERS=8, K=50, STOP=14400` nello sketch sono **placeholder** da fissare; (d) i nomi di slide/capitoli citati vanno verificati sui materiali reali. **Consiglio:** tenere il **servizio esponenziale nel modello base** (così l'M/M/m/K è verificabile analiticamente) e usare H₂ solo come variante/what-if.

### Step 4 — Verifica & Validazione (decisioni)
| Aspetto | Contenuto |
|---|---|
| Verifica codice | bilancio flussi (arrivi = completamenti + scarti + residui nel nodo) per classe e totale; `PlantSeeds` una volta fuori dal ciclo; accumulatori d'area aggiornati PRIMA del cambio di stato; identità W=D+S e l̄=q̄+x̄; Legge di Little con λ_eff=λ(1−P_loss) |
| Baseline analitici (λ₂=0) | **M/M/1**: U=ρ, E(N)=ρ/(1−ρ), E(N_Q)=ρ²/(1−ρ), E(T_S)=1/(μ−λ), E(T_Q)=ρ/(μ−λ) · **M/M/m** (Erlang-C): π₀, P_Q, E(T_Q)=P_Q/(mμ(1−ρ)) · **M/M/m/K** (nascita-morte, PASTA): P_loss=π_K, X=λ(1−P_loss), U=λ(1−P_loss)/(mμ); per K=m ⇒ **Erlang-B** |
| Criterio statistico | il valore teorico deve cadere nell'**IC 95%** della stima simulata; t*→1.96 per n grande; n≥~30–40 repliche (≈385 se si vuole semiampiezza = 10% di s) |
| Consistency checks (validazione) | monotonìa: m↑ ⇒ E(N),D,P_loss↓; λ↑ ⇒ W,U,P_loss↑; saturazione λ≫mμ ⇒ P_loss→1−mμ/λ; grafici W vs λ, P_loss vs K, E(N) vs m |
| Ramo multi-classe/priorità | non ha forma prodotto: validare prima il motore in mono-classe (λ₂=0 vs M/M/m/K), poi verificare che E(T_Q,1)<E(T_Q,2) e la conservazione del lavoro |

### Step 5 — Analisi del transitorio (decisioni)
| Aspetto | Contenuto |
|---|---|
| Problema | **initial condition bias**: partenza da sistema vuoto (N(0)=0) sottostima code/attese iniziali |
| Procedura | R=4–5 repliche indipendenti (seed via `PlantSeeds` fuori dal ciclo) sovrapposte; media cumulativa **N̄(t)=area.node(t)/t** e W̄(n)=Σwᵢ/n |
| Warm-up | **metodo di Welch**: media di ensemble tra repliche + media mobile ⇒ individuare t_warm dove la curva si appiattisce |
| Uso del warm-up | per lo **steady-state** (dimensionamento nominale) si **scarta [0, t_warm]** e si azzerano gli accumulatori a t_warm |
| Scenario attacco | l'attacco a fasce (Normale→Picco→Mitigazione) NON ammette steady-state ⇒ **orizzonte finito (terminating)**, inizializzando lo stato al regime pre-attacco; **il transitorio dell'attacco NON si tronca** (è l'oggetto di studio) |
| Grafici report | N̄(t) multi-replica; curva Welch con cutoff t_warm; profilo temporale N̄(t), W̄₁(t), W̄₂(t), P_loss(t) lungo le fasi |
| Criticità | t_warm cresce con ρ→1 e con m; scelta dell'intervallo di campionamento; non confondere transitorio iniziale (artefatto, da troncare) con transitorio d'attacco (fisico, da analizzare) |

### Step 6 — Disegno esperimenti / orizzonte (decisioni)
| Aspetto | Contenuto |
|---|---|
| Attacco a fasce | **orizzonte finito (terminating)**: **repliche indipendenti** (n=64 o 96), stesse condizioni iniziali, `PlantSeeds` fuori dal ciclo; NON si tronca il transitorio |
| Dimensionamento nominale | **orizzonte infinito (steady-state)**: singolo run lungo + **Batch Means** dopo il warm-up (Step 5) |
| Batch Means | k batch (**k≥32, rif. 64**), dimensione b abbastanza grande da azzerare l'**autocorrelazione** (b ≳ 2× lag di cutoff); medie di batch trattate i.i.d. Normali |
| IC 95% | x̄ ± t*·s/√(N−1), t*=idfStudent(N−1, 0.975); t*→1.96 per N>40; per medie **e** percentili; programma **`estimate`** (algoritmo di Welford) |
| Piano what-if | far variare **m∈{2,4,8,16}**, **K∈{10,50,100,200,∞}**, **λ₂** (moderato→sovraccarico), **disciplina** (FIFO vs priorità) |
| Confronto configurazioni | **Common Random Numbers (CRN)**: stessi stream di arrivo (0,1) su tutte le varianti ⇒ le differenze dipendono solo dalle scelte strutturali, non dal rumore |
| Criticità | b troppo piccolo ⇒ autocorrelazione residua ⇒ IC falsamente stretti (copertura ≪95%); b troppo grande ⇒ k<10 ⇒ t* instabile e IC larghi; confronti senza CRN ⇒ potere statistico ridotto |

### Step 7 — Analisi output & fase decisionale (decisioni)
| Aspetto | Contenuto |
|---|---|
| Output | **niente raw data dump**: aggregazione online con **Welford** (media/varianza a singolo passaggio); salvare solo il vettore sintetico per configurazione (medie + semiampiezze IC) + seed/`SelectStream` per riproducibilità |
| Grafici | ogni punto con **barra IC 95%**; assi con unità; interpolazione solo per X continua (λ₂), punti discreti per m; alto data-to-ink. G1: W₁,P_loss,1 vs m (+ linea SLA); G2: P_loss vs λ₂ (soglia 1%); G3: FIFO vs priorità (W₁ vs λ₂) |
| Tabelle | stima ± semiampiezza w per W₁,W₂,D₁,D₂,P_loss,1,P_loss,2,U,X_eff; celle SLA in grassetto |
| Decisione m* | minimo m con **W̄₁(m)+w₁(m) ≤ W_SLA** (limite superiore IC sotto la SLA) |
| Decisione λ₂* | massimo λ₂ prima che P_loss,1 superi 1% (intersezione della stima intervallare con 0.01) |
| Scheduling | priorità NP protegge la Classe 1 scaricando ritardo/scarto sulla Classe 2; FIFO fa collassare anche il legittimo sotto attacco |
| Confronto robusto | **CRN + differenza accoppiata** dᵢ=x_{A,i}−x_{B,i}, IC su d̄: se **non contiene 0** ⇒ A≠B significativo; se contiene 0 ⇒ indistinguibili. Attenzione all'**overlap trap** degli IC |
| Trade-off/vincoli | m↑ meno code ma più costo; K↑ azzera scarti ma aumenta ritardo (bufferbloat/jitter); ottimo = (m*,K*) minimo costo con P_loss,1≤1% e W₁≤W_SLA al picco |
| Criticità | non concludere da IC sovrapposti senza test accoppiato; decisione sensibile ai parametri sintetici dell'attacco; ottimo a regime ≠ tenuta al transitorio d'attacco (bilanciare entrambi) |

### Step 8 — Modello migliorativo (decisioni)
| Aspetto | Contenuto |
|---|---|
| Proposte (da programma) | **A) Autoscaling orizzontale con isteresi** (Serazzi); **B) Size-Based/SITA + Fast-Track** (Harchol-Balter); **C) Multi-queue + routing/overflow verso nodo di supporto** (caso edge/cloud Serazzi) |
| Candidato scelto | **Autoscaling dinamico dei serventi** (m variabile tra m_min e m_max) — *da confermare col compagno* |
| Modellazione (Next-Event) | nuove variabili `m_active`, `server_status[i]`∈{OFF,WARMING_UP,IDLE,BUSY}; parametri soglie **N_up/N_down** + **Δt_setup** (setup time); nuovi eventi `SERVER_ACTIVATED`/`SERVER_DEACTIVATED`; logica scale-up in arrivo, scale-down in completamento |
| Confronto base vs migliorativo | **stessi scenari + CRN**; **differenza accoppiata** dᵢ=X_migl,i−X_base,i con IC 95% (via `estimate`); significativo se IC non contiene 0; **variazione %** Δ%=(X_migl−X_base)/X_base; tabelle affiancate + grafici W₁ vs λ₂ |
| Criticità | **chattering** se N_up/N_down troppo vicine (serve isteresi/tempo minimo); **setup delay** troppo lungo ⇒ servente pronto a picco finito; **fairness**: autoscaling/size-based penalizzano fortemente la Classe 2 (possibile starvation) |

### Mappatura esercizi ↔ strumenti del corso (traccia progetto)
1. Nodo singolo normale → M/M/1 / KP
2. Sotto attacco + cluster → M/M/m (Erlang-C), stabilità
3. Buffer finito → sistema a perdita M/M/m/K (Erlang-B), P_loss, throughput effettivo
4. Protezione legittimo → scheduling a priorità (senza prelazione) + size-based + slowdown
5. Pipeline end-to-end + upgrade → rete aperta (Jackson) + legge gen. tempo di risposta + fattore di scala + bound Xmax=1/Dmax

---

## 4. Fonti e articoli

### Notizie / report sul caso (verificati via web, set. 2026)
- Cloudflare — 2025 Q4 DDoS threat report (31,4 Tbps): https://blog.cloudflare.com/ddos-threat-report-2025-q4/
- SecurityAffairs — AISURU 29,7 Tbps: https://securityaffairs.com/185299/security/cloudflare-mitigates-record-29-7-tbps-ddos-attack-by-the-aisuru-botnet.html
- The Hacker News — record 11,5 Tbps (AISURU): https://thehackernews.com/2025/09/cloudflare-blocks-record-breaking-115.html
- GBHackers — AISURU, 300.000 router e CVE sfruttate: https://gbhackers.com/aisuru-botnet/
- Krebs on Security — AISURU colpisce ISP USA: https://krebsonsecurity.com/2025/10/ddos-botnet-aisuru-blankets-us-isps-in-record-ddos/

### Testi/materiali del corso (da citare nella relazione)
- Leemis & Park — *Discrete-Event Simulation: A First Course* (processo di modellazione, obiettivi, modello concettuale)
- Harchol-Balter — *Performance Modeling and Design of Computer Systems* (sistemi aperti/chiusi; scheduling a priorità e size-based)
- Serazzi — *Performance Modeling* (astrazione, single station & bottleneck, casi di studio edge/cloud, autoscaler)
- Kurkowski — (metodologia simulazione/credibilità)
- Slide e trascrizioni del corso (Prof.ssa de Nitto Personè)

> ⚠️ Da verificare direttamente nei materiali: numeri esatti di capitoli/sezioni e nomi file delle slide citati da NotebookLM (vedi note di verifica del Punto 1).

---

## 5. Questioni aperte / TODO
- [x] **Individuale o gruppo?** → **Gruppo di 2** ⇒ modello migliorativo (Step 8) OBBLIGATORIO; ricordare la comunicazione via e-mail al docente.
- [x] **Linguaggio del simulatore** → **Python**.
- [ ] Idea per il modello migliorativo (Step 8): autoscaling dinamico dei moduli di scrubbing, corsia Fast-Track per il legittimo, o routing intelligente — da scegliere.
- [ ] **Piano di lavoro codice:** prima si completa il metodo con NotebookLM (Step 7–9), poi si scrive il codice Python (`src/`: `rngs.py`, `rvgs.py`, `simulator.py`, `verify.py`, `transient.py`, `experiments.py`). Il codice va **commentato**; l'**esecuzione la fa lo studente** (non eseguito nel workspace).
- [ ] Confermare i riferimenti bibliografici esatti (capitoli/sezioni) nelle proprie copie dei testi.
- [ ] Decidere valore di K (capacità buffer) e da dove ricavarlo.
- [ ] Decidere distribuzione del tempo di servizio: Esponenziale vs Bounded Pareto/Iperesponenziale (heavy-tail per richieste HTTP).
- [ ] Decidere se modellare il ramp-up dell'attacco (evento artificiale / fascia temporale) o scenario a carico costante + what-if.
- [ ] Orizzonte: transitorio (obbligatorio) + scelta finito vs steady-state/batch means.
- [ ] Validare i parametri sintetici con almeno un benchmark di letteratura.

---

## 6. Changelog
- **2026-09-22 (a)** — Creazione registro. Scelta caso (AISURU/scrubbing), parametri baseline, mappatura esercizi, fonti iniziali. Impostazione Punto 1.
- **2026-09-22 (b)** — Letta la **Guida ufficiale del progetto**: aggiunta sezione 1-bis con i 9 step. Emerso requisito **simulatore a eventi discreti**, transitorio obbligatorio, modello migliorativo per gruppi. Aggiornati i TODO. Preparato il prompt NotebookLM per lo **Step 2 (Modello Concettuale e delle Specifiche)**.
- **2026-09-22 (c)** — Decisioni: **gruppo di 2** (⇒ Step 8 obbligatorio) e **simulatore in Python**.
- **2026-09-22 (d)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 2**: fissate le decisioni su stato, eventi, carico, distribuzioni e scheduling. Aggiunto **vincolo: solo distribuzioni/discipline viste a lezione** (⚠️ NHPP e Bounded Pareto da verificare; in caso negativo → evento artificiale per il picco e H₂ per la variabilità). Preparato il prompt per lo **Step 3 (simulatore Next-Event in Python)**.
- **2026-09-22 (e)** — Creata e pushata la **repo GitHub `pmcsn-ddos-scrubbing`** (pubblica) con questo registro come README. Aggiunta sezione "Stato di avanzamento". Preparati i prompt NotebookLM per gli Step 4–9.
- **2026-09-22 (f)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 3** (simulatore Next-Event in Python): fissate architettura, strutture dati, gestione eventi, accumulatori/leggi operazionali, multi-stream `rngs`/`rvgs`, `PlantSeeds` fuori dal ciclo, predisposizione a verifica (M/M/1, M/M/m/K) e transitorio. Annotati refusi dello pseudocodice e consiglio di tenere servizio esponenziale nel base. Prossimo: prompt Step 4 (Verifica & Validazione).
- **2026-09-22 (g)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 4** (Verifica & Validazione): fissati controlli di verifica (bilancio flussi, Little, W=D+S), baseline analitici M/M/1 / M/M/m / M/M/m/K (Erlang-B), criterio dell'IC 95% e consistency checks. Prossimo: prompt Step 5 (Analisi del transitorio).
- **2026-09-22 (h)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 5** (Analisi del transitorio): metodo di Welch, repliche indipendenti, media cumulativa, troncamento del warm-up per lo steady-state; distinzione tra transitorio iniziale (da troncare) e transitorio d'attacco a fasce (orizzonte finito, da analizzare). Prossimo: prompt Step 6 (orizzonte finito/infinito, batch means, IC).
- **2026-09-22 (i)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 6** (Disegno esperimenti): repliche (orizzonte finito) per l'attacco, batch means (k≥32/64) per il dimensionamento, IC 95% con `estimate`/Welford, matrice what-if (m,K,λ₂,disciplina) e **Common Random Numbers** per i confronti. Prossimo: prompt Step 7 (analisi output e decisione).
- **2026-09-22 (j)** — Deciso il **piano di lavoro codice**: completare prima il metodo (prompt Step 7–9 su NotebookLM), poi scrivere il simulatore Python **commentato**; l'esecuzione sarà a carico dello studente.
- **2026-09-22 (k)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 7** (Analisi output & decisione): aggregazione Welford senza raw data, grafici con barre IC, criteri decisionali m*/λ₂*, confronto CRN con differenza accoppiata e overlap trap. Prossimo: prompt Step 8 (modello migliorativo, obbligatorio per il gruppo).
- **2026-09-22 (l)** — Ricevuta e registrata la risposta NotebookLM per lo **Step 8** (Modello migliorativo): proposte autoscaling/size-based/routing; candidato **autoscaling con isteresi** (da confermare); modellazione (nuovi stati/eventi/soglie, setup time); confronto base vs migliorativo con CRN + differenza accoppiata + variazione %. Prossimo: prompt Step 9 (relazione + orale).
