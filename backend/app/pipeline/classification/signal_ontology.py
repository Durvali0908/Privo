"""
app/pipeline/classification/signal_ontology.py

Defines Privo's signal ontology:
    SignalType       → the named signal a detection represents
    SignalCategory   → which exposure category the signal serves
    ClassificationRule → maps a detection pattern to a SignalType

This is the knowledge layer. The engine in signal_classification.py
applies these rules. Changing exposure logic means changing rules here,
not touching the engine.
"""

from enum import Enum
from typing import Optional
from dataclasses import dataclass


class SignalType(str, Enum):
    """
    Named privacy signals that Privo can identify.
    A signal is a semantic interpretation of one or more detections.
    """
    # Identity signals
    FACE_VISIBLE        = "face_visible"
    MULTIPLE_FACES      = "multiple_faces"

    # Contact signals
    QR_URL              = "qr_url"
    QR_CONTACT          = "qr_contact"          # vCard / MATMSG
    QR_GENERIC          = "qr_generic"

    # Document signals
    INDIAN_ID_AADHAAR   = "indian_id_aadhaar"
    INDIAN_ID_PAN       = "indian_id_pan"
    PASSPORT_INDICATOR  = "passport_indicator"
    GENERIC_DOCUMENT    = "generic_document"

    # Financial signals
    FINANCIAL_INDICATOR = "financial_indicator"  # currency symbols / amounts

    # Activity signals
    TEXT_PRESENT        = "text_present"         # generic text region

    # Child safety signals
    CHILD_FACE_INDICATOR = "child_face_indicator"  # future: age estimation


class SignalCategory(str, Enum):
    """Maps signals to Privo's official exposure categories."""
    IDENTITY    = "identity_exposure"
    CONTACT     = "contact_exposure"
    DOCUMENT    = "document_exposure"
    FINANCIAL   = "financial_exposure"
    ACTIVITY    = "activity_exposure"
    CHILD       = "child_safety_exposure"


# Maps each SignalType to its exposure category
SIGNAL_CATEGORY_MAP: dict[SignalType, SignalCategory] = {
    SignalType.FACE_VISIBLE:         SignalCategory.IDENTITY,
    SignalType.MULTIPLE_FACES:       SignalCategory.IDENTITY,
    SignalType.QR_URL:               SignalCategory.CONTACT,
    SignalType.QR_CONTACT:           SignalCategory.CONTACT,
    SignalType.QR_GENERIC:           SignalCategory.CONTACT,
    SignalType.INDIAN_ID_AADHAAR:    SignalCategory.DOCUMENT,
    SignalType.INDIAN_ID_PAN:        SignalCategory.DOCUMENT,
    SignalType.PASSPORT_INDICATOR:   SignalCategory.DOCUMENT,
    SignalType.GENERIC_DOCUMENT:     SignalCategory.DOCUMENT,
    SignalType.FINANCIAL_INDICATOR:  SignalCategory.FINANCIAL,
    SignalType.TEXT_PRESENT:         SignalCategory.ACTIVITY,
    SignalType.CHILD_FACE_INDICATOR: SignalCategory.CHILD,
}


@dataclass
class ClassificationRule:
    """
    A single rule that maps a detection pattern to a SignalType.

    field     : which DetectedRegion field to inspect
                "region_type" | "content"
    pattern   : exact string or substring to match (case-insensitive)
    signal    : the SignalType to assign when the rule matches
    partial   : if True, match as substring; if False, exact match
    """
    field:   str
    pattern: str
    signal:  SignalType
    partial: bool = True


# ─────────────────────────────────────────────────────────────────
# CLASSIFICATION RULES
# Applied in order — first match wins for content-based rules.
# Region-type rules (face, qr_code, text) are always applied first.
# ─────────────────────────────────────────────────────────────────

# Indian document patterns
# Based on publicly known format structures — no real PII used.
AADHAAR_PATTERNS = [
    "aadhaar", "aadhar", "uid", "uidai",
    "unique identification", "भारत",         # Hindi: India
    "government of india",
]
# 12-digit Aadhaar number pattern checked separately via regex in engine.

PAN_PATTERNS = [
    "permanent account", "pan card", "income tax",
    "आयकर",              # Hindi: income tax
]
# PAN format: 5 letters + 4 digits + 1 letter — checked via regex in engine.

PASSPORT_PATTERNS = [
    "passport", "republic of india", "ministry of external",
    "surname", "nationality", "date of birth", "place of birth",
]

FINANCIAL_PATTERNS = [
    "₹", "inr", "account no", "account number", "ifsc",
    "bank", "credit card", "debit card", "cvv", "upi",
    "gpay", "phonepe", "paytm",
]

QR_URL_PREFIXES = ["http://", "https://", "www."]
QR_CONTACT_PREFIXES = ["begin:vcard", "matmsg:", "mailto:", "tel:"]