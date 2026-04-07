#!/usr/bin/env python3
"""
Quick test: Scrape Banco de Chile using open-banking-chile.
Prompts for credentials securely (never stored to disk).
Displays accounts, balances, and last 5 movements per source.
"""

import getpass
import json
import os
import subprocess
import sys
from collections import defaultdict


def prompt_credentials():
    """Securely prompt for RUT and password."""
    print("=" * 60)
    print("  Banco de Chile — Test Scraper")
    print("  (credentials stay in memory, never saved to disk)")
    print("=" * 60)
    print()
    rut = input("  RUT (ej: 12345678-9): ").strip()
    password = getpass.getpass("  Clave Internet: ")
    print()
    return rut, password


def run_scraper(rut: str, password: str) -> dict:
    """Run the open-banking-chile CLI and return parsed JSON."""
    env = os.environ.copy()
    env["BCHILE_RUT"] = rut
    env["BCHILE_PASS"] = password

    # Use our modified local fork
    cli_path = os.path.join(
        os.path.dirname(__file__), "open-banking-chile-fork", "dist", "cli.js"
    )

    print("Starting Chrome + scraper (this takes 30-90 seconds)...")
    print("If 2FA (Clave Dinamica) is requested, approve it on your phone.\n")

    # Stream stderr (debug logs) live, capture stdout (JSON result)
    proc = subprocess.Popen(
        ["node", cli_path, "--bank", "bchile", "--headful"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )

    # Read stderr in real-time so user sees progress
    import threading

    def stream_stderr():
        for line in proc.stderr:
            print(f"  [scraper] {line.rstrip()}")

    t = threading.Thread(target=stream_stderr, daemon=True)
    t.start()

    try:
        stdout_data, _ = proc.communicate(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        print("\nTimeout — scraper took too long (>5 min).")
        sys.exit(1)

    if proc.returncode != 0:
        print(f"\nScraper exited with code {proc.returncode}")
        print(f"STDOUT:\n{stdout_data[:1000]}")
        sys.exit(1)

    stdout = stdout_data.strip()

    # The CLI outputs a dotenv tip line before the JSON, and may use
    # non-standard quotes. Find the JSON object by looking for {"success
    json_start = stdout.find('{"success')
    if json_start == -1:
        # Try alternate: the scraper might output with single quotes
        json_start = stdout.find("{'success")
    if json_start == -1:
        print("No JSON found in scraper output.")
        print(f"STDOUT:\n{stdout[:1000]}")
        sys.exit(1)

    json_str = stdout[json_start:]

    # Try parsing directly first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # The CLI may output JS-style JSON (unquoted keys, single quotes).
    # Save raw output and parse with Node.js which handles it natively.
    raw_path = os.path.join(os.path.dirname(__file__), "_raw_output.tmp")
    with open(raw_path, "w") as f:
        f.write(json_str)

    try:
        node_result = subprocess.run(
            [
                "node",
                "-e",
                f"const fs=require('fs'); const raw=fs.readFileSync('{raw_path}','utf8'); console.log(JSON.stringify(eval('('+raw+')')))",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if node_result.returncode == 0:
            return json.loads(node_result.stdout.strip())
    except Exception:
        pass
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)

    print("Could not parse JSON from scraper output.")
    print(f"First 500 chars of JSON:\n{json_str[:500]}")
    sys.exit(1)


def format_amount(amount: int) -> str:
    """Format CLP amount with sign and thousands separator."""
    sign = "+" if amount > 0 else ""
    return f"{sign}${amount:,.0f}".replace(",", ".")


def print_movements(label: str, movs: list, limit: int = 10):
    """Print a section of movements."""
    print(f"\n  --- {label} ({len(movs)} total) — Last {min(limit, len(movs))}: ---")
    print(
        f"  {'Date':<12} {'Time':<6} {'Description':<38} {'Amount':>15} {'Balance':>12} {'Cuotas':>8}"
    )
    print(f"  {'-'*12} {'-'*6} {'-'*38} {'-'*15} {'-'*12} {'-'*8}")
    for m in movs[:limit]:
        desc = m["description"][:38]
        cuotas = m.get("installments", "")
        time = m.get("time", "") or ""
        bal = m.get("balance", "")
        bal_str = (
            f"${bal:,.0f}".replace(",", ".")
            if isinstance(bal, (int, float)) and bal != 0
            else ""
        )
        print(
            f"  {m['date']:<12} {time:<6} {desc:<38} {format_amount(m['amount']):>15} {bal_str:>12} {cuotas:>8}"
        )


def display_results(data: dict):
    """Pretty-print the scraper results."""
    print("\n" + "=" * 60)

    if not data.get("success"):
        print(f"  ERROR: {data.get('error', 'Unknown error')}")
        return

    print(f"  Bank: {data['bank']}")
    print(f"  Total movements fetched: {len(data.get('movements', []))}")

    # Balances
    all_balances = data.get("allBalances", {})
    if all_balances:
        print("\n  Account Balances:")
        for key, val in all_balances.items():
            label = key.replace("_", " ").title()
            print(f"    {label}: ${val:,.0f}".replace(",", "."))
    else:
        balance = data.get("balance")
        if balance is not None:
            print(f"  Account balance: ${balance:,.0f}".replace(",", "."))

    # Credit card cupos
    credit_cards = data.get("creditCards", [])
    if credit_cards:
        print(f"\n  Credit Cards ({len(credit_cards)}):")
        for cc in credit_cards:
            print(f"    {cc.get('label', 'Card')}")
            nat = cc.get("national", {})
            if nat:
                print(
                    f"      Nacional:  used=${nat.get('used',0):,.0f}  available=${nat.get('available',0):,.0f}  total=${nat.get('total',0):,.0f}".replace(
                        ",", "."
                    )
                )
            intl = cc.get("international", {})
            if intl:
                print(
                    f"      Internacional: used=${intl.get('used',0):,.0f}  available=${intl.get('available',0):,.0f}  total=${intl.get('total',0):,.0f} {intl.get('currency','')}".replace(
                        ",", "."
                    )
                )
            if cc.get("nextBillingDate"):
                print(f"      Next billing: {cc['nextBillingDate']}")

    # Group movements by source
    movements = data.get("movements", [])
    by_source = defaultdict(list)
    for m in movements:
        by_source[m.get("source", "unknown")].append(m)

    source_labels = {
        "account": "Cuenta Corriente/Vista",
        "credit_card_unbilled": "Tarjeta de Credito (por facturar)",
        "credit_card_billed": "Tarjeta de Credito (facturado)",
    }

    for source, movs in by_source.items():
        label = source_labels.get(source, source)

        # Sort movements by date (newest first)
        # Date format is DD-MM-YYYY, convert for sorting
        def sort_key(m):
            d = m.get("date", "")
            parts = d.split("-")
            if len(parts) == 3:
                return f"{parts[2]}-{parts[1]}-{parts[0]}"  # YYYY-MM-DD
            return d

        movs.sort(key=sort_key, reverse=True)

        # Sub-group by currency if available
        by_currency = defaultdict(list)
        for m in movs:
            curr = m.get("currency", "")
            acct_name = m.get("accountName", "")
            acct_num = m.get("accountNumber", "")
            key = f"{curr}|{acct_name}|{acct_num}" if curr else ""
            by_currency[key].append(m)

        if len(by_currency) > 1 or (len(by_currency) == 1 and "" not in by_currency):
            for key, sub_movs in by_currency.items():
                if key:
                    parts = key.split("|")
                    curr, acct_name, acct_num = parts[0], parts[1], parts[2]
                    sub_label = f"{label} — {acct_name} {acct_num} ({curr})"
                else:
                    sub_label = f"{label} (sin moneda)"
                print_movements(sub_label, sub_movs, 999)
        else:
            print_movements(label, movs, 999)

    print("\n" + "=" * 60)


def main():
    rut, password = prompt_credentials()

    data = run_scraper(rut, password)

    # Save raw JSON for inspection
    raw_path = os.path.join(os.path.dirname(__file__), "last_result.json")
    with open(raw_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  (Raw JSON saved to {raw_path})")

    # Save debug log separately
    debug_log = data.get("debug", "")
    if debug_log:
        debug_path = os.path.join(os.path.dirname(__file__), "last_debug.log")
        with open(debug_path, "w") as f:
            f.write(debug_log)
        print(f"  (Debug log saved to {debug_path})")

    display_results(data)


if __name__ == "__main__":
    main()
