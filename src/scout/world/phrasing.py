"""How suppliers say things on their pages, in three tiers.

common  the phrasing the keyword checks in scout/verify.py were written for
varied  the same facts in other words; a labelled sample of it is what the reader is trained on
novel   phrasing that appears only later (the drift and held-out worlds); nothing is trained on it until it is
        harvested from production

Every template is labelled with its stance. The labels are the truth: they stay in the world, and only the corpus
export (scripts/export_labels.py, standing in for an annotation team) and the stand-in model read them.
"""

from __future__ import annotations

T = dict[str, dict[str, list[str]]]  # tier -> language -> templates

MAKES: T = {
    "common": {
        "en": ["{name} is a manufacturer with in-house production.", "We produce every part in our own production."],
        "de": ["{name} ist ein Hersteller mit eigener Fertigung.", "Wir fertigen alle Teile in eigener Fertigung."],
    },
    "varied": {
        "en": [
            "All parts leave our own plant in {city}.",
            "Every part is made on our shop floor, from raw material to inspection.",
            "{staff} people work in our factory in {city} in three shifts.",
            "We machine, finish and inspect everything under one roof.",
        ],
        "de": [
            "Alle Teile entstehen in unserem Werk in {city}.",
            "Vom Rohmaterial bis zur Prüfung läuft alles in unserer Halle.",
            "{staff} Mitarbeitende arbeiten bei uns im Dreischichtbetrieb.",
            "Wir produzieren selbst am Standort {city}.",
        ],
    },
    "novel": {
        "en": [
            "Our {staff} employees take each part from bar stock to packed pallet in {city}.",
            "Nothing is subcontracted: the machines in hall 2 are ours.",
        ],
        "de": [
            "Unsere {staff} Beschäftigten bringen jedes Teil vom Stangenmaterial bis zur Palette.",
            "Nichts wird vergeben: die Maschinen in Halle 2 gehören uns.",
        ],
    },
}

TRADES: T = {
    "common": {
        "en": ["We are a distributor of industrial components from leading manufacturers."],
        "de": ["Wir sind Händler und Vertrieb von Industriekomponenten."],
    },
    "varied": {
        "en": [
            "We source from a network of partner factories and handle logistics for you.",
            "Our sourcing team places your orders with vetted factories in Asia.",
            "We buy from selected plants and deliver from our warehouse in {city}.",
        ],
        "de": [
            "Wir beschaffen die Teile bei geprüften Partnerwerken.",
            "Unser Einkaufsteam vergibt Ihre Aufträge an ausgewählte Fabriken.",
            "Wir kaufen bei ausgewählten Werken ein und liefern aus unserem Lager in {city}.",
        ],
    },
    "novel": {
        "en": [
            "As an agency we connect buyers with qualified factories across Asia.",
            "You order from us; production is handled by our partners.",
        ],
        "de": [
            "Als Agentur bringen wir Einkäufer mit qualifizierten Werken zusammen.",
            "Sie bestellen bei uns, gefertigt wird bei unseren Partnern.",
        ],
    },
}

PROC_ON: T = {
    "common": {"en": ["Our core capability is {proc}."], "de": ["Unsere Kernkompetenz: {proc}."]},
    "varied": {
        "en": [
            "Customers come to us for {proc} in small and large batches.",
            "{proc} is what we do every day, on {machines} machines.",
            "We added a second line for {proc} this year.",
        ],
        "de": [
            "Für {proc} kommen Kunden mit kleinen und großen Serien zu uns.",
            "{proc} machen wir jeden Tag, auf {machines} Maschinen.",
            "Für {proc} haben wir dieses Jahr eine zweite Linie aufgebaut.",
        ],
    },
    "novel": {
        "en": ["Ask us about {proc}: lead times from three weeks."],
        "de": ["Fragen Sie uns nach {proc}: Lieferzeiten ab drei Wochen."],
    },
}

PROC_OFF: T = {
    "common": {
        "en": ["We no longer offer {proc} since last year."],
        "de": ["{proc}: diese Leistung bieten wir nicht mehr an."],
    },
    "varied": {
        "en": [
            "We sold our {proc} line in {year} and now focus on other work.",
            "{proc} was moved out of our plant in {year}.",
            "After {year} we stopped taking orders for {proc}.",
        ],
        "de": [
            "Die Sparte {proc} haben wir {year} verkauft.",
            "{proc} wurde {year} aus unserem Werk ausgelagert.",
            "Seit {year} nehmen wir keine Aufträge für {proc} mehr.",
        ],
    },
    "novel": {
        "en": ["Since the move to {city} we outsource {proc} entirely."],
        "de": ["Seit dem Umzug nach {city} vergeben wir {proc} komplett nach außen."],
    },
}

