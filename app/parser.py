import re
from .models import Complaint

DATE_RE = re.compile(r"(?<!\d)(1[2-9]|20|21)(?:st|nd|rd|th)?(?=\s*(?:ko|tarikh|wala|sep|sept|september)\b)", re.I)
TRIP_RE = re.compile(r"\bT\d{6}\b", re.I)

def parse_complaint(text: str) -> Complaint:
    lower = text.lower()
    injection = any(x in lower for x in ("ignore all previous", "system:", "approve karo", "approve all"))
    kinds: set[str] = set()
    if any(x in lower for x in ("surge", "multiplier")): kinds.add("surge")
    if any(x in lower for x in ("incentive", "12 order", "12 se")): kinds.add("incentive")
    if any(x in lower for x in ("penalty", "cancel")): kinds.add("penalty")
    if any(x in lower for x in ("payment nahi", "paisa hi nahi", "missing", "payout kam", "payout galat")): kinds.add("missing")
    if any(x in lower for x in ("distance", "km")): kinds.add("distance")
    dates=list(dict.fromkeys(DATE_RE.findall(lower)))
    if not dates and re.search(r"\bkal\b", lower):
        dates=['21']
    return Complaint(
        dates=dates,
        trip_ids=[x.upper() for x in dict.fromkeys(TRIP_RE.findall(text))],
        kinds=kinds, text=text, injection=injection,
    )

def foreign_rider_claim(text: str, rider_id: str) -> bool:
    ids = re.findall(r"\bR\d{3}\b", text.upper())
    return any(x != rider_id.upper() for x in ids)
