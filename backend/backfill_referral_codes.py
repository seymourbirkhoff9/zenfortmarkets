"""
backfill_referral_codes.py — Generate referral codes for existing users

Run this script after applying the migration to backfill referral codes
for existing users who don't have one yet.
"""

import sys
import os
import random
import string

# Add the parent directory to the path to import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import get_db
from app.models import User


def generate_unique_referral_code(db_session) -> str:
    """Generate a unique 8-character uppercase alphanumeric referral code."""
    while True:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        existing = db_session.query(User).filter(User.referral_code == code).first()
        if not existing:
            return code


def backfill_referral_codes():
    """Generate referral codes for all users who don't have one."""
    db = next(get_db())
    
    try:
        # Find users without referral codes (empty string or None)
        users_without_codes = db.query(User).filter(
            (User.referral_code == None) | (User.referral_code == "")
        ).all()
        
        print(f"Found {len(users_without_codes)} users without referral codes")
        
        for user in users_without_codes:
            code = generate_unique_referral_code(db)
            user.referral_code = code
            print(f"Generated referral code '{code}' for user {user.email}")
        
        db.commit()
        print(f"\nSuccessfully backfilled {len(users_without_codes)} referral codes")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 60)
    print("BACKFILL REFERRAL CODES FOR EXISTING USERS")
    print("=" * 60)
    backfill_referral_codes()
    print("=" * 60)
