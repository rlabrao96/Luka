from modules.email.filter import is_financial_email


def test_filter_rejects_non_financial_in_pipeline_context():
    """Verify the filter would reject a non-financial email in the pipeline."""
    assert not is_financial_email(
        subject="Novedades de marzo",
        sender="marketing@tienda.cl",
        body="Descubre las mejores ofertas de esta semana",
    )


def test_filter_accepts_financial_in_pipeline_context():
    """Verify the filter would accept a financial email in the pipeline."""
    assert is_financial_email(
        subject="Transferencia a Terceros",
        sender="serviciodetransferencias@bancochile.cl",
        body="Transferencia por $40.000 a Cuenta Corriente",
    )
