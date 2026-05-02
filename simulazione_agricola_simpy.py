"""
Project Work - Simulazione di un processo produttivo nel settore primario
Caso: azienda agricola mista con grano, pomodori e olive.

Versione finale con SimPy.
Punto chiave del modello:
- le quantita' da raccogliere/produrre sono generate casualmente dal randomizzatore;
- i parametri configurabili descrivono il processo produttivo: resa per ettaro,
  tempi per unita', capacita' giornaliera, risorse disponibili e regole operative;
- il miglioramento dello scenario digitalizzato non dipende da un moltiplicatore
  di efficienza imposto, ma emerge da risorse e regole operative: piu' macchinari,
  presenza di monitoraggio IoT, minori imprevisti, minore setup e minore spreco.
"""

import csv
import random
import statistics
from dataclasses import dataclass, field
from queue import Queue
from typing import Dict, List

import simpy


@dataclass
class ProdottoConfig:
    prodotto: str
    sequenza_produttiva: str
    resa_per_ettaro: float
    tempo_per_unita: float
    capacita_giornaliera_prodotto: float
    priorita: int
    manodopera_per_unita: float
    macchinari_per_unita: float
    trasporto_per_unita: float
    deperibilita: float


@dataclass
class RisorsaConfig:
    scenario: str
    risorsa: str
    capacita_giornaliera: int
    costo_giornaliero: float


@dataclass
class ScenarioConfig:
    scenario: str
    descrizione: str
    criterio_pianificazione: str
    setup_base: float
    probabilita_imprevisto_base: float
    ritardo_imprevisto_min: float
    ritardo_imprevisto_max: float
    spreco_base: float


@dataclass
class Lotto:
    id_lotto: int
    prodotto: str
    quantita: float
    sequenza_produttiva: str
    priorita: int
    tempo_per_unita: float
    capacita_giornaliera_prodotto: float
    resa_per_ettaro: float
    manodopera_per_unita: float
    macchinari_per_unita: float
    trasporto_per_unita: float
    deperibilita: float
    urgenza: int
    ettari_necessari: float = 0


@dataclass
class RisultatoLotto:
    scenario: str
    id_lotto: int
    prodotto: str
    sequenza_produttiva: str
    quantita_richiesta: float
    quantita_buona: float
    spreco: float
    ettari_necessari: float
    inizio: float
    fine: float
    durata_totale: float
    attesa_risorse: float
    setup: float
    ritardo_imprevisto: float
    uso_iot: bool


