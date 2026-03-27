import re

FINANCIAL_KEYWORDS = {
    # Spanish (Chilean banks)
    "transferencia",
    "transaccion",
    "transacción",
    "compra",
    "pago",
    "tarjeta",
    "crédito",
    "credito",
    "débito",
    "debito",
    "abono",
    "depósito",
    "deposito",
    "giro",
    "cajero",
    "monto",
    "cuenta corriente",
    "cuenta vista",
    "línea de crédito",
    "linea de credito",
    "pac",
    "pat",
    "cuota",
    "cargo",
    "comprobante",
    "saldo",
    "retiro",
    # English (US banks)
    "transaction",
    "purchase",
    "payment",
    "transfer",
    "debit",
    "credit",
    "deposit",
    "withdrawal",
    "charge",
    "balance",
    "statement",
    "spending alert",
    "unusual activity",
    "account activity",
    "your account",
    "your card",
    "was used",
    "was charged",
    "has been posted",
    "available balance",
    "low balance",
    "payment due",
    "payment received",
    "direct deposit",
    "overdraft",
    "atm withdrawal",
    "pending transaction",
    "authorization",
}

# Domains used by Chilean banks and fintechs for transaction notifications.
# Mapped from the Fintoc-supported institution list.
BANK_SENDER_DOMAINS = {
    # Traditional banks
    "bancoestado.cl",
    "bci.cl",
    "bice.cl",
    "bancochile.cl",
    "bancofalabella.cl",
    "itau.cl",
    "bancoripley.cl",
    "santander.cl",
    "bancoconsorcio.cl",
    "scotiabank.cl",
    "bancosecurity.cl",
    "bancointernacional.cl",
    "coopeuch.cl",
    "bbva.cl",
    "bbva.com",
    "hsbc.cl",
    "hsbc.com",
    # Fintechs / prepaid (Chile)
    "mercadopago.cl",
    "mercadopago.com",
    "mercadolibre.cl",
    "mercadolibre.com",
    "somosmach.com",
    "bcidigital.cl",
    "tenpo.cl",
    "tapp.cl",
    "losheroes.cl",
    "copec.cl",
    "copecpay.cl",
    "dale.cl",
    # US major banks
    "bankofamerica.com",
    "chase.com",
    "jpmorgan.com",
    "citi.com",
    "citibank.com",
    "wellsfargo.com",
    "capitalone.com",
    "usbank.com",
    "pnc.com",
    "truist.com",
    "td.com",
    "tdbank.com",
    "regions.com",
    "53.com",  # Fifth Third Bank
    "fifththird.com",
    "key.com",
    "keybank.com",
    "citizensbank.com",
    "ally.com",
    "discover.com",
    "americanexpress.com",
    "aexp.com",
    "gs.com",  # Goldman Sachs / Marcus
    "marcus.com",
    "schwab.com",
    "fidelity.com",
    "synchrony.com",
    "navyfederal.org",
    "usaa.com",
    # US fintechs / neobanks
    "sofi.com",
    "chime.com",
    "venmo.com",
    "paypal.com",
    "zellepay.com",
    "cash.app",
    "robinhood.com",
    "wealthfront.com",
    "betterment.com",
    "coinbase.com",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w.-]+)")


def _extract_domain(sender: str) -> str | None:
    """Extract the domain from a From header like 'Banco X <noti@banco.cl>'."""
    m = _EMAIL_RE.search(sender)
    return m.group(1).lower() if m else None


def is_bank_sender(sender: str) -> bool:
    """Return True if the sender's domain matches a known Chilean bank."""
    domain = _extract_domain(sender)
    if not domain:
        return False
    # Match exact domain or parent domain (e.g. noti.bancochile.cl → bancochile.cl)
    return any(domain == d or domain.endswith("." + d) for d in BANK_SENDER_DOMAINS)


def is_financial_email(subject: str, sender: str, body: str) -> bool:
    """Check if an email is likely a financial notification based on keyword matching."""
    text = f"{subject} {sender} {body}".lower()
    return any(kw in text for kw in FINANCIAL_KEYWORDS)
