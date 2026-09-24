"""Currency catalogue used by the pair search box."""

CURRENCIES: dict[str, str] = {
    "USD": "US Dollar", "EUR": "Euro", "JPY": "Japanese Yen", "GBP": "British Pound",
    "AUD": "Australian Dollar", "NZD": "New Zealand Dollar", "CAD": "Canadian Dollar",
    "CHF": "Swiss Franc", "CNY": "Chinese Yuan", "HKD": "Hong Kong Dollar",
    "SGD": "Singapore Dollar", "SEK": "Swedish Krona", "NOK": "Norwegian Krone",
    "DKK": "Danish Krone", "PLN": "Polish Zloty", "CZK": "Czech Koruna",
    "HUF": "Hungarian Forint", "TRY": "Turkish Lira", "ZAR": "South African Rand",
    "MXN": "Mexican Peso", "BRL": "Brazilian Real", "INR": "Indian Rupee",
    "KRW": "South Korean Won", "THB": "Thai Baht", "VND": "Vietnamese Dong",
    "IDR": "Indonesian Rupiah", "MYR": "Malaysian Ringgit", "PHP": "Philippine Peso",
    "TWD": "Taiwan Dollar", "ILS": "Israeli Shekel", "RUB": "Russian Ruble",
}

POPULAR_PAIRS: list[str] = [
    "EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "USD/CHF", "NZD/USD",
    "EUR/GBP", "EUR/JPY", "GBP/JPY", "USD/VND", "USD/SGD", "USD/CNY", "EUR/VND",
]


BASE_FIRST = {"EUR", "GBP", "AUD", "NZD"}


def conventional_pair(code: str) -> str:
    if code == "USD":
        return "EUR/USD"
    return f"{code}/USD" if code in BASE_FIRST else f"USD/{code}"


def describe(pair: str) -> dict:
    base, quote = pair.split("/")
    base_name = CURRENCIES.get(base, base)
    quote_name = CURRENCIES.get(quote, quote)
    return {"pair": pair, "symbol": pair.replace("/", ""), "label": f"{base_name} / {quote_name}"}


def search(query: str, limit: int = 12) -> list[dict]:
    """Rank popular pairs first, then any pair the query can form from known currencies."""
    needle = query.strip().upper().replace("-", "").replace("_", "").replace("/", "")
    if not needle:
        return [describe(pair) for pair in POPULAR_PAIRS[:limit]]

    results: list[str] = []

    def add(pair: str) -> None:
        if pair not in results:
            results.append(pair)

    for pair in POPULAR_PAIRS:
        if needle in pair.replace("/", ""):
            add(pair)

    if len(needle) == 6 and needle[:3] in CURRENCIES and needle[3:] in CURRENCIES:
        add(f"{needle[:3]}/{needle[3:]}")

    for code, name in CURRENCIES.items():
        if code.startswith(needle) or needle in name.upper():
            add(conventional_pair(code))
            for counter in ("EUR", "JPY", "GBP"):
                if counter != code:
                    add(f"{code}/{counter}")

    return [describe(pair) for pair in results[:limit]]
