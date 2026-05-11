"""
redactor.py  –  Core redaction engine (byte-in / byte-out interface)
Consumed by main.py (FastAPI) and usable standalone.
"""

import re, io, hashlib, logging
from dataclasses import dataclass
from typing import Optional

import fitz        # PyMuPDF  (pip install pymupdf)
import spacy       # pip install spacy && python -m spacy download en_core_web_sm

log = logging.getLogger("redactor")

# ── NLP model ─────────────────────────────────────────────────────────────────
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    raise RuntimeError(
        "spaCy model missing. Run: python -m spacy download en_core_web_sm"
    )


# ── PII pattern registry ──────────────────────────────────────────────────────
@dataclass(frozen=True)
class PiiPattern:
    label: str
    pattern: re.Pattern
    keep_suffix: Optional[int] = None   # trailing DIGITS to leave visible


PII_PATTERNS: list[PiiPattern] = [
    # SIN (Canadian): 123-456-789  →  ███-███-789  (keep last 3 digits)
    PiiPattern(
        "SIN",
        re.compile(r"\b\d{3}[- ]\d{3}[- ]\d{3}\b"),
        keep_suffix=3,
    ),
    # Canadian / US phone: any format  →  ███-███-1234  (keep last 4 digits)
    PiiPattern(
        "phone",
        re.compile(
            r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]\d{3}[-.\s]\d{4}\b"
        ),
        keep_suffix=4,
    ),
    # Bank account (7–12 digits)  →  keep last 4
    PiiPattern(
        "account",
        re.compile(r"\b\d{7,12}\b"),
        keep_suffix=4,
    ),
    # Credit card (major networks)  →  keep last 4
    PiiPattern(
        "credit_card",
        re.compile(
            r"\b(?:4[0-9]{12}(?:[0-9]{3})?|"
            r"5[1-5][0-9]{14}|"
            r"3[47][0-9]{13}|"
            r"3(?:0[0-5]|[68][0-9])[0-9]{11})\b"
        ),
        keep_suffix=4,
    ),
    # Full redactions
    PiiPattern("email",   re.compile(
        r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
    )),
    PiiPattern("postal",  re.compile(r"\b[A-Z]\d[A-Z][ -]?\d[A-Z]\d\b")),
    PiiPattern("dob",     re.compile(
        r"\b(?:\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4})\b"
    )),
]

# Verification: patterns that must produce ZERO matches in the redacted output
_VERIFY_PATTERNS: list[re.Pattern] = [
    re.compile(r"\b\d{3}[- ]\d{3}[- ]\d{3}\b"),                              # full SIN
    re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"),    # email
    re.compile(r"\b[A-Z]\d[A-Z][ -]?\d[A-Z]\d\b"),                           # postal
]

REDACT_FILL = (0, 0, 0)
METADATA_FIELDS = ("author","producer","creator","title",
                   "subject","keywords","creationDate","modDate")


# ── Data types ────────────────────────────────────────────────────────────────
@dataclass
class RedactionTarget:
    page_num: int
    rect: fitz.Rect
    reason: str


class RedactionVerificationError(Exception):
    pass


# ── Character-level partial redaction ─────────────────────────────────────────
def _targets_from_match(
    page: fitz.Page,
    page_num: int,
    span: dict,
    span_text: str,
    match: re.Match,
    pii: PiiPattern,
) -> list[RedactionTarget]:
    targets: list[RedactionTarget] = []
    span_start = match.start()
    matched_str = match.group()

    matched_chars = [
        (span_start + i, ch.isdigit())
        for i, ch in enumerate(matched_str)
    ]

    if pii.keep_suffix:
        digits_seen = 0
        keep_from: Optional[int] = None
        for idx in range(len(matched_chars) - 1, -1, -1):
            if matched_chars[idx][1]:
                digits_seen += 1
            if digits_seen == pii.keep_suffix:
                keep_from = idx
                break
        if keep_from is None:
            return targets
        redact_indices = [abs_i for abs_i, _ in matched_chars[:keep_from]]
    else:
        redact_indices = [abs_i for abs_i, _ in matched_chars]

    if not redact_indices:
        return targets

    chars = span.get("chars", [])
    char_rects = [
        fitz.Rect(chars[ci]["bbox"])
        for ci in redact_indices
        if ci < len(chars)
    ]

    if not char_rects:
        # Fallback: search for full match text
        for r in page.search_for(matched_str, clip=fitz.Rect(span["bbox"])):
            targets.append(RedactionTarget(page_num, r, pii.label))
        return targets

    merged = char_rects[0]
    for r in char_rects[1:]:
        merged = merged | r
    merged = merged + (-0.5, -0.5, 0.5, 0.5)
    targets.append(RedactionTarget(page_num, merged, pii.label))
    return targets


