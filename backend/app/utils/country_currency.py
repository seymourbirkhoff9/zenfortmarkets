"""
app/utils/country_currency.py
Offline, zero-network country → ISO 4217 currency resolution using pycountry.

Resolution chain:
  1. pycountry.countries.search_fuzzy(name) → alpha-2 code
  2. alpha-2 → currency via ALPHA2_TO_CURRENCY dict
  3. Fallback → "USD"

Never raises — always returns a non-empty string.
"""
import logging
from typing import Optional

import pycountry

logger = logging.getLogger("zenfort.country")

# ──────────────────────────────────────────────────────────────────
# Alpha-2 → Primary ISO 4217 fiat currency
# Sources: ISO 4217, xe.com reference data
# ──────────────────────────────────────────────────────────────────
ALPHA2_TO_CURRENCY: dict = {
    # Africa
    "NG": "NGN",  # Nigeria
    "GH": "GHS",  # Ghana
    "KE": "KES",  # Kenya
    "ZA": "ZAR",  # South Africa
    "TZ": "TZS",  # Tanzania
    "ET": "ETB",  # Ethiopia
    "CM": "XAF",  # Cameroon
    "SN": "XOF",  # Senegal
    "CI": "XOF",  # Ivory Coast
    "ZM": "ZMW",  # Zambia
    "ZW": "ZWL",  # Zimbabwe
    "EG": "EGP",  # Egypt
    "MA": "MAD",  # Morocco
    "DZ": "DZD",  # Algeria
    "TN": "TND",  # Tunisia
    "UG": "UGX",  # Uganda
    "RW": "RWF",  # Rwanda
    "AO": "AOA",  # Angola
    "MZ": "MZN",  # Mozambique
    "MG": "MGA",  # Madagascar
    # Europe
    "GB": "GBP",  # United Kingdom
    "FR": "EUR",  # France
    "DE": "EUR",  # Germany
    "ES": "EUR",  # Spain
    "IT": "EUR",  # Italy
    "NL": "EUR",  # Netherlands
    "PT": "EUR",  # Portugal
    "BE": "EUR",  # Belgium
    "AT": "EUR",  # Austria
    "FI": "EUR",  # Finland
    "GR": "EUR",  # Greece
    "IE": "EUR",  # Ireland
    "SE": "SEK",  # Sweden
    "NO": "NOK",  # Norway
    "DK": "DKK",  # Denmark
    "PL": "PLN",  # Poland
    "CH": "CHF",  # Switzerland
    "UA": "UAH",  # Ukraine
    "RU": "RUB",  # Russia
    "TR": "TRY",  # Turkey
    "CZ": "CZK",  # Czech Republic
    "HU": "HUF",  # Hungary
    "RO": "RON",  # Romania
    # Americas
    "US": "USD",  # United States
    "CA": "CAD",  # Canada
    "BR": "BRL",  # Brazil
    "MX": "MXN",  # Mexico
    "AR": "ARS",  # Argentina
    "CO": "COP",  # Colombia
    "CL": "CLP",  # Chile
    "PE": "PEN",  # Peru
    "VE": "VES",  # Venezuela
    # Asia-Pacific
    "IN": "INR",  # India
    "CN": "CNY",  # China
    "JP": "JPY",  # Japan
    "SG": "SGD",  # Singapore
    "AU": "AUD",  # Australia
    "NZ": "NZD",  # New Zealand
    "ID": "IDR",  # Indonesia
    "MY": "MYR",  # Malaysia
    "PK": "PKR",  # Pakistan
    "BD": "BDT",  # Bangladesh
    "TH": "THB",  # Thailand
    "VN": "VND",  # Vietnam
    "PH": "PHP",  # Philippines
    "KR": "KRW",  # South Korea
    "TW": "TWD",  # Taiwan
    "HK": "HKD",  # Hong Kong
    "LK": "LKR",  # Sri Lanka
    "NP": "NPR",  # Nepal
    "MM": "MMK",  # Myanmar
    "KH": "KHR",  # Cambodia
    # Middle East
    "AE": "AED",  # United Arab Emirates
    "SA": "SAR",  # Saudi Arabia
    "QA": "QAR",  # Qatar
    "KW": "KWD",  # Kuwait
    "BH": "BHD",  # Bahrain
    "OM": "OMR",  # Oman
    "IQ": "IQD",  # Iraq
    "IR": "IRR",  # Iran
    "IL": "ILS",  # Israel
    "JO": "JOD",  # Jordan
}

FALLBACK_CURRENCY = "USD"

# Common aliases that pycountry's fuzzy search gets wrong
ALIASES: dict = {
    "uk":           "United Kingdom",
    "usa":          "United States",
    "us":           "United States",
    "uae":          "United Arab Emirates",
    "drc":          "Democratic Republic of the Congo",
    "korea":        "South Korea",
    "south korea":  "South Korea",
    "taiwan":       "Taiwan",
    "russia":       "Russian Federation",
    "iran":         "Iran",
    "syria":        "Syria",
    "czech republic": "Czechia",
    "ivory coast":  "Côte d'Ivoire",
}


def get_currency_for_country(country_name: Optional[str]) -> str:
    """
    Return the ISO 4217 currency code for the given country name.

    Uses pycountry.countries.search_fuzzy() so it handles:
      - Any case:  "france", "FRANCE", "France" → EUR
      - Common aliases: "UK" → GBP,  "USA" → USD
      - Slight misspellings (fuzzy search)

    Always returns a non-empty string; defaults to "USD" on any failure.
    """
    if not country_name or not country_name.strip():
        return FALLBACK_CURRENCY

    cleaned = country_name.strip()
    lower_cleaned = cleaned.lower()

    # Normalise common abbreviations or title-case regular names for fuzzy search
    if lower_cleaned in ALIASES:
        normalised = ALIASES[lower_cleaned]
    else:
        normalised = cleaned.title()

    try:
        matches = pycountry.countries.search_fuzzy(normalised)
        if not matches:
            raise LookupError("No match found")

        alpha2: str = matches[0].alpha_2
        currency = ALPHA2_TO_CURRENCY.get(alpha2)

        if currency:
            logger.debug(
                "Currency resolved: '%s' → alpha-2=%s → %s",
                country_name, alpha2, currency,
            )
            return currency

        logger.warning(
            "Alpha-2 '%s' not in currency map for '%s', defaulting to %s",
            alpha2, country_name, FALLBACK_CURRENCY,
        )
        return FALLBACK_CURRENCY

    except LookupError:
        logger.warning(
            "pycountry could not match '%s', defaulting to %s",
            country_name, FALLBACK_CURRENCY,
        )
        return FALLBACK_CURRENCY

