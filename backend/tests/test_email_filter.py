from modules.email.filter import is_financial_email, is_bank_sender


def test_matches_transfer_email():
    assert is_financial_email(
        subject="Transferencia a Terceros",
        sender="serviciodetransferencias@bancochile.cl",
        body="Te informamos que has realizado una Transferencia a terceros",
    )


def test_matches_credit_card_purchase():
    assert is_financial_email(
        subject="Aviso de compra",
        sender="enviodigital@bancochile.cl",
        body="se ha realizado una compra por $1.450 con Tarjeta de Crédito ****5032",
    )


def test_matches_credit_card_payment():
    assert is_financial_email(
        subject="Comprobante pago Tarjeta de Crédito Nacional",
        sender="serviciodetransferencias@bancochile.cl",
        body="se ha efectuado el pago de la tarjeta de crédito nacional",
    )


def test_matches_deposit():
    assert is_financial_email(
        subject="Abono en cuenta",
        sender="notificaciones@banco.cl",
        body="Se ha registrado un abono en su cuenta corriente",
    )


def test_matches_pac_pat():
    assert is_financial_email(
        subject="Cargo PAC procesado",
        sender="notificaciones@banco.cl",
        body="Se ha procesado su pago automático PAC",
    )


def test_matches_atm_withdrawal():
    assert is_financial_email(
        subject="Giro en cajero",
        sender="notificaciones@banco.cl",
        body="Se ha realizado un retiro en cajero automático",
    )


def test_rejects_newsletter():
    assert not is_financial_email(
        subject="Novedades de marzo",
        sender="marketing@tienda.cl",
        body="Descubre las mejores ofertas de esta semana en nuestra tienda online",
    )


def test_rejects_personal_email():
    assert not is_financial_email(
        subject="Hola, cómo estás?",
        sender="amigo@gmail.com",
        body="Te escribo para coordinar la junta del viernes",
    )


def test_rejects_promotional_bank_email_without_keywords():
    assert not is_financial_email(
        subject="Nuevos beneficios para ti",
        sender="ofertas@bancochile.cl",
        body="Aprovecha nuestras nuevas promociones exclusivas para clientes premium",
    )


def test_case_insensitive():
    assert is_financial_email(
        subject="TRANSFERENCIA EXITOSA",
        sender="banco@test.cl",
        body="detalle de su TRANSFERENCIA",
    )


def test_matches_keyword_in_sender_only():
    assert is_financial_email(
        subject="Notification",
        sender="serviciodetransferencias@bancochile.cl",
        body="You have a new message",
    )


# ── is_bank_sender tests ──


def test_bank_sender_exact_domain():
    assert is_bank_sender("notificaciones@bancochile.cl")


def test_bank_sender_subdomain():
    assert is_bank_sender("alertas@noti.santander.cl")


def test_bank_sender_with_display_name():
    assert is_bank_sender("Banco de Chile <enviodigital@bancochile.cl>")


def test_bank_sender_fintech():
    assert is_bank_sender("no-reply@tenpo.cl")
    assert is_bank_sender("alertas@somosmach.com")
    assert is_bank_sender("noti@mercadopago.com")


def test_bank_sender_rejects_unknown():
    assert not is_bank_sender("promo@tienda.cl")
    assert not is_bank_sender("offers@amazon.com")


def test_bank_sender_rejects_gmail():
    assert not is_bank_sender("someone@gmail.com")


def test_bank_sender_rejects_empty():
    assert not is_bank_sender("")
    assert not is_bank_sender("no-email-here")
