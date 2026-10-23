from app.database import engine
from sqlalchemy import text

with engine.connect() as conn:
    result = conn.execute(text('SELECT currency, rate_per_usd, override_rate, is_enabled FROM fx_rates'))
    rows = result.fetchall()
    if rows:
        print("FX Rates in database:")
        for row in rows:
            print(f"  {row.currency}: rate_per_usd={row.rate_per_usd}, override_rate={row.override_rate}, is_enabled={row.is_enabled}")
    else:
        print("No FX rates found in database.")
