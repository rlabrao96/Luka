FINANCIAL_KEYWORDS = {
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
}


def is_financial_email(subject: str, sender: str, body: str) -> bool:
    """Check if an email is likely a financial notification based on keyword matching."""
    text = f"{subject} {sender} {body}".lower()
    return any(kw in text for kw in FINANCIAL_KEYWORDS)
