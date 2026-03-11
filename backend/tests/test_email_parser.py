from modules.email.parser import parse_bank_email


SANTANDER_EMAIL = """
Estimado cliente,
Se ha realizado una COMPRA por $15.990 en LIDER PROVI
Fecha: 10/03/2026 14:32
Tarjeta: **** 1234
"""

BCI_EMAIL = """
Transacción realizada
Comercio: COPEC LAS CONDES
Monto: $ 32.000
Fecha: 10/03/2026 08:15
"""

CHILE_EMAIL = """
Compra aprobada en STARBUCKS PROVIDENCIA
Monto: $4.500
10/03/2026 10:05
"""


def test_parse_santander_email():
    result = parse_bank_email(SANTANDER_EMAIL)
    assert result is not None
    assert result.amount == 15990
    assert "LIDER" in result.raw_merchant
    assert result.transaction_date is not None


def test_parse_bci_email():
    result = parse_bank_email(BCI_EMAIL)
    assert result is not None
    assert result.amount == 32000
    assert "COPEC" in result.raw_merchant


def test_parse_banco_chile_email():
    result = parse_bank_email(CHILE_EMAIL)
    assert result is not None
    assert result.amount == 4500
    assert "STARBUCKS" in result.raw_merchant


def test_returns_none_for_non_transaction_email():
    result = parse_bank_email("Hola, bienvenido a tu banco.")
    assert result is None
