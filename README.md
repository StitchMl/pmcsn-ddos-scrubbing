# Progetto PMCSN

## 1. Sintesi del caso reale

Botnet **AISURU** (variante Mirai/TurboMirai), 2025. Recluta dispositivi IoT sfruttando vulnerabilità note e zero-day; con 1–4 milioni di dispositivi ha generato i DDoS più grandi mai registrati. Il progetto modella l'infrastruttura di **mitigazione/scrubbing** di un PoP CDN come sistema a coda, per dimensionarla in modo che il traffico legittimo rispetti la QoS durante l'attacco.

### Vulnerabilità sfruttate
| CVE / vettore    | Dispositivo                            |
|------------------|----------------------------------------|
| CVE-2017-5259    | Cambium Networks                       |
| CVE-2023-28771   | Zyxel                                  |
| CVE-2023-50381   | Realtek Jungle SDK                     |
| Zero-day cnPilot | Cambium cnPilot routers                |
| Supply-chain     | server aggiornamento firmware Totolink |

### Numeri reali dell'attacco
- Picchi volumetrici: **22,2 → 29,7 → 31,4 Tbps**
- Picco pacchetti: **14,1 miliardi pps** (Bpps)
- Picco HTTP: **205 milioni rps** (Mrps)
- Durata attacchi lampo: **35–69 s**
- Dispositivi infetti: **1–4 milioni** (router, DVR, Android TV); ~300.000 router iniziali
- Cloudflare: **47,1 milioni** di attacchi mitigati nel 2025 (autonomamente)

---

## 2. Parametri del modello

> ⚠️ Valori scelti per avere numeri comodi e stabilità per m ≥ 4. Sono **sintetici**.

| Simbolo         | Significato                               | Valore baseline          | Fonte/nota                                                         |
|-----------------|-------------------------------------------|--------------------------|--------------------------------------------------------------------|
| $$E(S)$$        | tempo medio di ispezione per richiesta    | $$0,1 \text{ ms}$$       | assunto (ispezione L7)                                             |
| $$μ$$           | capacità di un core                       | 10.000 req/s             | $$= 1/E(S)$$                                                       |
| $$λ_L$$         | frequenza traffico legittimo              | $$6.000 \text{ req/s}$$  | $$\text{ assunto (}ρ=0,6 \text{ a 1 core in condizioni normali)}$$ |
| $$λ_A$$         | frequenza traffico d'attacco              | $$24.000 \text{ req/s}$$ | assunto (4× il legittimo)                                          |
| $$λ = λ_L+λ_A$$ | carico totale sotto attacco               | $$30.000 \text{ req/s}$$ | $$→ ρ = 3/m\text{, stabile per } m ≥ 4$$                           |
| $$m$$           | n. core/serventi scrubbing                | ≥ 4 (da dimensionare)    | incognita di progetto                                              |
| $$K$$           | capacità buffer (finita)                  | da definire              | $$\text{per calcolo }P_{loss}$$                                    |
| $$p_1, p_2$$    | frazione arrivi classe legittima/sospetta | $$0,2 / 0,8$$            | $$= λ_L/λ, λ_A/λ$$                                                 |

### Requisiti QoS
- Tempo di risposta medio complessivo sotto attacco: **$$E(T_S) ≤ 0,5 \text{ ms}$$**
- Tempo di risposta medio traffico legittimo (con priorità): **$$E(T_S,\text{legittimo}) ≤ 0,3 \text{ ms}$$**
- Perdita traffico legittimo: **≤ 1%**

---

## 3. Decisioni di modellazione

