"""Auto-create bank accounts from Luka Connect scrape data and update balances."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.households.models import BankAccount, HouseholdMember

# Map bank codes to display names (keys are lowercase to match Luka Connect codes)
BANK_NAMES = {
    "bchile": "Banco de Chile",
    "banco_chile": "Banco de Chile",
    "banco_estado": "BancoEstado",
    "bci": "BCI",
    "santander": "Santander",
    "falabella": "Banco Falabella",
}

# Map allBalances keys to (account_name, account_kind, currency)
ALL_BALANCES_KEY_MAP = {
    "CUENTA_CORRIENTE_CLP": ("Cuenta Corriente Moneda Local", "checking_account", "CLP"),
    "CUENTA_CORRIENTE_USD": ("Cuenta Corriente M/E", "checking_account", "USD"),
    "LINEA_CREDITO_CLP": ("Línea de Crédito", "line_of_credit", "CLP"),
}


async def ensure_accounts(
    db: AsyncSession,
    user_id: uuid.UUID,
    bank_code: str,
    movements: list[dict] | None,
    all_balances: dict | None,
    credit_cards: list[dict] | None,
) -> dict[tuple[str, str], uuid.UUID]:
    """
    Auto-create/update bank accounts from scrape data. Returns ba_map:
    dict[(account_name, currency) -> bank_account_id]
    """
    # Resolve household
    hm_result = await db.execute(
        select(HouseholdMember.household_id).where(HouseholdMember.user_id == user_id)
    )
    household_id = hm_result.scalar_one_or_none()
    if not household_id:
        return {}

    bank_name = BANK_NAMES.get(bank_code, bank_code)
    now = datetime.now(timezone.utc)

    # Collect all accounts to ensure: list of dicts with account fields
    accounts_to_ensure: list[dict] = []

    # --- Step 1: Accounts from movements ---
    if movements:
        seen_movement_accounts: set[tuple[str, str]] = set()
        for mov in movements:
            acct_name = mov.get("accountName")
            currency = mov.get("currency", "CLP")
            if not acct_name or (acct_name, currency) in seen_movement_accounts:
                continue
            seen_movement_accounts.add((acct_name, currency))

            # Only create accounts for source="account" movements
            # CC movements use the checking accountNumber, not a real CC account
            if mov.get("source") == "account":
                accounts_to_ensure.append(
                    {
                        "account_name": acct_name,
                        "account_number": mov.get("accountNumber"),
                        "account_kind": "checking_account",
                        "currency": currency,
                    }
                )

    # --- Step 2: Accounts from creditCards[] ---
    if credit_cards:
        for card in credit_cards:
            label = card.get("label", "")
            # Extract account number from label (e.g., "Visa Signature ****5032" -> "****5032")
            parts = label.split()
            acct_number = parts[-1] if parts else None

            national = card.get("national")
            if national and isinstance(national, dict) and "total" in national:
                accounts_to_ensure.append(
                    {
                        "account_name": f"{label} Nacional",
                        "account_number": acct_number,
                        "account_kind": "credit_card",
                        "currency": "CLP",
                        "balance_current": -(national["total"] - national.get("available", 0)),
                        "balance_limit": national["total"],
                    }
                )

            international = card.get("international")
            if international and isinstance(international, dict) and "total" in international:
                accounts_to_ensure.append(
                    {
                        "account_name": f"{label} Internacional",
                        "account_number": acct_number,
                        "account_kind": "credit_card",
                        "currency": international.get("currency", "USD"),
                        "balance_current": -(
                            international["total"] - international.get("available", 0)
                        ),
                        "balance_limit": international["total"],
                    }
                )

    # --- Step 3: Line of credit from allBalances ---
    if all_balances and "LINEA_CREDITO_CLP" in all_balances:
        val = all_balances["LINEA_CREDITO_CLP"]
        accounts_to_ensure.append(
            {
                "account_name": "Línea de Crédito",
                "account_number": None,
                "account_kind": "line_of_credit",
                "currency": "CLP",
                "balance_current": val,
                "balance_limit": val,
            }
        )

    # --- Dedup + create/update ---
    # Fetch existing accounts for this user+bank
    existing_result = await db.execute(
        select(BankAccount).where(
            BankAccount.user_id == user_id,
            BankAccount.bank_name == bank_name,
        )
    )
    existing_accounts = list(existing_result.scalars().all())
    existing_map: dict[tuple[str, str], BankAccount] = {
        (a.account_name, a.currency): a for a in existing_accounts if a.account_name and a.currency
    }

    ba_map: dict[tuple[str, str], uuid.UUID] = {}

    for acct_data in accounts_to_ensure:
        key = (acct_data["account_name"], acct_data["currency"])
        existing = existing_map.get(key)

        if existing:
            # Update balance if we have fresh data
            if "balance_current" in acct_data:
                existing.balance_current = acct_data["balance_current"]
                existing.balance_limit = acct_data.get("balance_limit")
                existing.last_synced_at = now
            ba_map[key] = existing.id
        else:
            # Create new account
            new_account = BankAccount(
                household_id=household_id,
                user_id=user_id,
                bank_name=bank_name,
                account_name=acct_data["account_name"],
                account_number=acct_data.get("account_number"),
                account_kind=acct_data["account_kind"],
                currency=acct_data["currency"],
                account_type="personal",
                balance_current=acct_data.get("balance_current"),
                balance_limit=acct_data.get("balance_limit"),
                last_synced_at=now if "balance_current" in acct_data else None,
            )
            db.add(new_account)
            await db.flush()  # Get the ID without committing
            ba_map[key] = new_account.id
            existing_map[key] = new_account

    # --- Update checking account balances from allBalances ---
    if all_balances:
        for bal_key, (acct_name, _, currency) in ALL_BALANCES_KEY_MAP.items():
            if bal_key in all_balances and bal_key != "LINEA_CREDITO_CLP":
                key = (acct_name, currency)
                acct = existing_map.get(key)
                if acct:
                    acct.balance_current = all_balances[bal_key]
                    acct.balance_limit = None
                    acct.last_synced_at = now

    # Also add any existing accounts (from previous syncs) to ba_map
    for (name, curr), acct in existing_map.items():
        if (name, curr) not in ba_map:
            ba_map[(name, curr)] = acct.id

    return ba_map