CERT_ON: T = {
    "common": {"en": ["Certified to {cert}."], "de": ["Zertifiziert nach {cert}."]},
    "varied": {
        "en": [
            "We passed our {cert} recertification audit this spring.",
            "Our quality system is audited every year to {cert}.",
            "{cert} certificate in place, copy available on request.",
        ],
        "de": [
            "Das Rezertifizierungsaudit nach {cert} haben wir im Frühjahr bestanden.",
            "Unser QM-System wird jährlich nach {cert} auditiert.",
            "Zertifikat nach {cert} liegt vor, Kopie auf Anfrage.",
        ],
    },
    "novel": {
        "en": ["{cert} certificate no. {num}, valid until {future}."],
        "de": ["{cert}-Zertifikat Nr. {num}, gültig bis {future}."],
    },
}

CERT_OFF: T = {
    "common": {
        "en": ["Our {cert} certificate expired in 2024."],
        "de": ["Unser Zertifikat {cert} ist 2024 abgelaufen."],
    },
    "varied": {
        "en": [
            "Our {cert} certificate lapsed in {year}.",
            "{cert} certification was withdrawn after the last audit.",
            "We let our {cert} certification run out in {year}.",
        ],
        "de": [
            "Unser {cert}-Zertifikat war bis {year} gültig.",
            "Die Zertifizierung nach {cert} ruht derzeit.",
            "Das {cert}-Zertifikat wurde nach dem letzten Audit entzogen.",
        ],
    },
    "novel": {
        "en": ["The {cert} audit was failed in {year}; recertification is planned."],
        "de": ["Das {cert}-Audit {year} wurde nicht bestanden, die Rezertifizierung ist geplant."],
    },
}

CERT_OTHERS: T = {  # a certificate on the page that is not the company's own
    "common": {"en": [], "de": []},
    "varied": {
        "en": [
            "Our customers include {cert} certified medical and automotive companies.",
            "We are preparing for {cert} and expect the audit next year.",
        ],
        "de": [
            "Zu unseren Kunden zählen nach {cert} zertifizierte Unternehmen.",
            "Wir bereiten uns auf {cert} vor, das Audit ist für nächstes Jahr geplant.",
        ],
    },
    "novel": {
        "en": ["Our raw material comes from {cert} certified mills."],
        "de": ["Unser Rohmaterial stammt aus nach {cert} zertifizierten Werken."],
    },
}

BOILERPLATE = {
    "en": [
        "Founded in {founded}, family owned.",
        "Contact our sales team for a quote within 48 hours.",
        "News: our new ERP system went live this quarter.",
        "We are hiring apprentices for next autumn.",
    ],
    "de": [
        "Gegründet {founded}, familiengeführt.",
        "Unser Vertrieb sendet Ihnen ein Angebot innerhalb von 48 Stunden.",
        "Neu: unser ERP-System ist seit diesem Quartal live.",
        "Wir suchen Auszubildende für den Herbst.",
    ],
}

CITIES = ["Brno", "Graz", "Poznań", "Brescia", "Porto", "Győr", "Lyon", "Valencia", "Eindhoven", "Chemnitz", "Izmir"]

BANKS = {
    "MAKES": MAKES,
    "TRADES": TRADES,
    "PROC_ON": PROC_ON,
    "PROC_OFF": PROC_OFF,
    "CERT_ON": CERT_ON,
    "CERT_OFF": CERT_OFF,
    "CERT_OTHERS": CERT_OTHERS,
}


def tier(r, shares: dict[str, float]) -> str:
    """Pick the tier of one sentence: novel first, then varied, otherwise common."""
    x = r.random()
    if x < shares.get("novel", 0.0):
        return "novel"
    if x < shares.get("novel", 0.0) + shares.get("varied", 0.0):
        return "varied"
    return "common"


def say(stance: str, lang: str, r, shares: dict[str, float], **slots) -> tuple[str, str]:
    """One sentence for a stance, and the tier it came from."""
    bank = BANKS[stance]
    t = tier(r, shares)
    options = bank[t][lang] or bank["varied"][lang]
    if not options:
        t, options = "common", bank["common"][lang]
    filled = {
        "city": r.choice(CITIES),
        "staff": r.choice([35, 80, 140, 260, 410]),
        "machines": r.choice([6, 12, 24, 40]),
        "year": r.choice([2022, 2023, 2024, 2025]),
        "future": r.choice(["03/2027", "11/2028", "06/2029"]),
        "num": r.randint(10_000, 99_999),
        **slots,
    }
    return r.choice(options).format(**filled), t