| Decisione                                                                    | Motivazione                                                                                                       |
|------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------|
| Caso scelto: scrubbing DDoS / AISURU                                         | Recente, reale, cyber/vulnerabilità; mappa su code, Erlang, perdita, scheduling                                   |
| Workload multi-classe: legittimo vs attacco                                  | Serve per scheduling a priorità e per P_loss del legittimo                                                        |
| Nodo scrubbing = risorsa critica (bottleneck)                                | Astrazione: si isola il collo di bottiglia, non tutto il PoP                                                      |
| Arrivi Poisson (legittimo); attacco heavy-load/eventualmente NHPP in ramp-up | Sovrapposizione molti utenti indip. → Poisson (Palm-Khinchin)                                                     |
| Buffer finito M/M/m/K per gestire ρ≥1 e calcolare P_loss                     | Senza loss il sistema aperto diverge sotto attacco                                                                |
| Valutare ANCHE il transitorio (attacchi 35–69 s)                             | L'attacco è impulsivo/non stazionario: steady-state da solo sottostima i ritardi iniziali                         |
| **Gruppo di 2 persone**                                                      | → **modello migliorativo (Step 8) obbligatorio**; comunicare i componenti al docente via e-mail prima dell'inizio |
| **Linguaggio simulatore: Python**                                            | Scelta per lo Step 3 (Next-Event); attenzione a PRNG con stream indipendenti e gestione seed (plantseed/putseed)  |
| **VINCOLO: usare solo distribuzioni/discipline/metodi visti a lezione**      | Evitare tecniche non trattate nel corso (rischio all'esame/relazione)                                             |

### Modello concettuale e delle specifiche
| Elemento                        | Scelta                                                                                                                |
|---------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| $$\text{Stato analitico }S(t)$$ | $$\text{vettore popolazione }(n₁,n₂), 0≤n₁+n₂≤K$$                                                                     |
| Stato simulatore                | $$l₁,l₂, servers[m]\text{ (idle/busy+classe), code per classe }Q₁,Q₂$$                                                |
| Topologia                       | 1 centro **multi-server m**, buffer **finito K**, sistema aperto                                                      |
| Eventi                          | arrivo cl.1, arrivo cl.2, completamento servente s; artificiali: cambio fase, campionamento, stop                     |
| Carico cl.1 (legittimo)         | Poisson omogeneo λ₁                                                                                                   |
| Carico cl.2 (attacco)           | Poisson a **carico costante elevato**; picco via **evento artificiale** che cambia λ₂                                 |
| Interarrivi                     | **Esponenziale**                                                                                                      |
| Tempi di servizio               | **Esponenziale** (modello analitico/validazione) + variante ad alta variabilità **Iperesponenziale H₂**               |
| Scheduling                      | **FIFO**, **priorità astratta NP/P**, **size-based**, **PS** (per confronto slowdown)                                 |
| Criticità chiave                | priorità multi-classe + buffer finito ⇒ **niente forma prodotto** ⇒ simulatore obbligatorio; transitorio obbligatorio |

### Modello computazionale / simulatore
| Elemento               | Scelta                                                                                                                                                                                              |
|------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Paradigma              | **Next-Event** (event-scheduling), Python nativo                                                                                                                                                    |
| Libreria PRNG          | **`rngs.py` / `rvgs.py`** di Leemis & Park                                                                                                                                                          |
| Stream (SelectStream)  | 0=arrivi cl.1, 1=arrivi cl.2, 2=servizio cl.1, 3=servizio cl.2, 4=eventi artificiali                                                                                                                |
| Seed                   | **`PlantSeeds()` UNA volta, FUORI dal ciclo repliche**                                                                                                                                              |
| Event list             | ARR1, ARR2, m completamenti (uno per servente), evento fase, STOP; idle ⇒ `t=INFINITY`                                                                                                              |
| Stato                  | `number_c1,number_c2`, `servers[m]` (busy+classe), `queue_c1`,`queue_c2` (timestamp arrivo)                                                                                                         |
| Scheduling nel sim.    | **priorità astratta non-preemptive** (coda 1 prima della coda 2)                                                                                                                                    |
| Accumulatori           | `area.node/queue/service` (integrali d'area, aggiornati PRIMA di cambiare stato), `sum.delay`, `sum.service`, conteggi arrivi/completamenti/**dropped** per classe                                  |
| Metriche               | $$E(N_c)=\text{area.node}/T, E(N_Q,c)=\text{area.queue}/T, E(T_Q,c)=\text{sum.delay}/C_c, E(T_S,c)=E(T_Q,c)+E(S_c), U=\text{area.service}/(m·T), X_c=C_c/T, P_loss,c=\text{dropped}/\text{arrivi}$$ |
| Picco d'attacco        | **evento artificiale a fasce** (Normale→Picco→Mitigazione) che cambia λ₂                                                                                                                            |
| Variabilità servizio   | **Esponenziale** nel base; **H₂/Erlang** come variante ad alta variabilità                                                                                                                          |
| Predisposizione Step 4 | riducibile a **M/M/1** (λ₂=0, m=1, K=∞) e **M/M/m/K** (λ₂=0) per confronto analitico                                                                                                                |
| Predisposizione Step 5 | registrare **media cumulativa** N̄(t) a intervalli per il warm-up                                                                                                                                    |

### Verifica & Validazione
| Aspetto                          | Contenuto                                                                                                                                                                                                                                                              |
|----------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Verifica codice                  | bilancio flussi (arrivi = completamenti + scarti + residui nel nodo) per classe e totale; `PlantSeeds` una volta fuori dal ciclo; accumulatori d'area aggiornati PRIMA del cambio di stato; identità W=D+S e l̄=q̄+x̄; Legge di Little con λ_eff=λ(1−P_loss)              |
| Baseline analitici (λ₂=0)        | $$\text{M/M/1}: U=ρ, E(N)=ρ/(1−ρ), E(N_Q)=ρ²/(1−ρ), E(T_S)=1/(μ−λ), E(T_Q)=ρ/(μ−λ) · \text{M/M/m} (Erlang-C): π₀, P_Q, E(T_Q)=P_Q/(mμ(1−ρ)) · \text{M/M/m/K}\text{ (nascita-morte, PASTA): }P_loss=π_K, X=λ(1−P_loss), U=λ(1−P_loss)/(mμ); per K=m ⇒ \text{Erlang-B}$$ |
| Criterio statistico              | il valore teorico deve cadere nell'**IC 95%** della stima simulata; t*→1.96 per n grande; n≥~30–40 repliche (≈385 se si vuole semiampiezza = 10% di s)                                                                                                                 |
| Consistency checks (validazione) | $$\text{monotonìa: }m↑ ⇒ E(N),D,P_loss↓; λ↑ ⇒ W,U,P_loss↑\text{; saturazione }λ≫mμ ⇒ P_loss→1−mμ/λ\text{; grafici }W\text{ vs }λ, P_loss\text{ vs }K, E(N)\text{ vs }m$$                                                                                               |
| Ramo multi-classe/priorità       | non ha forma prodotto: validare prima il motore in mono-classe (λ₂=0 vs M/M/m/K), poi verificare che E(T_Q,1)<E(T_Q,2) e la conservazione del lavoro                                                                                                                   |

### Analisi del transitorio
| Aspetto          | Contenuto                                                                                                                                                                                                                         |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Problema         | **initial condition bias**: partenza da sistema vuoto (N(0)=0) sottostima code/attese iniziali                                                                                                                                    |
| Procedura        | R=4–5 repliche indipendenti (seed via `PlantSeeds` fuori dal ciclo) sovrapposte; media cumulativa **N̄(t)=area.node(t)/t** e W̄(n)=Σwᵢ/n                                                                                            |
| Warm-up          | **metodo di Welch**: media di ensemble tra repliche + media mobile ⇒ individuare t_warm dove la curva si appiattisce                                                                                                              |
| Uso del warm-up  | per lo **steady-state** (dimensionamento nominale) si **scarta [0, t_warm]** e si azzerano gli accumulatori a t_warm                                                                                                              |
| Scenario attacco | l'attacco a fasce (Normale→Picco→Mitigazione) NON ammette steady-state ⇒ **orizzonte finito (terminating)**, inizializzando lo stato al regime pre-attacco; **il transitorio dell'attacco NON si tronca** (è l'oggetto di studio) |
| Grafici report   | N̄(t) multi-replica; curva Welch con cutoff t_warm; profilo temporale N̄(t), W̄₁(t), W̄₂(t), P_loss(t) lungo le fasi                                                                                                                  |
| Criticità        | t_warm cresce con ρ→1 e con m; scelta dell'intervallo di campionamento; non confondere transitorio iniziale (artefatto, da troncare) con transitorio d'attacco (fisico, da analizzare)                                            |

### Disegno esperimenti / orizzonte
| Aspetto                  | Contenuto                                                                                                                                                                                |
|--------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Attacco a fasce          | **orizzonte finito (terminating)**: **repliche indipendenti** (n=64 o 96), stesse condizioni iniziali, `PlantSeeds` fuori dal ciclo; NON si tronca il transitorio                        |
| Dimensionamento nominale | **orizzonte infinito (steady-state)**: singolo run lungo + **Batch Means** dopo il warm-up (Step 5)                                                                                      |
| Batch Means              | k batch (**k≥32, rif. 64**), dimensione b abbastanza grande da azzerare l'**autocorrelazione** (b ≳ 2× lag di cutoff); medie di batch trattate i.i.d. Normali                            |
| IC 95%                   | x̄ ± t*·s/√(N−1), t*=idfStudent(N−1, 0.975); t*→1.96 per N>40; per medie **e** percentili; programma **`estimate`** (algoritmo di Welford)                                                |
| Piano what-if            | far variare **m∈{2,4,8,16}**, **K∈{10,50,100,200,∞}**, **λ₂** (moderato→sovraccarico), **disciplina** (FIFO vs priorità)                                                                 |
| Confronto configurazioni | **Common Random Numbers (CRN)**: stessi stream di arrivo (0,1) su tutte le varianti ⇒ le differenze dipendono solo dalle scelte strutturali, non dal rumore                              |
| Criticità                | b troppo piccolo ⇒ autocorrelazione residua ⇒ IC falsamente stretti (copertura ≪95%); b troppo grande ⇒ k<10 ⇒ t* instabile e IC larghi; confronti senza CRN ⇒ potere statistico ridotto |

### Analisi output & fase decisionale
| Aspetto           | Contenuto                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Output            | **niente raw data dump**: aggregazione online con **Welford** (media/varianza a singolo passaggio); salvare solo il vettore sintetico per configurazione (medie + semiampiezze IC) + seed/`SelectStream` per riproducibilità        |
| Grafici           | ogni punto con **barra IC 95%**; assi con unità; interpolazione solo per X continua (λ₂), punti discreti per m; alto data-to-ink. G1: W₁,P_loss,1 vs m (+ linea SLA); G2: P_loss vs λ₂ (soglia 1%); G3: FIFO vs priorità (W₁ vs λ₂) |
| Tabelle           | stima ± semiampiezza w per W₁,W₂,D₁,D₂,P_loss,1,P_loss,2,U,X_eff; celle SLA in grassetto                                                                                                                                            |
| Decisione m*      | minimo m con **W̄₁(m)+w₁(m) ≤ W_SLA** (limite superiore IC sotto la SLA)                                                                                                                                                             |
| Decisione λ₂*     | massimo λ₂ prima che P_loss,1 superi 1% (intersezione della stima intervallare con 0.01)                                                                                                                                            |
| Scheduling        | priorità NP protegge la Classe 1 scaricando ritardo/scarto sulla Classe 2; FIFO fa collassare anche il legittimo sotto attacco                                                                                                      |
| Confronto robusto | **CRN + differenza accoppiata** dᵢ=x_{A,i}−x_{B,i}, IC su d̄: se **non contiene 0** ⇒ A≠B significativo; se contiene 0 ⇒ indistinguibili. Attenzione all'**overlap trap** degli IC                                                   |
| Trade-off/vincoli | m↑ meno code ma più costo; K↑ azzera scarti ma aumenta ritardo (bufferbloat/jitter); ottimo = (m*,K*) minimo costo con P_loss,1≤1% e W₁≤W_SLA al picco                                                                              |
| Criticità         | non concludere da IC sovrapposti senza test accoppiato; decisione sensibile ai parametri sintetici dell'attacco; ottimo a regime ≠ tenuta al transitorio d'attacco (bilanciare entrambi)                                            |

### Modello migliorativo
| Aspetto                        | Contenuto                                                                                                                                                                                                                                             |
|--------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Proposte (da programma)        | **A) Autoscaling orizzontale con isteresi** (Serazzi); **B) Size-Based/SITA + Fast-Track** (Harchol-Balter); **C) Multi-queue + routing/overflow verso nodo di supporto** (caso edge/cloud Serazzi)                                                   |
| Candidato scelto               | **Autoscaling dinamico dei serventi** (m variabile tra m_min e m_max) — *da confermare col compagno*                                                                                                                                                  |
| Modellazione (Next-Event)      | nuove variabili `m_active`, `server_status[i]`∈{OFF,WARMING_UP,IDLE,BUSY}; parametri soglie **N_up/N_down** + **Δt_setup** (setup time); nuovi eventi `SERVER_ACTIVATED`/`SERVER_DEACTIVATED`; logica scale-up in arrivo, scale-down in completamento |
| Confronto base vs migliorativo | **stessi scenari + CRN**; **differenza accoppiata** dᵢ=X_migl,i−X_base,i con IC 95% (via `estimate`); significativo se IC non contiene 0; **variazione %** Δ%=(X_migl−X_base)/X_base; tabelle affiancate + grafici W₁ vs λ₂                           |
| Criticità                      | **chattering** se N_up/N_down troppo vicine (serve isteresi/tempo minimo); **setup delay** troppo lungo ⇒ servente pronto a picco finito; **fairness**: autoscaling/size-based penalizzano fortemente la Classe 2 (possibile starvation)              |

