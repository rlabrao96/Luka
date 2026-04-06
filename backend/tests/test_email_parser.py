from modules.email.parser import parse_bank_email_regex as parse_bank_email


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


# --- Bank of America (US) ---

BOFA_TARGET = (
    "Credit card transaction exceeds alert limit you set "
    "Customized Cash Rewards Visa Signature ending in 5876 "
    "Amount: $17.08 "
    "Date: March 28, 2026 "
    "Where: TARGET STORE- T3206 "
    "View details "
    "If you made this purchase or payment but don't recognize the "
    "amount, wait until the final purchase amount has posted "
    "before filing a dispute claim."
)

BOFA_WINE = (
    "Credit card transaction exceeds alert limit you set "
    "Customized Cash Rewards Visa Signature ending in 5876 "
    "Amount: $23.96 "
    "Date: March 28, 2026 "
    "Where: WINE AND SPIRITS 9101 "
    "View details"
)


def test_parse_bofa_target():
    result = parse_bank_email(BOFA_TARGET)
    assert result is not None
    assert result.amount == 1708  # $17.08 stored as cents
    assert result.currency == "USD"
    assert "TARGET STORE" in result.raw_merchant
    assert result.transaction_date.day == 28
    assert result.transaction_date.month == 3
    assert result.transaction_type == "expense"


def test_parse_bofa_wine():
    result = parse_bank_email(BOFA_WINE)
    assert result is not None
    assert result.amount == 2396  # $23.96 stored as cents
    assert result.currency == "USD"
    assert "WINE AND SPIRITS" in result.raw_merchant


def test_clp_currency_default():
    result = parse_bank_email(SANTANDER_EMAIL)
    assert result is not None
    assert result.currency == "CLP"
    assert result.amount == 15990


# --- Bank of America Zelle ---

BOFA_ZELLE = (
    "Zelle® payment of $2,000.00 to BENJAMIN BRAITHWAITE has been sent "
    "Sent from account ending in 7422 "
    "To 646-215-0024 "
    "Your message Security deposit "
    "View your balance "
    "Confirmation jnbsadfl3 "
    "If you didn't make this payment, contact us"
)


def test_parse_bofa_zelle():
    result = parse_bank_email(BOFA_ZELLE)
    assert result is not None
    assert result.amount == 200000  # $2,000.00 stored as cents
    assert result.currency == "USD"
    assert result.transaction_type == "transfer"
    assert "Benjamin Braithwaite" in result.raw_merchant


BOFA_ZELLE_SMALL = (
    "Zelle® payment of $50.00 to JANE DOE has been sent "
    "Sent from account ending in 7422 "
    "To 555-123-4567 "
    "View your balance "
    "Confirmation abc123"
)


def test_parse_bofa_zelle_small_amount():
    result = parse_bank_email(BOFA_ZELLE_SMALL)
    assert result is not None
    assert result.amount == 5000  # $50.00 stored as cents
    assert result.currency == "USD"
    assert result.transaction_type == "transfer"
    assert "Jane Doe" in result.raw_merchant


# --- BofA mixed-case and special char merchants ---

BOFA_SPOTIFY = (
    "Credit card transaction exceeds alert limit you set "
    "Customized Cash Rewards Visa Signature ending in 5876 "
    "Amount: $7.55 "
    "Date: April 5, 2026 "
    "Where: Spotify P412215700 "
    "View details "
    "If you made this purchase or payment but don't recognize the "
    "amount, wait until the final purchase amount has posted "
    "before filing a dispute claim. "
    "If you get an email that looks suspicious or you are not the intended "
    "recipient of this email, don't click on any links. Instead, forward to "
    "abuse@bankofamerica.com then delete it."
)


def test_parse_bofa_spotify():
    result = parse_bank_email(BOFA_SPOTIFY)
    assert result is not None
    assert result.amount == 755
    assert result.currency == "USD"
    assert "SPOTIFY" in result.raw_merchant
    assert "DELETE" not in result.raw_merchant


BOFA_CAFE = (
    "Credit card transaction exceeds alert limit you set "
    "Customized Cash Rewards Visa Signature ending in 5876 "
    "Amount: $5.19 "
    "Date: April 2, 2026 "
    "Where: BA@PENNPRETCAFE "
    "View details "
    "If you made this purchase or payment but don't recognize the "
    "amount, wait until the final purchase amount has posted "
    "before filing a dispute claim. "
    "abuse@bankofamerica.com then delete it."
)


def test_parse_bofa_cafe_at_sign():
    result = parse_bank_email(BOFA_CAFE)
    assert result is not None
    assert result.amount == 519
    assert result.currency == "USD"
    assert "PENNPRETCAFE" in result.raw_merchant
    assert "DELETE" not in result.raw_merchant


# --- PNC Zelle ---

PNC_ZELLE_SENT = (
    "Payment Alert You Sent a Payment to "
    "RAFAEL LABRA OETTINGER "
    "From Account: x1645 "
    "Amount: $500.00 "
    "Payment Date: 04/06/26 "
    "Memo: Apt April "
    "Transaction ID: PNCAA0ZGt35v "
    "This money will be in RAFAEL LABRA OETTINGER's account shortly, "
    "typically in minutes. "
    "For more information on sending and receiving money with people "
    "you know and trust, visit PNC.com/Zelle. "
    "Thank you for banking with PNC."
)


def test_parse_pnc_zelle_sent():
    result = parse_bank_email(PNC_ZELLE_SENT)
    assert result is not None
    assert result.amount == 50000  # $500.00 stored as cents
    assert result.currency == "USD"
    assert result.transaction_type == "transfer"
    assert "Rafael Labra Oettinger" in result.raw_merchant
    assert result.transaction_date.month == 4
    assert result.transaction_date.day == 6


PNC_ZELLE_RECEIVED = (
    "Payment Alert You Received a Payment from "
    "JANE DOE "
    "To Account: x1645 "
    "Amount: $75.50 "
    "Payment Date: 03/28/26 "
    "Memo: Dinner split "
    "Transaction ID: PNCBB1XYZ99w "
    "Thank you for banking with PNC."
)


def test_parse_pnc_zelle_received():
    result = parse_bank_email(PNC_ZELLE_RECEIVED)
    assert result is not None
    assert result.amount == 7550  # $75.50 stored as cents
    assert result.currency == "USD"
    assert result.transaction_type == "transfer"
    assert "Jane Doe" in result.raw_merchant
    assert result.transaction_date.month == 3
    assert result.transaction_date.day == 28
