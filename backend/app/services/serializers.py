from __future__ import annotations
"""
app/services/serializers.py — turn Transaction rows into API payloads.

Kept in one place so user and admin endpoints agree on shape, and so the
(potentially large) proof image is only ever included on detail requests.
"""
from typing import Iterable, Optional

from app.models import Transaction, User


def tx_view(tx: Transaction, own_wallet_ids: Optional[Iterable] = None) -> dict:
    direction = None
    if own_wallet_ids is not None:
        ids = set(own_wallet_ids)
        if tx.receiver_wallet_id in ids and tx.sender_wallet_id in ids:
            direction = None                  # internal move between own wallets
        elif tx.receiver_wallet_id in ids:
            direction = "in"
        elif tx.sender_wallet_id in ids:
            direction = "out"
    return {
        "id": tx.id,
        "amount": tx.amount,
        "currency": tx.currency,
        "tx_type": tx.tx_type,
        "description": tx.description,
        "status": tx.status,
        "direction": direction,
        "gateway_name": tx.gateway_name,
        "asset": tx.asset,
        "network": tx.network,
        "fee": tx.fee,
        "tx_hash": tx.tx_hash,
        "has_proof": bool(tx.proof_image_url),
        "withdrawal_address": tx.withdrawal_address,
        "withdrawal_details": tx.withdrawal_details,
        "payout_tx_hash": tx.payout_tx_hash,
        "rejection_reason": tx.rejection_reason,
        "reviewed_at": tx.reviewed_at,
        "created_at": tx.created_at,
    }


def admin_tx_view(tx: Transaction, user: Optional[User], include_proof: bool = False) -> dict:
    data = tx_view(tx)
    data.update(
        user_id=user.id if user else None,
        user_email=user.email if user else None,
        user_name=user.full_name if user else None,
        proof_image_url=tx.proof_image_url if include_proof else None,
    )
    return data
