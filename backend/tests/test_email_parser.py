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


# --- Real Banco de Chile formats (from actual emails) ---

BCHILE_COMPRA = (
    "Te informamos que se ha realizado una compra por $52.007 "
    "con Tarjeta de Crdito ****5032 en SCOTIABANK CAE SANTIAGO CL "
    "el 13/03/2026 09:45."
)

BCHILE_COMPROBANTE_PAGO = (
    "Comprobante de pago exitoso Detalle cuenta(s) pagada(s) "
    "Comercio SCOTIABANK CAE Monto $ 52.007 Detalle del pago "
    "Medio de pago Tarjeta de Crdito ****5032 "
    "Total $52.007 Fecha y Hora 13/03/2026 09:45:03"
)

BCHILE_COMPRA_PARKING = (
    "Te informamos que se ha realizado una compra por $1.450 "
    "con Tarjeta de Crdito ****5032 en PARKING COSTANERA SANTIAGO CL "
    "el 11/03/2026 15:09."
)


def test_parse_bchile_compra():
    result = parse_bank_email(BCHILE_COMPRA)
    assert result is not None
    assert result.amount == 52007
    assert "SCOTIABANK CAE" in result.raw_merchant
    assert "SANTIAGO" not in result.raw_merchant
    assert result.transaction_date.day == 13


def test_parse_bchile_comprobante_pago():
    result = parse_bank_email(BCHILE_COMPROBANTE_PAGO)
    assert result is not None
    assert result.amount == 52007
    assert "SCOTIABANK CAE" in result.raw_merchant


def test_parse_bchile_compra_parking():
    result = parse_bank_email(BCHILE_COMPRA_PARKING)
    assert result is not None
    assert result.amount == 1450
    assert "PARKING COSTANERA" in result.raw_merchant
    assert "SANTIAGO" not in result.raw_merchant


def test_html_stripping():
    html = "<html><body><p>compra por $5.990 en STARBUCKS SANTIAGO CL el 10/03/2026 10:00</p></body></html>"
    result = parse_bank_email(html)
    assert result is not None
    assert result.amount == 5990
    assert "STARBUCKS" in result.raw_merchant
