"""
PI / ISA-88 domain synonym dictionary.

Designed for upstream oil-and-gas AF hierarchies.  Each key is a canonical
concept; its value list contains all aliases that should match it during
query expansion and attribute resolution.
"""

from __future__ import annotations

from typing import Dict, List, Set

# --------------------------------------------------------------------------- #
# Canonical term → aliases mapping
# --------------------------------------------------------------------------- #

DOMAIN_SYNONYMS: Dict[str, List[str]] = {
    # ---- Process parameters ------------------------------------------------
    "temperature": [
        "temp", "ti", "tt", "te", "temperature", "thermal", "heat",
        "degc", "degf", "°c", "°f", "kelvin", "inlet temp", "outlet temp",
        "skin temp", "process temp",
    ],
    "pressure": [
        "pres", "press", "pi", "pt", "pe", "pressure", "psi", "barg", "bara",
        "bar", "kpa", "mpa", "psig", "psia", "differential pressure",
        "dp", "dpressure", "suction pressure", "discharge pressure",
        "inlet pressure", "outlet pressure",
    ],
    "flow": [
        "flow", "flow_rate", "flowrate", "fi", "ft", "fe", "fr",
        "m3/h", "m3h", "gpm", "lpm", "mmscfd", "scfd", "scf",
        "volumetric flow", "mass flow", "mfi", "mft",
        "gas flow", "liquid flow", "oil flow",
    ],
    "level": [
        "level", "li", "lt", "le", "lvl", "liq level",
        "liquid level", "interface level", "meter",
        "% level", "% full",
    ],
    "vibration": [
        "vibration", "vibr", "vib", "vt", "vi", "mm/s", "mms",
        "velocity", "acceleration", "displacement",
        "shaft vibration", "bearing vibration",
    ],
    "speed": [
        "speed", "rpm", "rev/min", "rotation", "rotational speed",
        "shaft speed", "motor speed", "compressor speed",
    ],
    "power": [
        "power", "watt", "kw", "mw", "kva", "mva",
        "active power", "reactive power", "apparent power",
        "motor power", "shaft power", "brake power",
    ],
    "current": [
        "current", "amps", "amp", "ampere", "ma",
        "motor current", "electrical current",
    ],
    "voltage": [
        "voltage", "volt", "v", "kv", "mv",
        "supply voltage", "motor voltage",
    ],
    "efficiency": [
        "efficiency", "eff", "η", "eta",
        "isentropic efficiency", "adiabatic efficiency",
        "polytropic efficiency", "mechanical efficiency",
        "thermal efficiency", "overall efficiency",
    ],
    "health": [
        "health", "healthscore", "health score", "condition",
        "reliability", "asset health", "equipment health",
        "rul", "remaining useful life",
    ],
    "status": [
        "status", "state", "running", "stopped", "trip",
        "alarm", "fault", "online", "offline", "mode",
        "operating", "standby",
    ],
    "production": [
        "production", "output", "throughput", "yield",
        "gas production", "oil production", "liquid production",
        "gross production", "net production",
        "mmscfd", "bbl/d", "stb/d", "ton/d",
    ],
    "position": [
        "position", "pos", "opening", "travel",
        "valve position", "valve opening", "stroke",
    ],
    "torque": [
        "torque", "nm", "ft-lb",
        "shaft torque", "motor torque",
    ],
    "density": [
        "density", "sg", "specific gravity", "api gravity",
        "kg/m3", "lb/ft3",
    ],
    "humidity": [
        "humidity", "rh", "relative humidity", "moisture",
        "dew point", "dewpoint", "water content",
    ],

    # ---- Equipment types ---------------------------------------------------
    "separator": [
        "separator", "sep", "separator vessel",
        "gas sep", "gas separator",
        "hp sep", "hp separator",
        "lp sep", "lp separator",
        "test sep", "test separator",
        "3-phase sep", "3 phase separator",
        "scrubber",
    ],
    "compressor": [
        "compressor", "comp", "k-", "c-",
        "gas compressor", "reciprocating compressor",
        "centrifugal compressor", "screw compressor",
        "compression",
    ],
    "pump": [
        "pump", "p-", "centrifugal pump", "injection pump",
        "transfer pump", "booster pump", "submersible pump",
    ],
    "heat_exchanger": [
        "heat exchanger", "hx", "exchanger", "cooler",
        "aftercooler", "intercooler", "air cooler", "ace",
        "plate exchanger", "shell and tube",
    ],
    "vessel": [
        "vessel", "v-", "drum", "flash drum",
        "slug catcher", "buffer vessel", "storage vessel",
        "accumulator",
    ],
    "valve": [
        "valve", "pv", "fv", "lcv", "pcv", "tv", "hv",
        "control valve", "pressure control valve",
        "flow control valve", "level control valve",
        "shutdown valve", "sdv", "isolation valve",
    ],
    "filter": [
        "filter", "strainer", "coalescer",
        "gas filter", "liquid filter",
    ],
    "metering": [
        "metering", "meter", "flow meter", "fiscal meter",
        "custody transfer", "orifice plate",
        "coriolis", "ultrasonic meter",
    ],

    # ---- Hierarchy / plant structure ---------------------------------------
    "train": [
        "train", "unit", "processing train", "production train",
        "train 1", "train 2", "train 3", "t1", "t2", "t3",
    ],
    "plant": [
        "plant", "facility", "complex", "site",
        "processing plant", "gas plant",
    ],
    "upstream": [
        "upstream", "inlet", "suction", "feed", "incoming",
    ],
    "downstream": [
        "downstream", "outlet", "discharge", "export", "delivery",
    ],

    # ---- Performance / condition -------------------------------------------
    "low": [
        "low", "below", "under", "below target", "underperforming",
        "trip low", "alarm low", "ll", "lll",
    ],
    "high": [
        "high", "above", "over", "above target",
        "trip high", "alarm high", "hh", "hhh",
    ],
    "normal": [
        "normal", "ok", "healthy", "good", "nominal",
        "within range", "on target",
    ],
    "abnormal": [
        "abnormal", "fault", "anomaly", "deviation",
        "out of range", "degraded", "alarm",
    ],
}

