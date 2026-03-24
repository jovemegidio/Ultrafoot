

# -*- coding: utf-8 -*-
"""Download real flag PNG images from flagcdn.com for all game country codes."""
import os
import urllib.request
import ssl
import time

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAGS_DI
R = os.path.join(BASE, "data", "assets", "flags")

# Mapping: game country code -> ISO 3166-1 alpha-2 (lowercase)
CODE_MAP = {
    "AFG": "af",  # Afeganistão
    "AFS": "za",  # África do Sul
    "AGO": "ao",  # Angola
    "ALE": "de",  # Alemanha
    "ALB": "al",  # Albânia
    "ALG": "dz",  # Argélia
    "AND": "ad",  # Andorra
    "ARG": "ar",  # Argentina
    "ARM": "am",  # Armênia
    "ARS": "sa",  # Arábia Saudita
    "ARU": "aw",  # Aruba
    "AUS": "au",  # Austrália
    "AUT": "at",  # Áustria
    "AZE": "az",  # Azerbaijão
    "BAH": "bs",  # Bahamas
    "BAN": "bd",  # Bangladesh
    "BAR": "bb",  # Barbados
    "BEL": "be",  # Bélgica
    "BEN": "bj",  # Benim
    "BHR": "bh",  # Bahrein
    "BIE": "by",  # Bielorrússia
    "BKF": "bf",  # Burkina Faso
    "BLZ": "bz",  # Belize
    "BOL": "bo",  # Bolívia
    "BON": "bq",  # Bonaire
    "BOS": "ba",  # Bósnia
    "BOT": "bw",  # Botsuana
    "BRA": "br",  # Brasil
    "BRU": "bn",  # Brunei
    "BUL": "bg",  # Bulgária
    "BUR": "bi",  # Burundi
    "BUT": "bt",  # Butão
    "CAM": "cm",  # Camarões
    "CAN": "ca",  # Canadá
    "CAT": "qa",  # Catar
    "CAV": "cv",  # Cabo Verde
    "CAZ": "kz",  # Cazaquistão
    "CHA": "td",  # Chade
    "CHI": "cl",  # Chile
    "CHN": "cn",  # China
    "CMJ": "kh",  # Camboja
    "CNG": "cg",  # Congo
    "COL": "co",  # Colômbia
    "COM": "km",  # Comores
    "CPR": "cy",  # Chipre
    "CRN": "me",  # Montenegro (Crna Gora)
    "CRO": "hr",  # Croácia
    "CRS": "cr",  # Costa Rica
    "CUB": "cu",  # Cuba
    "CUR": "cw",  # Curaçao
    "DIN": "dk",  # Dinamarca
    "DJI": "dj",  # Djibuti
    "DOM": "do",  # Rep. Dominicana
    "EGI": "eg",  # Egito
    "ELS": "sv",  # El Salvador
    "EMI": "ae",  # Emirados
    "EQU": "ec",  # Equador
    "ERI": "er",  # Eritreia
    "ESC": "gb-sct",  # Escócia
    "ESP": "es",  # Espanha
    "ESS": "sz",  # Essuatíni
    "EST": "ee",  # Estônia
    "ETI": "et",  # Etiópia
    "EUA": "us",  # EUA
    "FIJ": "fj",  # Fiji
    "FIL": "ph",  # Filipinas
    "FIN": "fi",  # Finlândia
    "FRA": "fr",  # França
    "GAB": "ga",  # Gabão
    "GAM": "gm",  # Gâmbia
    "GAN": "gh",  # Gana
    "GDA": "gd",  # Granada
    "GEO": "ge",  # Geórgia
    "GIB": "gi",  # Gibraltar
    "GMA": "gt",  # Guatemala
    "GNB": "gw",  # Guiné-Bissau
    "GNE": "gq",  # Guiné Equatorial
    "GRE": "gr",  # Grécia
    "GUA": "gy",  # Guiana
    "GUI": "gn",  # Guiné
    "GUN": "gf",  # Guiana Francesa
    "HAI": "ht",  # Haiti
    "HKG": "hk",  # Hong Kong
    "HOL": "nl",  # Holanda
    "HON": "hn",  # Honduras
    "HUN": "hu",  # Hungria
    "ICA": "ky",  # Ilhas Cayman
    "ICO": "fo",  # Ilhas Faroé
    "IDO": "id",  # Indonésia
    "IEM": "ye",  # Iêmen
    "IND": "in",  # Índia
    "ING": "gb-eng",  # Inglaterra
    "IRA": "iq",  # Iraque
    "IRL": "ie",  # Irlanda
    "IRN": "ir",  # Irã
    "ISA": "is",  # Islândia
    "ISL": "is",  # Islândia (alt)
    "ISR": "il",  # Israel
    "ITA": "it",  # Itália
    "ITC": "vi",  # Ilhas Virgens
    "JAM": "jm",  # Jamaica
    "JAP": "jp",  # Japão
    "JOR": "jo",  # Jordânia
    "KIR": "kg",  # Quirguistão
    "KOS": "xk",  # Kosovo
    "KUW": "kw",  # Kuwait
    "LAO": "la",  # Laos
    "LBN": "lb",  # Líbano
    "LES": "ls",  # Lesoto
    "LET": "lv",  # Letônia
    "LIB": "ly",  # Líbia
    "LIE": "li",  # Liechtenstein
    "LIT": "lt",  # Lituânia
    "LRI": "lr",  # Libéria
    "LUX": "lu",  # Luxemburgo
    "MAC": "mo",  # Macau
    "MAD": "mg",  # Madagascar
    "MAL": "my",  # Malásia
    "MAR": "ma",  # Marrocos
    "MAU": "mu",  # Maurício
    "MCD": "mk",  # Macedônia do Norte
    "MEX": "mx",  # México
    "MGL": "mn",  # Mongólia
    "MIA": "mm",  # Mianmar
    "MLD": "mv",  # Maldivas
    "MLI": "ml",  # Mali
    "MNC": "mc",  # Mônaco
    "MOC": "mz",  # Moçambique
    "MOL": "md",  # Moldávia
    "MON": "mn",  # Mongólia (in case of conflict, use unique)
    "MST": "ms",  # Montserrat
    "MTA": "mt",  # Malta
    "MTI": "mr",  # Mauritânia
    "MWI": "mw",  # Malawi
    "NAM": "na",  # Namíbia
    "NAU": "nr",  # Nauru
    "NCA": "nc",  # Nova Caledônia
    "NEP": "np",  # Nepal
    "NIC": "ni",  # Nicarágua
    "NIG": "ng",  # Nigéria
    "NIR": "gb-nir",  # Irlanda do Norte
    "NOR": "no",  # Noruega
    "NOZ": "nz",  # Nova Zelândia
    "OMA": "om",  # Omã
    "PAL": "ps",  # Palestina
    "PAN": "pa",  # Panamá
    "PAQ": "pk",  # Paquistão
    "PAR": "py",  # Paraguai
    "PER": "pe",  # Peru
    "PGA": "pg",  # Papua Nova Guiné
    "PLU": "pw",  # Palau
    "PNG": "pg",  # Papua Nova Guiné (alt)
    "POL": "pl",  # Polônia
    "POR": "pt",  # Portugal
    "PRI": "pr",  # Porto Rico
    "QUE": "ke",  # Quênia
    "RCA": "cf",  # Rep. Centro-Africana
    "RDG": "cd",  # RD Congo
    "RDO": "do",  # Rep. Dominicana
    "ROM": "ro",  # Romênia
    "RTC": "cz",  # Rep. Tcheca
    "RUA": "rw",  # Ruanda
    "RUS": "ru",  # Rússia
    "SAM": "ws",  # Samoa
    "SAN": "sm",  # San Marino
    "SCN": "sn",  # Senegal (alt?) -- actually Sudan do Sul?
    "SEN": "sn",  # Senegal
    "SER": "rs",  # Sérvia
    "SEY": "sc",  # Seychelles
    "SIN": "sg",  # Singapura
    "SIR": "sy",  # Síria
    "SLE": "sl",  # Serra Leoa
    "SOM": "so",  # Somália
    "SRI": "lk",  # Sri Lanka
    "STL": "lc",  # Santa Lúcia
    "STP": "st",  # São Tomé e Príncipe
    "SUD": "sd",  # Sudão
    "SUE": "se",  # Suécia
    "SUI": "ch",  # Suíça
    "SUR": "sr",  # Suriname
    "SVG": "vc",  # São Vicente e Granadinas
    "TAD": "tj",  # Tajiquistão
    "TAI": "th",  # Tailândia
    "TAN": "tz",  # Tanzânia
    "TAW": "tw",  # Taiwan
    "TCM": "tm",  # Turcomenistão
    "TML": "tl",  # Timor-Leste
    "TON": "to",  # Tonga
    "TRT": "tt",  # Trinidad e Tobago
    "TTI": "tt",  # Trinidad e Tobago (alt)
    "TUN": "tn",  # Tunísia
    "TUR": "tr",  # Turquia
    "TUV": "tv",  # Tuvalu
    "UCR": "ua",  # Ucrânia
    "UGA": "ug",  # Uganda
    "URU": "uy",  # Uruguai
    "UZB": "uz",  # Uzbequistão
    "VAN": "vu",  # Vanuatu
    "VEN": "ve",  # Venezuela
    "VIE": "vn",  # Vietnã
    "ZAM": "zm",  # Zâmbia
    "ZIM": "zw",  # Zimbábue
}

