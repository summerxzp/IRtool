from dataclasses import dataclass


@dataclass
class SignatureParseResult:
    signer_status: str
    signature_detail: str
    publisher: str


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

