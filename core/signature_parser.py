from dataclasses import dataclass
from typing import List


@dataclass
class SignatureParseResult:
    signer_status: str
    signature_detail: str
    publisher: str


def _score_decoded_text(text: str) -> float:
    if not text:
        return float("-inf")
    length = len(text)
    replacement = text.count("\ufffd")
    null_chars = text.count("\x00")
    control_chars = sum(1 for ch in text if ord(ch) < 32 and ch not in "\r\n\t")
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\r\n\t")
    printable_ratio = printable / max(length, 1)
    return (
        printable_ratio * 1000
        - replacement * 60
        - null_chars * 100
        - control_chars * 20
    )


def decode_sigcheck_bytes(data: bytes, preferred_encoding: str = "") -> str:
    """Decode sigcheck raw output with best-effort multi-encoding fallback."""
    if not data:
        return ""

    candidates: List[str] = []
    if preferred_encoding:
        candidates.append(preferred_encoding)

    # UTF-16 often appears in redirected Windows CLI output.
    if b"\x00" in data:
        candidates.extend(["utf-16le", "utf-16", "utf-16be"])

    candidates.extend(
        [
            "utf-8-sig",
            "utf-8",
            "gb18030",
            "gbk",
            "cp936",
            "mbcs",
            "cp1252",
            "latin-1",
        ]
    )

    # Keep order and deduplicate.
    seen = set()
    encodings = []
    for enc in candidates:
        key = (enc or "").strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        encodings.append(enc)

    best_text = ""
    best_score = float("-inf")

    for encoding in encodings:
        try:
            text = data.decode(encoding, errors="strict")
            score = _score_decoded_text(text)
            if score > best_score:
                best_score = score
                best_text = text
        except (LookupError, UnicodeDecodeError):
            continue

    if best_text:
        return best_text.replace("\r\n", "\n").strip("\ufeff").strip()

    # Final fallback
    fallback = data.decode("utf-8", errors="replace")
    return fallback.replace("\r\n", "\n").strip("\ufeff").strip()


def parse_sigcheck_output(output: str) -> SignatureParseResult:
    """Parse sigcheck output into UI-friendly signature fields."""
    text = (output or "").strip()
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    verified_value = ""
    signer_line = ""
    for line in lines:
        lower = line.lower()
        if not verified_value and lower.startswith("verified:"):
            parts = line.split(":", 1)
            verified_value = parts[1].strip().lower() if len(parts) == 2 else ""
        if not signer_line and ("signed by" in lower or lower.startswith("signer:")):
            signer_line = line

    publisher = ""
    if ":" in signer_line:
        publisher = signer_line.split(":", 1)[1].strip()

    detail = signer_line or (f"Verified: {verified_value}" if verified_value else "")

    if verified_value:
        if any(token in verified_value for token in ("signed", "catalog", "valid", "yes")):
            return SignatureParseResult("(Verified)", detail, publisher)
        if any(token in verified_value for token in ("unsigned", "n/a", "no")):
            return SignatureParseResult("(Unsigned)", detail, publisher)
        if any(token in verified_value for token in ("error", "failed", "revoked", "expired")):
            return SignatureParseResult("(Error)", detail or text, publisher)

    output_lower = text.lower()
    if "error" in output_lower or "failed" in output_lower:
        return SignatureParseResult("(Error)", text, publisher)
    if "unsigned" in output_lower:
        return SignatureParseResult("(Unsigned)", detail, publisher)
    if "signed" in output_lower and "verified" in output_lower:
        return SignatureParseResult("(Verified)", detail, publisher)

    return SignatureParseResult("(Unsigned)", detail, publisher)
