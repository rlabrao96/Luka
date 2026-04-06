# DEPRECATED: Use bank_registry_service.py for async DB-backed lookups.
# This module is kept as a sync fallback when DB is unavailable.
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
    # Portuguese (Brazilian banks)
    "transação",
    "transacao",
    "compra aprovada",
    "cartão",
    "cartao",
    "fatura",
    "pagamento",
    "pix",
    # Additional Spanish (CO/MX/PE)
    "movimiento",
    "consumo",
    "aviso",
    "alerta",
    "notificación",
    "notificacion",
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

# Map sender domains to display-friendly bank names.
# Used to infer bank_name from email sender when no bank account is linked.
BANK_DISPLAY_NAMES = {
    # Chile
    "bancoestado.cl": "BancoEstado",
    "bci.cl": "BCI",
    "bice.cl": "BICE",
    "bancochile.cl": "Banco de Chile",
    "bancofalabella.cl": "Banco Falabella",
    "itau.cl": "Itaú",
    "bancoripley.cl": "Banco Ripley",
    "santander.cl": "Santander",
    "bancoconsorcio.cl": "Banco Consorcio",
    "scotiabank.cl": "Scotiabank",
    "bancosecurity.cl": "Banco Security",
    "bancointernacional.cl": "Banco Internacional",
    "coopeuch.cl": "Coopeuch",
    "bbva.cl": "BBVA",
    "bbva.com": "BBVA",
    "hsbc.cl": "HSBC",
    "hsbc.com": "HSBC",
    "bcidigital.cl": "BCI",
    "mercadopago.cl": "Mercado Pago",
    "mercadopago.com": "Mercado Pago",
    "tenpo.cl": "Tenpo",
    "tapp.cl": "TAPP",
    # USA
    "bankofamerica.com": "Bank of America",
    "chase.com": "Chase",
    "jpmorgan.com": "JPMorgan",
    "citi.com": "Citi",
    "citibank.com": "Citi",
    "wellsfargo.com": "Wells Fargo",
    "capitalone.com": "Capital One",
    "usbank.com": "US Bank",
    "pnc.com": "PNC",
    "truist.com": "Truist",
    "td.com": "TD Bank",
    "tdbank.com": "TD Bank",
    "regions.com": "Regions Bank",
    "53.com": "Fifth Third Bank",
    "fifththird.com": "Fifth Third Bank",
    "key.com": "KeyBank",
    "keybank.com": "KeyBank",
    "citizensbank.com": "Citizens Bank",
    "ally.com": "Ally",
    "discover.com": "Discover",
    "americanexpress.com": "American Express",
    "aexp.com": "American Express",
    "gs.com": "Goldman Sachs",
    "marcus.com": "Marcus",
    "schwab.com": "Charles Schwab",
    "fidelity.com": "Fidelity",
    "synchrony.com": "Synchrony",
    "navyfederal.org": "Navy Federal",
    "usaa.com": "USAA",
    "sofi.com": "SoFi",
    "chime.com": "Chime",
    "venmo.com": "Venmo",
    "paypal.com": "PayPal",
    "zellepay.com": "Zelle",
    "cash.app": "Cash App",
    "robinhood.com": "Robinhood",
}

_EMAIL_RE = re.compile(r"[\w.+-]+@([\w.-]+)")


def _extract_domain(sender: str) -> str | None:
    """Extract the domain from a From header like 'Banco X <noti@banco.cl>'."""
    m = _EMAIL_RE.search(sender)
    return m.group(1).lower() if m else None


def _match_bank_domain(domain: str) -> str | None:
    """Return the matching BANK_SENDER_DOMAINS entry for a domain (exact or subdomain)."""
    for d in BANK_SENDER_DOMAINS:
        if domain == d or domain.endswith("." + d):
            return d
    return None


def is_bank_sender(sender: str) -> bool:
    """Return True if the sender's domain matches a known bank."""
    domain = _extract_domain(sender)
    if not domain:
        return False
    return _match_bank_domain(domain) is not None


def get_bank_name(sender: str) -> str | None:
    """Infer a display-friendly bank name from the sender's email domain."""
    domain = _extract_domain(sender)
    if not domain:
        return None
    matched = _match_bank_domain(domain)
    if not matched:
        return None
    return BANK_DISPLAY_NAMES.get(matched)


def is_financial_email(subject: str, sender: str, body: str) -> bool:
    """Check if an email is likely a financial notification based on keyword matching."""
    text = f"{subject} {sender} {body}".lower()
    return any(kw in text for kw in FINANCIAL_KEYWORDS)
