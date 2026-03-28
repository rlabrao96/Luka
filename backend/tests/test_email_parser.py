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


# --- Banco de Chile transfer format ---

BCHILE_TRANSFER = (
    "Estimado(a) Rafael Andres Labra Oettinger "
    "Le informamos que usted ha efectuado una transferencia de fondos "
    "a Juan Jose Lamarca, el dia 28 de marzo de 2026, desde su "
    "Cuenta Corriente 4420427502. El detalle puede revisarlo a continuación "
    "Datos del Destinatario Nombre Juan Jose Lamarca Rut 19.686.463-6 "
    "Cuenta 7031408002 Banco Banco Santander "
    "Datos de la Transferencia Fecha 28/03/2026 "
    "Cuenta 4420427502 Monto $95.600 ID TEF_IPE260328122512408087647"
)


def test_parse_bchile_transfer():
    result = parse_bank_email(BCHILE_TRANSFER)
    assert result is not None
    assert result.amount == 95600
    assert result.transaction_type == "transfer"
    assert "Juan Jose Lamarca" in result.raw_merchant
    assert result.transaction_date.day == 28


def test_purchase_has_expense_type():
    result = parse_bank_email(SANTANDER_EMAIL)
    assert result is not None
    assert result.transaction_type == "expense"


# --- Banco Edwards incoming transfer ---

EDWARDS_TRANSFER_INCOMING = (
    "Comprobante de transferencia electrónica de fondos "
    "Estimado(a): Paula Valentina Correa Silva "
    "Te informamos que nuestro(a) cliente Catalina Sofia Jadranka Droppelmann "
    "ha efectuado una transferencia de fondos a tu cuenta con el siguiente detalle: "
    "Datos de cuenta Fecha 20/03/2026 "
    "Asunto Viatico iquiqie 3 días enero 2026 "
    "Datos de destinatario Nombre y Apellido Paula Valentina Correa Silva "
    "Rut 19526537-2 Email pcorreasilva97@gmail.com "
    "Banco Banco Santander Cuenta destino Cuenta Corriente 00-007-74057-47 "
    "Monto $180.000 "
    "Número de comprobante TEFMBCO2603201625123966472310"
)


def test_parse_edwards_transfer_incoming():
    result = parse_bank_email(EDWARDS_TRANSFER_INCOMING)
    assert result is not None
    assert result.amount == 180000
    assert result.transaction_type == "transfer"
    assert "Catalina" in result.raw_merchant
    assert "Droppelmann" in result.raw_merchant
    assert result.transaction_date.day == 20


# --- Santander outgoing transfer ---

SANTANDER_TRANSFER_OUTGOING = (
    "Comprobante Transferencia de fondos "
    "Estimado(a) PAULA VALENTINA CORREA SILVA: "
    "Te enviamos el detalle de la transferencia realizada el 03/03/2026. "
    "Monto transferido $ 8.226 "
    "Datos de origen Tipo de cuenta Cuenta Corriente "
    "Nº de cuenta 0-000-77-40574-7 RUT 19.526.537-2 "
    "Nombre PAULA VALENTINA CORREA SILVA "
    "Comentario 1FIN-pi_3ARsYnir5EmvnZ0xYZKaVuoli2h "
    "Datos de destino Nombre UNIRED RUT 76.063.653-3 "
    "Banco Banco BICE Tipo de cuenta Cuenta Corriente "
    "Nº de cuenta 0-000-01-38661-1 E-mail transferencias@fintoc.com"
)


def test_parse_santander_transfer_outgoing():
    result = parse_bank_email(SANTANDER_TRANSFER_OUTGOING)
    assert result is not None
    assert result.amount == 8226
    assert result.transaction_type == "transfer"
    assert "Unired" in result.raw_merchant
    assert result.transaction_date.day == 3