---

## 4. Fonti e articoli

### Notizie / report sul caso (verificati via web, set. 2026)
- Cloudflare — 2025 Q4 DDoS threat report (31,4 Tbps): https://blog.cloudflare.com/ddos-threat-report-2025-q4/
- SecurityAffairs — AISURU 29,7 Tbps: https://securityaffairs.com/185299/security/cloudflare-mitigates-record-29-7-tbps-ddos-attack-by-the-aisuru-botnet.html
- The Hacker News — record 11,5 Tbps (AISURU): https://thehackernews.com/2025/09/cloudflare-blocks-record-breaking-115.html
- GBHackers — AISURU, 300.000 router e CVE sfruttate: https://gbhackers.com/aisuru-botnet/
- Krebs on Security — AISURU colpisce ISP USA: https://krebsonsecurity.com/2025/10/ddos-botnet-aisuru-blankets-us-isps-in-record-ddos/

### Testi/materiali del corso
- Leemis & Park — *Discrete-Event Simulation: A First Course* (processo di modellazione, obiettivi, modello concettuale)
- Harchol-Balter — *Performance Modeling and Design of Computer Systems* (sistemi aperti/chiusi; scheduling a priorità e size-based)
- Serazzi — *Performance Modeling* (astrazione, single station & bottleneck, casi di studio edge/cloud, autoscaler)
- Kurkowski — (metodologia simulazione/credibilità)
- Slide e trascrizioni del corso (Prof.ssa de Nitto Personè)