# For gb-eng, gb-sct, gb-nir, gb-wls we need special handling
# flagcdn.com supports them at: https://flagcdn.com/w80/gb-eng.png etc.

def download_flags():
    os.makedirs(FLAGS_DIR, exist_ok=True)

    ctx = ssl.create_default_context()

    total = len(CODE_MAP)
    success = 0
    failed = []

    for i, (game_code, iso2) in enumerate(sorted(CODE_MAP.items()), 1):
        dest = os.path.join(FLAGS_DIR, f"{game_code}.png")
        if os.path.exists(dest) and os.path.getsize(dest) > 100:
            print(f"[{i}/{total}] {game_code} -> already exists, skipping")
            success += 1
            continue

        url = f"https://flagcdn.com/w80/{iso2}.png"
        print(f"[{i}/{total}] {game_code} -> {url} ... ", end="", flush=True)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                data = resp.read()
            with open(dest, "wb") as f:
                f.write(data)
            print(f"OK ({len(data)} bytes)")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append((game_code, iso2, str(e)))
        time.sleep(0.1)

    print(f"\nDone: {success}/{total} flags downloaded.")
    if failed:
        print("Failed:")
        for code, iso2, err in failed:
            print(f"  {code} ({iso2}): {err}")


if __name__ == "__main__":
    download_flags()
