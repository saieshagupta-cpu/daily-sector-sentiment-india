"""Indian ticker resolver — built from our 240-name config pool.

Unlike the US version which pulls all 5,461 US listings from Finnhub, this
keeps the universe scoped to the 60 Big Names + 180 New Names we curate.
That's enough for the dashboard's purpose (resolving headline → ticker for
names in our portfolio).

Cashtags ($RELIANCE) and company-name matches both supported.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from config.settings import CANDIDATES, UNIVERSE, CONFIG_DIR


# Manually-curated short names / aliases that Indian press commonly uses.
# Each ticker can have multiple search names — all get added to the name index.
EXTRA_ALIASES: dict[str, list[str]] = {
    "RELIANCE":   ["Reliance Industries", "Reliance", "RIL"],
    "ONGC":       ["ONGC", "Oil and Natural Gas"],
    "SUNPHARMA":  ["Sun Pharma", "Sun Pharmaceutical"],
    "DRREDDY":    ["Dr Reddy", "Dr. Reddy", "Dr. Reddy's", "Dr Reddys"],
    "ADANIGREEN": ["Adani Green", "Adani Green Energy"],
    "ADANIPOWER": ["Adani Power"],
    "ADANIENSOL": ["Adani Energy Solutions", "Adani Transmission"],
    "TATASTEEL":  ["Tata Steel"],
    "TATAPOWER":  ["Tata Power"],
    "TATACHEM":   ["Tata Chemicals"],
    "TATATECH":   ["Tata Technologies"],
    "TATAELXSI":  ["Tata Elxsi"],
    "JSWSTEEL":   ["JSW Steel"],
    "JSWENERGY":  ["JSW Energy"],
    "JSL":        ["Jindal Stainless"],
    "JINDALSTEL": ["Jindal Steel", "Jindal Steel and Power"],
    "HINDALCO":   ["Hindalco"],
    "HINDZINC":   ["Hindustan Zinc"],
    "HINDCOPPER": ["Hindustan Copper"],
    "HINDPETRO":  ["HPCL", "Hindustan Petroleum"],
    "NATIONALUM": ["NALCO", "National Aluminium"],
    "HDFCBANK":   ["HDFC Bank"],
    "HDFCLIFE":   ["HDFC Life"],
    "HDFCAMC":    ["HDFC Asset Management", "HDFC AMC"],
    "ICICIBANK":  ["ICICI Bank"],
    "ICICIGI":    ["ICICI Lombard"],
    "ICICIPRULI": ["ICICI Prudential"],
    "KOTAKBANK":  ["Kotak Mahindra Bank", "Kotak Bank"],
    "AXISBANK":   ["Axis Bank"],
    "SBIN":       ["SBI", "State Bank of India", "State Bank"],
    "SBILIFE":    ["SBI Life"],
    "SBICARD":    ["SBI Cards", "SBI Card"],
    "BAJFINANCE": ["Bajaj Finance"],
    "BAJAJFINSV": ["Bajaj Finserv"],
    "BAJAJHLDNG": ["Bajaj Holdings"],
    "IDFCFIRSTB": ["IDFC First Bank"],
    "INDUSINDBK": ["IndusInd Bank"],
    "FEDERALBNK": ["Federal Bank"],
    "BANDHANBNK": ["Bandhan Bank"],
    "AUBANK":     ["AU Small Finance Bank", "AU Bank"],
    "DLF":        ["DLF"],
    "GODREJPROP": ["Godrej Properties"],
    "OBEROIRLTY": ["Oberoi Realty"],
    "PRESTIGE":   ["Prestige Estates", "Prestige Group"],
    "LODHA":      ["Lodha", "Macrotech Developers"],
    "PHOENIXLTD": ["Phoenix Mills"],
    "BRIGADE":    ["Brigade Enterprises"],
    "MAHLIFE":    ["Mahindra Lifespace"],
    "INFY":       ["Infosys"],
    "WIPRO":      ["Wipro"],
    "HCLTECH":    ["HCL Tech", "HCL Technologies"],
    "TECHM":      ["Tech Mahindra"],
    "LTIM":       ["LTIMindtree", "LTI Mindtree"],
    "MPHASIS":    ["Mphasis"],
    "PERSISTENT": ["Persistent Systems"],
    "COFORGE":    ["Coforge"],
    "TCS":        ["TCS", "Tata Consultancy Services"],
    "LAURUSLABS": ["Laurus Labs"],
    "GLENMARK":   ["Glenmark"],
    "BIOCON":     ["Biocon"],
    "LUPIN":      ["Lupin"],
    "MANKIND":    ["Mankind Pharma"],
    "DIVISLAB":   ["Divis Lab", "Divi's Lab", "Divi's Laboratories"],
    "TORNTPHARM": ["Torrent Pharma"],
    "TORNTPOWER": ["Torrent Power"],
    "APOLLOHOSP": ["Apollo Hospitals"],
    "MAXHEALTH":  ["Max Healthcare"],
    "FORTIS":     ["Fortis Healthcare"],
    "GAIL":       ["GAIL"],
    "IOC":        ["Indian Oil"],
    "BPCL":       ["BPCL", "Bharat Petroleum"],
    "NTPC":       ["NTPC"],
    "POWERGRID":  ["Power Grid"],
    "COALINDIA":  ["Coal India"],
    "SAIL":       ["SAIL", "Steel Authority"],
    "NMDC":       ["NMDC"],
    "VEDL":       ["Vedanta"],
    "SUZLON":     ["Suzlon"],
    "IREDA":      ["IREDA"],
    "ZOMATO":     ["Zomato", "Eternal"],
    "PAYTM":      ["Paytm", "One 97"],
    "POLICYBZR":  ["Policybazaar", "PB Fintech"],
    "NYKAA":      ["Nykaa", "FSN E-Commerce"],
    "NAUKRI":     ["Info Edge", "Naukri"],
    "BSE":        ["BSE Limited", "Bombay Stock Exchange"],
    "MCX":        ["MCX", "Multi Commodity Exchange"],
    "ANGELONE":   ["Angel One", "Angel Broking"],
    "MUTHOOTFIN": ["Muthoot Finance"],
    "MANAPPURAM": ["Manappuram Finance"],
    "CHOLAFIN":   ["Cholamandalam"],
    "BAJFINANCE": ["Bajaj Finance"],
    "LICI":       ["LIC", "Life Insurance Corporation"],
    "INDHOTEL":   ["Indian Hotels", "Taj Hotels"],
    "LEMONTREE":  ["Lemon Tree Hotels"],
    "EIHOTEL":    ["EIH", "Oberoi Hotels"],
    "RVNL":       ["Rail Vikas Nigam", "RVNL"],
    "RAILTEL":    ["RailTel"],
    "IRCON":      ["Ircon"],
    "IRFC":       ["Indian Railway Finance"],
    "IRB":        ["IRB Infrastructure"],
    "PFC":        ["Power Finance"],
    "RECLTD":     ["REC Limited"],
    # --- Defense ---
    "HAL":        ["Hindustan Aeronautics", "HAL"],
    "BEL":        ["Bharat Electronics", "BEL"],
    "BDL":        ["Bharat Dynamics", "BDL"],
    "MAZDOCK":    ["Mazagon Dock", "Mazagon Dock Shipbuilders"],
    "COCHINSHIP": ["Cochin Shipyard"],
    "GRSE":       ["Garden Reach Shipbuilders", "GRSE"],
    "BEML":       ["BEML"],
    "MIDHANI":    ["Mishra Dhatu Nigam", "MIDHANI"],
    "SOLARINDS":  ["Solar Industries"],
    "LT":         ["Larsen & Toubro", "L&T", "Larsen and Toubro"],
    "PARAS":      ["Paras Defence", "Paras Defense"],
    "ZENTEC":     ["Zen Technologies"],
    "DCXINDIA":   ["DCX Systems"],
    "ASTRAMICRO": ["Astra Microwave"],
    "MTARTECH":   ["MTAR Technologies"],
    "AZAD":       ["Azad Engineering"],
    "IDEAFORGE":  ["ideaForge", "Idea Forge"],
    "HBLPOWER":   ["HBL Power Systems"],
    "WALCHANDIN": ["Walchandnagar Industries"],
    "TANEJAERO":  ["Taneja Aerospace"],
    "TEXMACO":    ["Texmaco Rail"],
    "TITAGARH":   ["Titagarh Rail", "Titagarh Wagons"],
    "BHARATFORG": ["Bharat Forge"],
    "BHEL":       ["Bharat Heavy Electricals", "BHEL"],
    "SANSERA":    ["Sansera Engineering"],
    "KIRLOSENG":  ["Kirloskar Oil Engines"],
    "PRECAM":     ["Precision Camshafts"],
    "THERMAX":    ["Thermax"],
    "TIMKEN":     ["Timken India"],
    "SCHAEFFLER": ["Schaeffler India"],
    "GRINDWELL":  ["Grindwell Norton"],
    "PREMEXPLN":  ["Premier Explosives"],
    "GOCLCORP":   ["GOCL Corporation"],
    # --- Utilities ---
    "NHPC":       ["NHPC"],
    "SJVN":       ["SJVN"],
    "TORNTPOWER": ["Torrent Power"],
    "IGL":        ["Indraprastha Gas", "IGL"],
    "MGL":        ["Mahanagar Gas"],
    "GUJGASLTD":  ["Gujarat Gas"],
    "GSPL":       ["Gujarat State Petronet"],
    "ATGL":       ["Adani Total Gas"],
    "CESC":       ["CESC Limited"],
    "NLCINDIA":   ["NLC India", "Neyveli Lignite"],
    "IRCTC":      ["IRCTC", "Indian Railway Catering"],
    "VATECHWABAG":["VA Tech Wabag"],
    "IEX":        ["Indian Energy Exchange"],
    "PRAJIND":    ["Praj Industries"],
    "KEC":        ["KEC International"],
    "INOXWIND":   ["Inox Wind"],
    "KPIGREEN":   ["KPI Green Energy"],
    "PREMIERENE": ["Premier Energies"],
    "ACMESOLAR":  ["ACME Solar"],
    "WAAREE":     ["Waaree", "Waaree Energies"],
    # --- FMCG ---
    "HINDUNILVR": ["Hindustan Unilever", "HUL"],
    "ITC":        ["ITC Limited", "ITC"],
    "NESTLEIND":  ["Nestle India", "Nestle"],
    "BRITANNIA":  ["Britannia Industries", "Britannia"],
    "DABUR":      ["Dabur India", "Dabur"],
    "COLPAL":     ["Colgate India", "Colgate Palmolive India"],
    "GODREJCP":   ["Godrej Consumer Products", "Godrej Consumer"],
    "MARICO":     ["Marico"],
    "VBL":        ["Varun Beverages"],
    "TATACONSUM": ["Tata Consumer Products", "Tata Consumer"],
    "EMAMILTD":   ["Emami"],
    "BAJAJCON":   ["Bajaj Consumer"],
    "JYOTHYLAB":  ["Jyothy Labs"],
    "GILLETTE":   ["Gillette India"],
    "HONASA":     ["Honasa Consumer", "Mamaearth"],
    "ZYDUSWELL":  ["Zydus Wellness"],
    "UNITDSPR":   ["United Spirits", "McDowell"],
    "UBL":        ["United Breweries"],
    "RADICO":     ["Radico Khaitan"],
    "METROBRAND": ["Metro Brands"],
    "RELAXO":     ["Relaxo Footwears"],
    "BATA":       ["Bata India"],
    "PAGEIND":    ["Page Industries"],
    "TRENT":      ["Trent"],
    "DMART":      ["Avenue Supermarts", "DMart"],
    "ABFRL":      ["Aditya Birla Fashion"],
    "HAVELLS":    ["Havells India", "Havells"],
    "TITAN":      ["Titan Company", "Titan"],
    "PIDILITIND": ["Pidilite Industries"],
    "ASIANPAINT": ["Asian Paints"],
    "BERGEPAINT": ["Berger Paints"],
    "KANSAINER":  ["Kansai Nerolac"],
    "PGHH":       ["P&G Hygiene", "Procter & Gamble Hygiene"],
}


CASHTAG_RE = re.compile(r"\$([A-Z][A-Z0-9]{1,15})\b")

# Single-word company names that match too aggressively. Cashtag form still works.
GENERIC_NAME_BLOCKLIST = {
    "NEWS", "BLOCK", "DATA", "POWER", "ENERGY", "BANK", "TRUST", "CAPITAL",
    "GROWTH", "INCOME", "GLOBAL", "STATE", "FIRST", "UNITED", "NATIONAL",
    "GENERAL", "AMERICAN", "INTERNATIONAL", "COMMUNITY", "STANDARD",
    "DIRECT", "PRIME", "OPEN", "CORE", "FREE", "REAL", "GOOD", "PURE",
    "SIMPLE", "MARKET", "SQUARE", "SOLO", "ONE", "MEDIA", "VITAL",
    "ELITE", "TODAY", "TOMORROW", "FUTURE", "SAFE", "SMART", "BRIGHT",
    "STRONG", "HERE", "POST", "WORLD", "FACT", "POINT", "PATH", "WAVE",
    "EDGE", "DRIVE", "PEAK", "RISE", "GAIN", "LEAP", "BOLD", "PIVOT",
    "FOCUS", "INDIA", "RAIL", "DLF",
}


@lru_cache(maxsize=1)
def get_universe() -> dict[str, dict]:
    """Return {ticker: {name, ...}} built from universe.yaml + candidates.yaml.

    Shape mirrors the US-version's resolver for downstream compatibility.
    """
    out: dict[str, dict] = {}
    for sec_rows in UNIVERSE.values():
        for row in sec_rows:
            out[row["ticker"]] = {
                "name": row.get("name", row["ticker"]),
                "description": row.get("name", row["ticker"]),
                "exchange": "XNSE",
                "type": "Common Stock",
            }
    for sec_tickers in CANDIDATES.values():
        for t in sec_tickers:
            out.setdefault(t, {
                "name": t,
                "description": t,
                "exchange": "XNSE",
                "type": "Common Stock",
            })
    return out


@lru_cache(maxsize=1)
def _name_index() -> list[tuple[re.Pattern, str]]:
    """Sorted regex list (longest first) for name-based matching.

    Each ticker contributes:
    - its full yaml name (if any)
    - all EXTRA_ALIASES entries
    - the bare ticker symbol itself (case-insensitive word match)
    """
    universe = get_universe()
    entries: list[tuple[str, str]] = []
    for ticker, info in universe.items():
        seen: set[str] = set()
        yaml_name = (info.get("name") or "").strip()
        if yaml_name and yaml_name.upper() != ticker:
            seen.add(yaml_name)
        for alias in EXTRA_ALIASES.get(ticker, []):
            seen.add(alias)
        # Also accept the bare ticker as a match (e.g. "RELIANCE", "TCS")
        if len(ticker) >= 3 and ticker not in GENERIC_NAME_BLOCKLIST:
            seen.add(ticker)
        for name in seen:
            if not name or len(name) < 3:
                continue
            if " " not in name and name.upper() in GENERIC_NAME_BLOCKLIST:
                continue
            entries.append((name, ticker))
    entries.sort(key=lambda x: len(x[0]), reverse=True)
    return [
        (re.compile(rf"(?<![\w]){re.escape(name)}(?![\w])", re.IGNORECASE), tk)
        for name, tk in entries
    ]


def extract_cashtags(text: str) -> set[str]:
    universe = get_universe()
    found = {m.group(1).upper() for m in CASHTAG_RE.finditer(text or "")}
    return {t for t in found if t in universe}


def extract_by_name(text: str, max_matches: int = 5) -> set[str]:
    if not text:
        return set()
    matched: set[str] = set()
    covered: list[tuple[int, int]] = []

    def overlaps(span: tuple[int, int]) -> bool:
        s, e = span
        return any(s < ce and cs < e for cs, ce in covered)

    for pattern, ticker in _name_index():
        if len(matched) >= max_matches:
            break
        m = pattern.search(text)
        if not m:
            continue
        if overlaps(m.span()):
            continue
        matched.add(ticker)
        covered.append(m.span())
    return matched


def extract_tickers(text: str) -> set[str]:
    return extract_cashtags(text) | extract_by_name(text)