---

## 5. Questioni aperte / TODO
- [ ] Idea per il modello migliorativo (Step 8): autoscaling dinamico dei moduli di scrubbing, corsia Fast-Track per il legittimo, o routing intelligente — da scegliere.
- [ ] **Piano di lavoro codice:** prima si completa il metodo con NotebookLM (Step 7–9), poi si scrive il codice Python (`src/`: `rngs.py`, `rvgs.py`, `simulator.py`, `verify.py`, `transient.py`, `experiments.py`). Il codice va **commentato**; l'**esecuzione la fa lo studente** (non eseguito nel workspace).
- [ ] Confermare i riferimenti bibliografici esatti (capitoli/sezioni) nelle proprie copie dei testi.
- [ ] Decidere valore di K (capacità buffer) e da dove ricavarlo.
- [ ] Decidere distribuzione del tempo di servizio: Esponenziale vs Bounded Pareto/Iperesponenziale (heavy-tail per richieste HTTP).
- [ ] Decidere se modellare il ramp-up dell'attacco (evento artificiale / fascia temporale) o scenario a carico costante + what-if.
- [ ] Orizzonte: transitorio (obbligatorio) + scelta finito vs steady-state/batch means.
- [ ] Validare i parametri sintetici con almeno un benchmark di letteratura.

---

## Struttura della repo
```
pmcsn-ddos-scrubbing/
├── README.md                (questo registro)
└── src/
    ├── rngs.py              PRNG multi-stream (Leemis & Park)  ✅
    ├── rvgs.py              generatori di variabili aleatorie  ✅
    ├── simulator.py         modello base Next-Event            ✅
    ├── verify.py            verifica vs M/M/1, M/M/m/K          ⬜ prossima
    ├── transient.py         analisi transitorio (Welch)        ⬜
    └── experiments.py       what-if, batch means, IC, CRN      ⬜
```
Per eseguire il modello base:  `python src/simulator.py`  (dalla cartella della repo).
