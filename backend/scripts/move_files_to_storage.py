"""
Move ID documents and payment screenshots that are still stored inside the database
(as data: URLs, from before file storage existed) into storage.

    python -m scripts.move_files_to_storage           # preview: counts and sizes only
    python -m scripts.move_files_to_storage --apply   # move them

Uses whichever storage the app is configured for (Supabase Storage when SUPABASE_URL and
SUPABASE_SERVICE_ROLE_KEY are set). Each row is committed on its own, so it can be re-run safely;
rows already moved are skipped.
"""
import sys

from app.database import SessionLocal
from app.models import Transaction, User
from app.services import storage


def main(apply: bool) -> None:
    db = SessionLocal()
    try:
        users = db.query(User).filter(User.kyc_document_url.like("data:%")).all()
        txs = db.query(Transaction).filter(Transaction.proof_image_url.like("data:%")).all()
        size = sum(len(u.kyc_document_url) for u in users) + sum(len(t.proof_image_url) for t in txs)
        target = type(storage.backend()).__name__
        print(f"{len(users)} ID document(s) and {len(txs)} payment screenshot(s) in the database "
              f"(~{size / 1_000_000:.1f} MB). Destination: {target}.")
        if not apply:
            print("Nothing changed. Re-run with --apply to move them.")
            return
        for u in users:
            u.kyc_document_url = storage.store(u.kyc_document_url, f"kyc/{u.id}", private=True)
            db.commit()
        for t in txs:
            owner = t.receiver_wallet_id or t.sender_wallet_id or "legacy"
            t.proof_image_url = storage.store(t.proof_image_url, f"proofs/{owner}", private=True)
            db.commit()
        print(f"Moved {len(users) + len(txs)} file(s).")
    finally:
        db.close()


if __name__ == "__main__":
    main("--apply" in sys.argv)
