"""Deterministic email-authentication gate.

Reads the trustworthy ``Authentication-Results`` header (added by our own upstream
mail server) and decides whether the sender is authenticated, BEFORE any AI scan.

Because inbound mail is forwarded (Gmail/Outlook), SPF is rewritten to the
forwarder and is unreliable. DKIM survives forwarding, so we key on DMARC result
and DKIM *alignment* to the From domain — never SPF.

Verdicts:
- "pass"            : DMARC passed, or a DKIM signature aligns with the From domain.
- "spoofed"         : DMARC failed — the From domain has a policy and this forged it.
- "unauthenticated" : no DMARC policy AND no DKIM aligned to the From domain.
- "unknown"         : no Authentication-Results available (fail open to the AI scan).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from postal_inspector.models.email import ParsedEmail

_DMARC_RE = re.compile(r"\bdmarc=(\w+)", re.IGNORECASE)
# dkim=pass ... header.d=domain  (or header.i=@domain)
_DKIM_RE = re.compile(r"dkim=pass\b[^;]*?header\.[di]=@?([A-Za-z0-9.\-]+)", re.IGNORECASE)
_ADDR_DOMAIN_RE = re.compile(r"@([A-Za-z0-9.\-]+)")


def _org_domain(domain: str) -> str:
    """Crude registrable-domain (eTLD+1): the last two labels.

    Good enough for US-style domains (chase.com, o.sofi.org -> sofi.org). Not
    public-suffix-aware, so multi-part TLDs (e.g. co.uk) are approximate.
    """
    parts = domain.strip(". ").lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()


def _from_org_domain(from_addr: str) -> str | None:
    m = _ADDR_DOMAIN_RE.search(from_addr or "")
    return _org_domain(m.group(1)) if m else None


def authentication_verdict(email: "ParsedEmail") -> tuple[str, str]:
    """Return (status, detail). status in {pass, spoofed, unauthenticated, unknown}."""
    ar = email.auth_results or ""
    if not ar:
        return ("unknown", "no Authentication-Results header")

    dmarc = ""
    m = _DMARC_RE.search(ar)
    if m:
        dmarc = m.group(1).lower()

    if dmarc == "pass":
        return ("pass", "dmarc=pass")
    if dmarc == "fail":
        return ("spoofed", "dmarc=fail")

    # dmarc=none (or absent): require a DKIM signature aligned to the From domain.
    from_dom = _from_org_domain(email.from_addr)
    dkim_domains = {_org_domain(d) for d in _DKIM_RE.findall(ar)}
    if from_dom and from_dom in dkim_domains:
        return ("pass", f"aligned DKIM ({from_dom})")
    if dkim_domains:
        return (
            "unauthenticated",
            f"dmarc={dmarc or 'none'}; DKIM aligns to {sorted(dkim_domains)} not {from_dom}",
        )
    return ("unauthenticated", f"dmarc={dmarc or 'none'}; no aligned DKIM")
