"""Add LLM parser tables: email_templates, bank_registry, parsed_email_log

Revision ID: 030
Revises: 029
Create Date: 2026-04-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "030"
down_revision = "029b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. email_templates (must be created first — bank_registry FK depends on it) ──
    op.create_table(
        "email_templates",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bank_domain", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("template_code", postgresql.JSONB(), nullable=False),
        sa.Column("template_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(), nullable=False, server_default="candidate"),
        sa.Column("validated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("accuracy", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retired_reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_email_templates_bank_domain", "email_templates", ["bank_domain"])

    # ── 2. bank_registry ──────────────────────────────────────────────────────────────
    op.create_table(
        "bank_registry",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("bank_domain", sa.String(), nullable=False),
        sa.Column("bank_name", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=False),
        sa.Column("known_subjects", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "notification_types",
            postgresql.JSONB(),
            nullable=False,
            server_default="[]",
        ),
        sa.Column("active_template_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("email_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="active"),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("bank_domain", name="uq_bank_registry_bank_domain"),
        sa.ForeignKeyConstraint(
            ["active_template_id"],
            ["email_templates.id"],
            name="fk_bank_registry_active_template_id",
            ondelete="SET NULL",
        ),
    )
    op.create_index("ix_bank_registry_bank_domain", "bank_registry", ["bank_domain"])
    op.create_index("ix_bank_registry_country", "bank_registry", ["country"])

    # ── 3. parsed_email_log ───────────────────────────────────────────────────────────
    op.create_table(
        "parsed_email_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bank_domain", sa.String(), nullable=False),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("raw_email_html", sa.Text(), nullable=True),
        sa.Column("llm_extraction", postgresql.JSONB(), nullable=True),
        sa.Column("template_extraction", postgresql.JSONB(), nullable=True),
        sa.Column("parser_used", sa.String(), nullable=False),
        sa.Column("llm_model_used", sa.String(), nullable=True),
        sa.Column("shadow_match", sa.Boolean(), nullable=True),
        sa.Column("waterfall_depth", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_parsed_email_log_user_id",
            ondelete="CASCADE",
        ),
    )
    op.create_index("ix_parsed_email_log_bank_domain", "parsed_email_log", ["bank_domain"])
    op.create_index("ix_parsed_email_log_created_at", "parsed_email_log", ["created_at"])

    # ── 4. RLS on parsed_email_log ────────────────────────────────────────────────────
    bind = op.get_bind()
    bind.execute(sa.text("ALTER TABLE parsed_email_log ENABLE ROW LEVEL SECURITY;"))
    bind.execute(
        sa.text(
            """
            CREATE POLICY parsed_email_log_user_isolation
                ON parsed_email_log
                USING (user_id = auth.uid());
            """
        )
    )

    # ── 5. Seed bank_registry ─────────────────────────────────────────────────────────
    _seed_bank_registry(bind)


def _seed_bank_registry(bind) -> None:
    rows = [
        # ── Chile ──────────────────────────────────────────────────────────────────
        ("bancochile.cl", "Banco de Chile", "CL", "active"),
        ("bancoestado.cl", "BancoEstado", "CL", "active"),
        ("santander.cl", "Santander", "CL", "active"),
        ("bci.cl", "BCI", "CL", "active"),
        ("bcidigital.cl", "BCI", "CL", "active"),
        ("bancofalabella.cl", "Banco Falabella", "CL", "active"),
        ("scotiabank.cl", "Scotiabank", "CL", "active"),
        ("bbva.cl", "BBVA", "CL", "active"),
        ("bbva.com", "BBVA", "CL", "active"),
        ("hsbc.cl", "HSBC", "CL", "active"),
        ("hsbc.com", "HSBC", "CL", "active"),
        ("bice.cl", "BICE", "CL", "active"),
        ("itau.cl", "Itaú", "CL", "active"),
        ("bancoripley.cl", "Banco Ripley", "CL", "active"),
        ("bancoconsorcio.cl", "Banco Consorcio", "CL", "active"),
        ("bancosecurity.cl", "Banco Security", "CL", "active"),
        ("bancointernacional.cl", "Banco Internacional", "CL", "active"),
        ("coopeuch.cl", "Coopeuch", "CL", "active"),
        ("mercadopago.cl", "Mercado Pago", "CL", "active"),
        ("mercadopago.com", "Mercado Pago", "CL", "active"),
        ("mercadolibre.cl", "MercadoLibre", "CL", "active"),
        ("mercadolibre.com", "MercadoLibre", "CL", "active"),
        ("somosmach.com", "Mach", "CL", "active"),
        ("tenpo.cl", "Tenpo", "CL", "active"),
        ("tapp.cl", "TAPP", "CL", "active"),
        ("losheroes.cl", "Los Héroes", "CL", "active"),
        ("copec.cl", "Copec", "CL", "active"),
        ("copecpay.cl", "CopecPay", "CL", "active"),
        ("dale.cl", "Dale", "CL", "active"),
        # ── Colombia ───────────────────────────────────────────────────────────────
        ("notificacionesbancolombia.com", "Bancolombia", "CO", "active"),
        ("bancolombia.com.co", "Bancolombia", "CO", "active"),
        ("davivienda.com", "Davivienda", "CO", "active"),
        ("bancodebogota.com.co", "Banco de Bogotá", "CO", "active"),
        ("bbva.com.co", "BBVA Colombia", "CO", "active"),
        ("nequi.com.co", "Nequi", "CO", "push_only"),
        # ── Mexico ─────────────────────────────────────────────────────────────────
        ("bbva.mx", "BBVA México", "MX", "active"),
        ("email.bbva.mx", "BBVA México", "MX", "active"),
        ("banorte.com", "Banorte", "MX", "active"),
        ("banamex.com", "Banamex", "MX", "active"),
        ("citibanamex.com", "Citibanamex", "MX", "active"),
        ("notificaciones.santander.com.mx", "Santander México", "MX", "active"),
        ("santander.com.mx", "Santander México", "MX", "active"),
        ("nu.com.mx", "Nu", "MX", "push_only"),
        # ── Peru ───────────────────────────────────────────────────────────────────
        ("bcp.com.pe", "BCP", "PE", "active"),
        ("viabcp.com", "BCP", "PE", "active"),
        ("interbank.pe", "Interbank", "PE", "active"),
        ("interbank.com.pe", "Interbank", "PE", "active"),
        ("bbva.pe", "BBVA Perú", "PE", "active"),
        ("scotiabank.com.pe", "Scotiabank Perú", "PE", "active"),
        ("yape.com.pe", "Yape", "PE", "push_only"),
        # ── Brazil ─────────────────────────────────────────────────────────────────
        ("nubank.com.br", "Nubank", "BR", "active"),
        ("novidades.nubank.com.br", "Nubank", "BR", "active"),
        ("itau.com.br", "Itaú", "BR", "active"),
        ("itau-unibanco.com.br", "Itaú Unibanco", "BR", "active"),
        ("bradesco.com.br", "Bradesco", "BR", "active"),
        ("bb.com.br", "Banco do Brasil", "BR", "push_only"),
        ("bancointer.com.br", "Banco Inter", "BR", "active"),
        ("inter.co", "Banco Inter", "BR", "active"),
        # ── USA — major banks ──────────────────────────────────────────────────────
        ("ealerts.bankofamerica.com", "Bank of America", "US", "active"),
        ("bankofamerica.com", "Bank of America", "US", "active"),
        ("chase.com", "Chase", "US", "active"),
        ("alertsp.chase.com", "Chase", "US", "active"),
        ("notify.wellsfargo.com", "Wells Fargo", "US", "active"),
        ("wellsfargo.com", "Wells Fargo", "US", "active"),
        ("citi.com", "Citi", "US", "active"),
        ("citibank.com", "Citi", "US", "active"),
        ("info3.citibank.com", "Citi", "US", "active"),
        ("pnc.com", "PNC", "US", "active"),
        ("jpmorgan.com", "JPMorgan", "US", "active"),
        ("capitalone.com", "Capital One", "US", "active"),
        ("usbank.com", "US Bank", "US", "active"),
        ("truist.com", "Truist", "US", "active"),
        ("td.com", "TD Bank", "US", "active"),
        ("tdbank.com", "TD Bank", "US", "active"),
        ("regions.com", "Regions Bank", "US", "active"),
        ("53.com", "Fifth Third Bank", "US", "active"),
        ("fifththird.com", "Fifth Third Bank", "US", "active"),
        ("key.com", "KeyBank", "US", "active"),
        ("keybank.com", "KeyBank", "US", "active"),
        ("citizensbank.com", "Citizens Bank", "US", "active"),
        ("ally.com", "Ally", "US", "active"),
        ("discover.com", "Discover", "US", "active"),
        ("americanexpress.com", "American Express", "US", "active"),
        ("aexp.com", "American Express", "US", "active"),
        ("gs.com", "Goldman Sachs", "US", "active"),
        ("marcus.com", "Marcus", "US", "active"),
        ("schwab.com", "Charles Schwab", "US", "active"),
        ("fidelity.com", "Fidelity", "US", "active"),
        ("synchrony.com", "Synchrony", "US", "active"),
        ("navyfederal.org", "Navy Federal", "US", "active"),
        ("usaa.com", "USAA", "US", "active"),
        # ── USA — fintechs ─────────────────────────────────────────────────────────
        ("sofi.com", "SoFi", "US", "active"),
        ("chime.com", "Chime", "US", "active"),
        ("venmo.com", "Venmo", "US", "active"),
        ("paypal.com", "PayPal", "US", "active"),
        ("zellepay.com", "Zelle", "US", "active"),
        ("cash.app", "Cash App", "US", "active"),
        ("robinhood.com", "Robinhood", "US", "active"),
        ("wealthfront.com", "Wealthfront", "US", "active"),
        ("betterment.com", "Betterment", "US", "active"),
        ("coinbase.com", "Coinbase", "US", "active"),
    ]

    insert_sql = sa.text(
        """
        INSERT INTO bank_registry (bank_domain, bank_name, country, status)
        VALUES (:bank_domain, :bank_name, :country, :status)
        ON CONFLICT (bank_domain) DO NOTHING
        """
    )
    for bank_domain, bank_name, country, status in rows:
        bind.execute(
            insert_sql,
            {
                "bank_domain": bank_domain,
                "bank_name": bank_name,
                "country": country,
                "status": status,
            },
        )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("DROP POLICY IF EXISTS parsed_email_log_user_isolation ON parsed_email_log;")
    )
    op.drop_index("ix_parsed_email_log_created_at", table_name="parsed_email_log")
    op.drop_index("ix_parsed_email_log_bank_domain", table_name="parsed_email_log")
    op.drop_table("parsed_email_log")

    op.drop_index("ix_bank_registry_country", table_name="bank_registry")
    op.drop_index("ix_bank_registry_bank_domain", table_name="bank_registry")
    op.drop_table("bank_registry")

    op.drop_index("ix_email_templates_bank_domain", table_name="email_templates")
    op.drop_table("email_templates")
