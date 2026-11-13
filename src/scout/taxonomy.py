"""What a buyer can ask for, and the words suppliers use for it, in English and German."""

PROCESSES = {
    "cnc_milling": ["cnc milling", "milling", "cnc-fräsen", "fräsen", "machining centre"],
    "cnc_turning": ["cnc turning", "turning", "cnc-drehen", "drehen", "lathe"],
    "sheet_metal": ["sheet metal", "laser cutting", "bending", "blechbearbeitung", "laserschneiden"],
    "die_casting": ["die casting", "pressure die casting", "druckguss"],
    "injection_molding": ["injection molding", "injection moulding", "spritzguss"],
    "pcb_assembly": ["pcb assembly", "smt assembly", "leiterplattenbestückung", "smd-bestückung"],
    "cable_harness": ["cable harness", "wire harness", "kabelkonfektion", "kabelbaum"],
    "forging": ["forging", "drop forging", "schmieden", "gesenkschmieden"],
}
MATERIALS = {
    "aluminium": ["aluminium", "aluminum", "alu"],
    "stainless_steel": ["stainless steel", "edelstahl", "1.4404", "316l"],
    "carbon_steel": ["carbon steel", "s235", "baustahl", "stahl"],
    "abs": ["abs"],
    "pa66": ["pa66", "polyamide", "polyamid"],
    "copper": ["copper", "kupfer"],
}
CERTS = {
    "ISO 9001": ["iso 9001"],
    "IATF 16949": ["iatf 16949"],
    "ISO 13485": ["iso 13485"],
    "AS9100": ["as9100", "en 9100"],
    "ISO 14001": ["iso 14001"],
}
EU = {"DE", "PL", "CZ", "IT", "PT", "AT", "HU", "FR", "ES", "NL"}
COUNTRIES = sorted(EU | {"TR", "CN", "IN", "US"})

# Words that say a company does not make the part itself. A page can avoid all of them.
DISTRIBUTOR_WORDS = [
    "distributor",
    "we distribute",
    "trading company",
    "händler",
    "vertrieb von",
    "großhandel",
    "authorised reseller",
    "reseller",
]
# A manufacturer claim needs a sentence like these on the page; without one a person checks.
PRODUCTION_WORDS = [
    "manufacturer",
    "in-house production",
    "own production",
    "we produce",
    "hersteller",
    "eigener fertigung",
    "eigene fertigung",
    "wir fertigen",
]
EXPIRY_WORDS = ["expired", "abgelaufen", "no longer certified", "nicht mehr zertifiziert"]
DISCONTINUED_WORDS = ["no longer offer", "discontinued", "nicht mehr an", "eingestellt"]


def terms(kind: dict[str, list[str]], key: str) -> list[str]:
    return kind[key]
