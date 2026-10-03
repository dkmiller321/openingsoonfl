"""Guess a cuisine from a business name (M3). Rules are checked in order; first match wins.

Each rule has whole words/phrases (matched on word boundaries) and stems (matched anywhere
in a word, for names like FATBURGER or TACOMANIACS). Unmatched names return None.
"""

from __future__ import annotations

import re

ICONS = {
    "hotel": "\U0001f3e8", "pizza": "\U0001f355", "sushi": "\U0001f363", "asian": "\U0001f35c",
    "mexican": "\U0001f32e", "bbq": "\U0001f356", "seafood": "\U0001f990", "burger": "\U0001f354",
    "hotdog": "\U0001f32d", "chicken": "\U0001f357", "breakfast": "\U0001f9c7",
    "bakery": "\U0001f96f", "icecream": "\U0001f366", "drinks": "\U0001f964",
    "coffee": "☕", "sandwich": "\U0001f96a", "latin": "\U0001f958",
    "caribbean": "\U0001f33a", "italian": "\U0001f35d", "mediterranean": "\U0001f959",
    "indian": "\U0001f35b", "bar": "\U0001f37a",
}
DEFAULT_ICON = "\U0001f37d️"
MOBILE_ICON = "\U0001f69a"

# (cuisine, whole words / phrases, stems)
RULES: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = [
    ("hotel", ("HOTEL", "INN", "SUITES", "RESORT", "HILTON", "MARRIOTT", "MARRIOT"), ()),
    ("pizza", ("PAPA JOHN", "PAPA JOHNS", "LITTLE CAESARS", "DOMINOS", "PIES"), ("PIZZ",)),
    ("sushi", ("HIBACHI", "JAPAN", "JAPANESE"), ("SUSHI",)),
    ("asian", ("PHO", "RAMEN", "NOODLE", "NOODLES", "THAI", "CHINESE", "WOK", "VIETNAMESE",
               "ASIAN", "KOREAN", "DUMPLING", "BANGKOK", "BOWL", "RICE"), ()),
    ("mexican", ("CHIPOTLE", "MEXICAN", "BURRITO", "CANTINA", "TAQUERIA", "TEQUILA",
                 "ANTOJITOS", "TEX MEX"), ("TACO",)),
    ("bbq", ("BARBECUE", "SMOKEHOUSE", "BRISKET", "SMOKE"), ("BBQ",)),
    ("seafood", ("FISH", "CRAB", "OYSTER", "SHRIMP", "LOBSTER", "GALLEY"), ("SEAFOOD",)),
    ("burger", ("CULVERS", "STEAK N SHAKE", "MCDONALDS", "MCDONALD", "SMASH"), ("BURGER",)),
    ("hotdog", ("DOG", "DOGS", "DOGZ"), ("HOTDOG", "DAWG", "CORNDOG")),
    ("chicken", ("CHICKEN", "WINGS", "WING", "POPEYES"), ("WINGSTOP",)),
    ("breakfast", ("DINER", "BREAKFAST", "BRUNCH", "TURNING POINT", "PANCAKE", "PANCAKES",
                   "EGGS", "GRIDDLE"),
     ("WAFFLE", "CREPE")),
    ("bakery", ("BAKERY", "BREAD", "PASTRY", "CAKE", "CAKES", "COOKIE", "COOKIES", "PRETZELS",
                "DOUGH", "CRUMBS"), ("BAGEL", "DONUT", "DOUGHNUT")),
    ("icecream", ("ICE CREAM", "GELATO", "GELAZZO", "GELO", "CREAMERY", "CUSTARD", "SCOOP",
                  "YOGURT", "SWEET", "TREATS"), ()),
    ("drinks", ("TEA", "JUICE", "LEMONADE", "SQUEEZE", "FRUITS", "BOBA", "SIPS", "PLAYA BOWLS"),
     ("SMOOTHIE",)),
    ("coffee", ("COFFEE", "ESPRESSO", "ROASTERS", "DUNKIN", "GRIND"), ("CAFE",)),
    ("sandwich", ("JIMMY JOHN", "JIMMY JOHNS", "SUBWAY", "SUBS", "DELI", "CHEESESTEAK",
                  "CHEESESTEAKS", "PHILLY", "PANERA", "PATTIES", "SANDWICH"), ()),
    ("latin", ("CUBAN", "CUBANITA", "LATIN", "LATINA", "PAELLA", "EMPANADA", "AREPA",
               "PINCHOS", "BORINQUBANA", "COCINITA", "BRASA"), ()),
    ("caribbean", ("HAWAIIAN", "ISLAND", "TROPICAL", "CARIBBEAN", "MENEHUNE"), ("JERK",)),
    ("italian", ("ITALIAN", "PASTA", "TRATTORIA", "RISTORANTE"), ()),
    ("mediterranean", ("PITA", "GYRO", "FALAFEL", "KEBAB", "SHAWARMA", "GREEK", "MOROCCO"), ()),
    ("indian", ("INDIAN", "CURRY", "TANDOORI", "MASALA"), ()),
    ("bar", ("BAR", "PUB", "TAVERN", "TAP", "TAPROOM", "WINE", "BEER", "SALOON", "LOUNGE",
             "WHISKEY", "BREWERY", "BREWING", "DAVE AND BUSTERS"), ()),
]


def _normalise(name: str) -> str:
    text = name.upper().replace("'", "").replace("’", "").replace("&", " AND ")
    return " " + " ".join(re.sub(r"[^A-Z0-9]+", " ", text).split()) + " "


def guess_cuisine(name: str) -> str | None:
    padded = _normalise(name)
    words = padded.split()
    for cuisine, phrases, stems in RULES:
        if any(f" {phrase} " in padded for phrase in phrases):
            return cuisine
        if any(stem in word for stem in stems for word in words):
            return cuisine
    return None


def cuisine_icon(cuisine: str | None, lead_type: str) -> str:
    if cuisine:
        return ICONS[cuisine]
    return MOBILE_ICON if lead_type == "mobile" else DEFAULT_ICON