# ── Page detection ────────────────────────────────────────────────────────────
def _find_pii_on_page(page: fitz.Page, page_num: int) -> list[RedactionTarget]:
    targets: list[RedactionTarget] = []
    blocks = page.get_text(
        "rawdict",
        flags=fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_PRESERVE_LIGATURES,
    )["blocks"]

    for block in blocks:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            for span in line["spans"]:
                span_text = "".join(c["c"] for c in span.get("chars", []))
                if not span_text.strip():
                    continue

                for pii in PII_PATTERNS:
                    for m in pii.pattern.finditer(span_text):
                        targets.extend(
                            _targets_from_match(
                                page, page_num, span, span_text, m, pii
                            )
                        )

                doc_nlp = nlp(span_text)
                for ent in doc_nlp.ents:
                    if ent.label_ in {"PERSON", "ORG", "GPE", "LOC"}:
                        for r in page.search_for(
                            ent.text, clip=fitz.Rect(span["bbox"])
                        ):
                            targets.append(
                                RedactionTarget(page_num, r, f"NLP:{ent.label_}")
                            )
    return targets


# ── Apply redactions ──────────────────────────────────────────────────────────
def _apply(doc: fitz.Document, targets: list[RedactionTarget]) -> None:
    by_page: dict[int, list[RedactionTarget]] = {}
    for t in targets:
        by_page.setdefault(t.page_num, []).append(t)

    for page_num, pts in by_page.items():
        page = doc[page_num]
        for t in pts:
            page.add_redact_annot(quad=t.rect, fill=REDACT_FILL, text="", cross_out=False)
        page.apply_redactions(
            images=fitz.PDF_REDACT_IMAGE_PIXELS,
            graphics=True,
        )


# ── Metadata scrub ────────────────────────────────────────────────────────────
def _scrub(doc: fitz.Document) -> None:
    doc.set_metadata({k: "" for k in METADATA_FIELDS})
    doc.del_xml_metadata()
    for page in doc:
        for annot in page.annots():
            if annot.type[0] != fitz.PDF_ANNOT_REDACT:
                page.delete_annot(annot)


# ── Verification ──────────────────────────────────────────────────────────────
def _verify(doc: fitz.Document) -> None:
    for pn, page in enumerate(doc):
        txt = page.get_text("text")
        for pat in _VERIFY_PATTERNS:
            hit = pat.search(txt)
            if hit:
                raise RedactionVerificationError(
                    f"Residual PII on page {pn}: {hit.group()!r}"
                )


# ── Summary builder ───────────────────────────────────────────────────────────
def _summarise(targets: list[RedactionTarget]) -> dict:
    counts: dict[str, int] = {}
    for t in targets:
        counts[t.reason] = counts.get(t.reason, 0) + 1
    counts["total"] = len(targets)
    return counts


# ── Public API ────────────────────────────────────────────────────────────────
def redact_pdf_bytes(pdf_bytes: bytes) -> tuple[bytes, dict]:
    """
    Accept raw PDF bytes, return (redacted_pdf_bytes, summary_dict).
    Raises RedactionVerificationError if verification fails after redaction.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    all_targets: list[RedactionTarget] = []
    for pn in range(len(doc)):
        all_targets.extend(_find_pii_on_page(doc[pn], pn))

    log.info("Found %d redaction targets.", len(all_targets))
    _apply(doc, all_targets)
    _scrub(doc)

    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True, linear=True, clean=True)
    doc.close()

    redacted_bytes = buf.getvalue()

    # Verify on the serialised bytes (not the in-memory doc)
    verify_doc = fitz.open(stream=redacted_bytes, filetype="pdf")
    _verify(verify_doc)
    verify_doc.close()

    return redacted_bytes, _summarise(all_targets)
