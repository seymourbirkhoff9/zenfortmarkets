"""
Report (and optionally fix) wallets that are not in the base currency.

Before this release, wallets were opened in the customer's local currency
(NGN, GHS, ...) while every amount was entered in USD. The amounts were always
treated as USD, so the label is what's wrong, not the number.

    python -m scripts.normalize_wallet_currency          # report only
    python -m scripts.normalize_wallet_currency --apply  # relabel to USD

Review the report first: if you ever entered amounts in a local currency on
purpose, convert those balances by hand instead of relabelling them.
"""
import sys

from sqlalchemy import func

from app.config import settings
from app.database import SessionLocal
from app.models import Transaction, User, Wallet


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        rows = (db.query(Wallet, User.email).join(User, User.id == Wallet.user_id)
                .filter(Wallet.currency != settings.BASE_CURRENCY).order_by(User.email).all())
        if not rows:
            print(f"All wallets are already {settings.BASE_CURRENCY}.")
            return
        print(f"{len(rows)} wallet(s) not in {settings.BASE_CURRENCY}:")
        for w, email in rows:
            print(f"  {email:<40} {w.wallet_type:<7} {w.currency}  balance {w.balance}")
        if apply:
            n = db.query(Wallet).filter(Wallet.currency != settings.BASE_CURRENCY) \
                .update({Wallet.currency: settings.BASE_CURRENCY}, synchronize_session=False)
            t = db.query(Transaction).filter(Transaction.currency != settings.BASE_CURRENCY) \
                .update({Transaction.currency: settings.BASE_CURRENCY}, synchronize_session=False)
            db.commit()
            print(f"Relabelled {n} wallet(s) and {t} transaction(s) to {settings.BASE_CURRENCY}.")
        else:
            print("Nothing changed. Re-run with --apply to relabel them.")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