# --------------------------------------------------------------------------- #
# Reverse lookup: alias → canonical
# --------------------------------------------------------------------------- #

_REVERSE: Dict[str, str] = {}
for canonical, aliases in DOMAIN_SYNONYMS.items():
    _REVERSE[canonical.lower()] = canonical
    for alias in aliases:
        _REVERSE[alias.lower()] = canonical


def expand_query(query: str) -> str:
    """
    Return an expanded version of query where recognised terms are
    supplemented with their aliases, joined into a single string for
    BM25 / vector retrieval.
    """
    tokens = query.lower().split()
    extra: Set[str] = set()
    for token in tokens:
        canonical = _REVERSE.get(token)
        if canonical:
            extra.update(DOMAIN_SYNONYMS[canonical])
    if extra:
        return query + " " + " ".join(extra - set(tokens))
    return query


def canonicalise(term: str) -> str:
    """Map any alias back to its canonical form, or return the original."""
    return _REVERSE.get(term.lower(), term)


def get_aliases(term: str) -> List[str]:
    """Return all aliases for a term (including aliases of its canonical form)."""
    canonical = _REVERSE.get(term.lower(), term.lower())
    return DOMAIN_SYNONYMS.get(canonical, [term])


def get_measurement_type(attr_name: str) -> str:
    """
    Infer the measurement category of a PI attribute by scanning its name
    against known aliases.  Returns the canonical category or 'other'.
    """
    lower = attr_name.lower()
    for alias, canonical in _REVERSE.items():
        if alias in lower:
            return canonical
    return "other"