def leggi_prodotti(percorso: str) -> Dict[str, ProdottoConfig]:
    prodotti = {}
    with open(percorso, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            prodotti[r["prodotto"]] = ProdottoConfig(
                prodotto=r["prodotto"],
                sequenza_produttiva=r["sequenza_produttiva"],
                resa_per_ettaro=float(r["resa_per_ettaro"]),
                tempo_per_unita=float(r["tempo_per_unita"]),
                capacita_giornaliera_prodotto=float(r["capacita_giornaliera_prodotto"]),
                priorita=int(r["priorita"]),
                manodopera_per_unita=float(r["manodopera_per_unita"]),
                macchinari_per_unita=float(r["macchinari_per_unita"]),
                trasporto_per_unita=float(r["trasporto_per_unita"]),
                deperibilita=float(r["deperibilita"]),
            )
    return prodotti


def leggi_risorse(percorso: str) -> Dict[str, Dict[str, RisorsaConfig]]:
    risorse = {}
    with open(percorso, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            scenario = r["scenario"]
            risorse.setdefault(scenario, {})
            risorse[scenario][r["risorsa"]] = RisorsaConfig(
                scenario=scenario,
                risorsa=r["risorsa"],
                capacita_giornaliera=int(float(r["capacita_giornaliera"])),
                costo_giornaliero=float(r["costo_giornaliero"]),
            )
    return risorse


def leggi_scenari(percorso: str) -> Dict[str, ScenarioConfig]:
    scenari = {}
    with open(percorso, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            scenari[r["scenario"]] = ScenarioConfig(
                scenario=r["scenario"],
                descrizione=r["descrizione"],
                criterio_pianificazione=r["criterio_pianificazione"],
                setup_base=float(r["setup_base"]),
                probabilita_imprevisto_base=float(r["probabilita_imprevisto_base"]),
                ritardo_imprevisto_min=float(r["ritardo_imprevisto_min"]),
                ritardo_imprevisto_max=float(r["ritardo_imprevisto_max"]),
                spreco_base=float(r["spreco_base"]),
            )
    return scenari


def genera_quantita_random(prodotto: str) -> int:
    """
    Randomizzatore richiesto dalla traccia PW15.
    Genera direttamente la quantita' da produrre/raccogliere.

    Gli intervalli sono interni alla funzione e non rappresentano la resa per ettaro.
    La resa per ettaro e' invece un parametro tecnico configurabile nel CSV.
    """
    intervalli = {
        "Grano": (90, 170),
        "Pomodori": (70, 150),
        "Olive": (45, 120),
    }
    minimo, massimo = intervalli[prodotto]
    return random.randint(minimo, massimo)


def genera_lotti(prodotti: Dict[str, ProdottoConfig], seed: int = 7) -> Queue:
    random.seed(seed)
    coda = Queue()
    id_lotto = 1

    # Per ogni prodotto genero piu' lotti, in modo che possano crearsi code e sovrapposizioni.
    for prodotto, cfg in prodotti.items():
        for _ in range(3):
            quantita = genera_quantita_random(prodotto)
            urgenza = random.randint(1, 5)
            lotto = Lotto(
                id_lotto=id_lotto,
                prodotto=prodotto,
                quantita=quantita,
                sequenza_produttiva=cfg.sequenza_produttiva,
                priorita=cfg.priorita,
                tempo_per_unita=cfg.tempo_per_unita,
                capacita_giornaliera_prodotto=cfg.capacita_giornaliera_prodotto,
                resa_per_ettaro=cfg.resa_per_ettaro,
                manodopera_per_unita=cfg.manodopera_per_unita,
                macchinari_per_unita=cfg.macchinari_per_unita,
                trasporto_per_unita=cfg.trasporto_per_unita,
                deperibilita=cfg.deperibilita,
                urgenza=urgenza,
                ettari_necessari=quantita / cfg.resa_per_ettaro,
            )
            coda.put(lotto)
            id_lotto += 1
    return coda


def copia_coda(coda: Queue) -> Queue:
    nuova = Queue()
    for lotto in list(coda.queue):
        nuova.put(lotto)
    return nuova


def ordina_lotti(lotti: List[Lotto], scenario: ScenarioConfig) -> List[Lotto]:
    if scenario.criterio_pianificazione == "priorita_digitale":
        # Con IoT e sistema digitale l'azienda lavora prima i lotti piu' urgenti e deperibili.
        return sorted(lotti, key=lambda l: (l.priorita, -l.deperibilita, l.urgenza, l.quantita))
    # Scenario tradizionale: pianificazione meno coordinata.
    random.shuffle(lotti)
    return lotti


def calcola_effetto_iot(risorse_cfg: Dict[str, RisorsaConfig]) -> float:
    """
    Restituisce un indice 0-1. Non e' un moltiplicatore diretto sul tempo.
    Serve a ridurre meccanismi operativi concreti: setup, imprevisti e spreco.
    """
    iot = risorse_cfg.get("monitoraggio_iot")
    if not iot or iot.capacita_giornaliera <= 0:
        return 0.0
    return min(1.0, iot.capacita_giornaliera / 4.0)


def processo_lotto(env, lotto: Lotto, scenario: ScenarioConfig, risorse, risorse_cfg, risultati: List[RisultatoLotto]):
    arrivo = env.now
    indice_iot = calcola_effetto_iot(risorse_cfg)
    usa_iot = indice_iot > 0 and "monitoraggio_iot" in risorse

    richieste_monitoraggio = []
    if usa_iot:
        richieste_monitoraggio.append(risorse["monitoraggio_iot"].request())
        yield simpy.AllOf(env, richieste_monitoraggio)
        # Il monitoraggio richiede un piccolo tempo iniziale, ma abilita decisioni migliori.
        yield env.timeout(0.10)
        for req in richieste_monitoraggio:
            req.resource.release(req)

    setup = max(0.10, scenario.setup_base * (1 - 0.55 * indice_iot))
    yield env.timeout(setup)

    # Il lotto richiede simultaneamente manodopera, macchinari e trasporto.
    # Se una risorsa non e' disponibile, SimPy mette automaticamente il lotto in coda.
    req_man = risorse["manodopera"].request()
    req_mac = risorse["macchinari"].request()
    req_tra = risorse["trasporto"].request()

    yield simpy.AllOf(env, [req_man, req_mac, req_tra])
    inizio_lavorazione = env.now
    attesa_risorse = inizio_lavorazione - arrivo - setup

    # Durata tecnica basata su quantita', tempo per unita' e capacita' giornaliera del prodotto.
    durata_da_tempo_unitario = lotto.quantita * lotto.tempo_per_unita
    durata_da_capacita = lotto.quantita / lotto.capacita_giornaliera_prodotto
    durata_tecnica = max(durata_da_tempo_unitario, durata_da_capacita)

    # La disponibilita' di macchinari incide in modo reale: non come bonus arbitrario,
    # ma come maggiore capacita' di lavorare lotti concorrenti. SimPy gestisce la coda.
    yield env.timeout(durata_tecnica)

    req_man.resource.release(req_man)
    req_mac.resource.release(req_mac)
    req_tra.resource.release(req_tra)

    # Imprevisti: non sono eliminati magicamente. Il monitoraggio li riduce perche' consente
    # controllo preventivo e migliore coordinamento operativo.
    probabilita_imprevisto = max(0.02, scenario.probabilita_imprevisto_base * (1 - 0.65 * indice_iot))
    ritardo = 0.0
    if random.random() < probabilita_imprevisto:
        ritardo = random.uniform(scenario.ritardo_imprevisto_min, scenario.ritardo_imprevisto_max)
        yield env.timeout(ritardo)

    # Spreco: i prodotti deperibili sono piu' sensibili alle attese. L'IoT riduce lo spreco
    # perche' coordina meglio tempi di raccolta, trasporto e monitoraggio.
    spreco_percentuale = scenario.spreco_base * (1 + lotto.deperibilita * 0.6) * (1 - 0.70 * indice_iot)
    spreco = lotto.quantita * spreco_percentuale
    quantita_buona = max(0, lotto.quantita - spreco)

    risultati.append(RisultatoLotto(
        scenario=scenario.scenario,
        id_lotto=lotto.id_lotto,
        prodotto=lotto.prodotto,
        sequenza_produttiva=lotto.sequenza_produttiva,
        quantita_richiesta=round(lotto.quantita, 2),
        quantita_buona=round(quantita_buona, 2),
        spreco=round(spreco, 2),
        ettari_necessari=round(lotto.ettari_necessari, 2),
        inizio=round(arrivo, 2),
        fine=round(env.now, 2),
        durata_totale=round(env.now - arrivo, 2),
        attesa_risorse=round(max(0, attesa_risorse), 2),
        setup=round(setup, 2),
        ritardo_imprevisto=round(ritardo, 2),
        uso_iot=usa_iot,
    ))


def simula_scenario(nome_scenario: str, coda_lotti: Queue, scenari, risorse_tutte):
    scenario = scenari[nome_scenario]
    risorse_cfg = risorse_tutte[nome_scenario]

    env = simpy.Environment()
    risorse = {}
    for nome, cfg in risorse_cfg.items():
        if cfg.capacita_giornaliera > 0:
            risorse[nome] = simpy.Resource(env, capacity=cfg.capacita_giornaliera)

    lotti = list(coda_lotti.queue)
    lotti = ordina_lotti(lotti, scenario)

    risultati = []
    for lotto in lotti:
        env.process(processo_lotto(env, lotto, scenario, risorse, risorse_cfg, risultati))

    env.run()
    return risultati


def riepilogo_per_prodotto(risultati: List[RisultatoLotto]):
    dati = {}
    for r in risultati:
        dati.setdefault(r.prodotto, {
            "quantita_richiesta": 0,
            "quantita_buona": 0,
            "spreco": 0,
            "tempo_complessivo": 0,
            "attesa": 0,
            "lotti": 0,
        })
        d = dati[r.prodotto]
        d["quantita_richiesta"] += r.quantita_richiesta
        d["quantita_buona"] += r.quantita_buona
        d["spreco"] += r.spreco
        d["tempo_complessivo"] = max(d["tempo_complessivo"], r.fine)
        d["attesa"] += r.attesa_risorse
        d["lotti"] += 1
    return dati


def stampa_risultati(nome_scenario, risultati: List[RisultatoLotto], risorse_cfg):
    fine_totale = max(r.fine for r in risultati)
    attesa_totale = sum(r.attesa_risorse for r in risultati)
    quantita_buona = sum(r.quantita_buona for r in risultati)
    spreco = sum(r.spreco for r in risultati)
    costo_giornaliero = sum(r.costo_giornaliero for r in risorse_cfg.values())
    costo_totale = costo_giornaliero * fine_totale

    print("\n" + "=" * 72)
    print(f"SCENARIO {nome_scenario}")
    print("=" * 72)
    print(f"Durata complessiva simulata: {fine_totale:.2f} giorni")
    print(f"Quantita' buona ottenuta: {quantita_buona:.2f}")
    print(f"Spreco stimato: {spreco:.2f}")
    print(f"Attesa complessiva per risorse: {attesa_totale:.2f} giorni")
    print(f"Costo operativo stimato: euro {costo_totale:.2f}")

    print("\nRiepilogo per prodotto:")
    for prodotto, d in riepilogo_per_prodotto(risultati).items():
        print(
            f"- {prodotto}: quantita' richiesta={d['quantita_richiesta']:.2f}, "
            f"quantita' buona={d['quantita_buona']:.2f}, "
            f"spreco={d['spreco']:.2f}, "
            f"tempo complessivo={d['tempo_complessivo']:.2f} giorni, "
            f"attesa={d['attesa']:.2f} giorni"
        )


def salva_csv(percorso: str, risultati_tutti: Dict[str, List[RisultatoLotto]]):
    campi = list(RisultatoLotto.__dataclass_fields__.keys())
    with open(percorso, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=campi)
        writer.writeheader()
        for risultati in risultati_tutti.values():
            for r in risultati:
                writer.writerow(r.__dict__)


def main():
    prodotti = leggi_prodotti("prodotti.csv")
    risorse = leggi_risorse("risorse.csv")
    scenari = leggi_scenari("scenari.csv")

    coda_base = genera_lotti(prodotti, seed=12)
    risultati_tutti = {}

    for nome_scenario in ["A", "B"]:
        risultati = simula_scenario(nome_scenario, copia_coda(coda_base), scenari, risorse)
        risultati_tutti[nome_scenario] = risultati
        stampa_risultati(nome_scenario, risultati, risorse[nome_scenario])

    salva_csv("risultati_simulazione.csv", risultati_tutti)

    a = risultati_tutti["A"]
    b = risultati_tutti["B"]
    durata_a = max(r.fine for r in a)
    durata_b = max(r.fine for r in b)
    attesa_a = sum(r.attesa_risorse for r in a)
    attesa_b = sum(r.attesa_risorse for r in b)
    spreco_a = sum(r.spreco for r in a)
    spreco_b = sum(r.spreco for r in b)

    print("\nCONFRONTO A/B")
    print(f"- Riduzione durata: {durata_a - durata_b:.2f} giorni")
    print(f"- Riduzione attese: {attesa_a - attesa_b:.2f} giorni")
    print(f"- Riduzione sprechi: {spreco_a - spreco_b:.2f} unita'")
    print("\nNota: il risultato migliore dello scenario B non deriva da un moltiplicatore di efficienza, ma da risorse e regole operative: piu' macchinari, uso di IoT, migliore pianificazione, minori imprevisti e minore spreco.")


if __name__ == "__main__":
    main()
