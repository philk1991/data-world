"""Central configuration for the Verano synthetic-data generators.

Everything that shapes the dataset lives here so the whole build is deterministic
(one global seed) and easy to reason about for the interview walk-through. Each
generator derives its own child RNG from the global seed via ``child_rng`` so the
streams stay independent and reproducible.
"""
from __future__ import annotations

import os
from datetime import date, datetime

import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# Environment / run parameters
# ─────────────────────────────────────────────────────────────────────────────

# Absolute path to the DuckDB file. Falls back to the repo-relative location so
# the generators run even without a .env (dbt reads the same file).
_DEFAULT_DB = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "verano.duckdb")
DUCKDB_PATH = os.environ.get("VERANO_DUCKDB_PATH", _DEFAULT_DB)

SEED = int(os.environ.get("VERANO_SEED", "42"))

WINDOW_START = datetime.fromisoformat(os.environ.get("VERANO_WINDOW_START", "2025-11-01"))
WINDOW_END = datetime.fromisoformat(os.environ.get("VERANO_WINDOW_END", "2026-04-30"))

# ─────────────────────────────────────────────────────────────────────────────
# Population sizes
# ─────────────────────────────────────────────────────────────────────────────

N_CUSTOMERS = 5_000
# Anonymous-only visitors with no customer record. They generate the bulk of the
# (never-identified) traffic — this is what keeps the identification rate low and
# realistic, since only known customers can trip a deterministic signal.
N_ANON_VISITORS = 9_000

MIN_EVENTS_TARGET = 100_000  # sanity floor; the generator asserts we clear this

# ─────────────────────────────────────────────────────────────────────────────
# Brand lines (mirrors Roman / Roman Petite / Roman Dusk)
# ─────────────────────────────────────────────────────────────────────────────

BRAND_LINES = ["Verano", "Petite", "Dusk"]          # Dusk = occasion/eveningwear
BRAND_LINE_WEIGHTS = [0.62, 0.23, 0.15]

# ─────────────────────────────────────────────────────────────────────────────
# Category hierarchy (department -> leaf category). Petite is modelled as a brand
# line + petite sizing rather than a category — a deliberate modelling choice
# (see README); the spec lists "Petite range" among categories but it is really
# a size range that cross-cuts the clothing categories.
# ─────────────────────────────────────────────────────────────────────────────

DEPARTMENTS: dict[str, list[str]] = {
    "Clothing": ["Dresses", "Tops", "Knitwear", "Outerwear", "Trousers", "Denim", "Occasionwear"],
    "Accessories": ["Bags", "Jewellery", "Scarves & Wraps"],
}

# Number of product groups (styles) to generate per leaf category. Total variants
# lands near ~2,000 once colourways x sizes are expanded (see catalogue.py).
GROUPS_PER_CATEGORY = {
    "Dresses": 30, "Occasionwear": 22, "Tops": 26, "Knitwear": 18, "Outerwear": 12,
    "Trousers": 15, "Denim": 12, "Bags": 12, "Jewellery": 14, "Scarves & Wraps": 8,
}


def category_id(name: str) -> str:
    """Stable slug id for a leaf category, e.g. 'Scarves & Wraps' -> 'scarves_wraps'."""
    return name.lower().replace(" & ", "_").replace(" ", "_")


CLOTHING_CATEGORIES = {category_id(c) for c in DEPARTMENTS["Clothing"]}
ACCESSORY_CATEGORIES = {category_id(c) for c in DEPARTMENTS["Accessories"]}

# ─────────────────────────────────────────────────────────────────────────────
# Sizing (UK womenswear). Petite line uses a shifted, shorter range.
# ─────────────────────────────────────────────────────────────────────────────

SIZES_STANDARD = ["8", "10", "12", "14", "16", "18", "20"]
SIZES_PETITE = ["6", "8", "10", "12", "14", "16"]
SIZE_ONE = ["One Size"]

# How often a customer's browsing filters to their own home size (size-driven
# browsing is a strong fashion behaviour).
P_FILTER_TO_HOME_SIZE = 0.7

# ─────────────────────────────────────────────────────────────────────────────
# Product attribute vocabularies (fashion-flavoured)
# ─────────────────────────────────────────────────────────────────────────────

COLOURS = ["Black", "Navy", "Ivory", "Blush", "Burgundy", "Emerald", "Camel",
           "Dusky Pink", "Cobalt", "Sage", "Rust", "Charcoal", "Red", "Teal"]

PATTERNS = ["Plain", "Floral", "Polka Dot", "Striped", "Animal Print", "Geometric",
            "Paisley", "Checked", "Embellished", "Lace"]

FABRICS = ["Cotton", "Viscose", "Jersey", "Wool Blend", "Linen", "Satin",
           "Chiffon", "Ponte", "Denim", "Faux Leather", "Cashmere Blend", "Sequin"]

PRICE_BANDS = ["Value", "Core", "Premium"]
PRICE_BAND_RANGE = {"Value": (12, 28), "Core": (28, 65), "Premium": (65, 140)}

SEASONS = ["AW25", "Winter Party", "SS26", "Spring Occasion"]

# Style-name building blocks per category (adjective pool + noun).
CATEGORY_NOUNS = {
    "dresses": ["Midi Dress", "Wrap Dress", "Shirt Dress", "Skater Dress", "Tea Dress"],
    "occasionwear": ["Maxi Gown", "Sequin Dress", "Occasion Jumpsuit", "Cape Dress", "Bardot Gown"],
    "tops": ["Blouse", "Shell Top", "Wrap Top", "Tunic", "Camisole"],
    "knitwear": ["Jumper", "Cardigan", "Knit Dress", "Roll Neck", "Tunic Knit"],
    "outerwear": ["Coat", "Trench", "Padded Jacket", "Wrap Coat", "Blazer"],
    "trousers": ["Tailored Trouser", "Wide Leg Trouser", "Culotte", "Cigarette Trouser"],
    "denim": ["Straight Jean", "Bootcut Jean", "Denim Jacket", "Denim Skirt", "Slim Jean"],
    "bags": ["Tote Bag", "Cross Body Bag", "Clutch", "Shoulder Bag"],
    "jewellery": ["Necklace", "Earrings", "Bracelet", "Brooch"],
    "scarves_wraps": ["Scarf", "Wrap", "Pashmina", "Snood"],
}
STYLE_ADJECTIVES = ["Floral", "Classic", "Cable", "Pleated", "Belted", "Cowl Neck",
                    "Fluted", "Textured", "Longline", "Cropped", "Statement", "Soft Touch"]

# ─────────────────────────────────────────────────────────────────────────────
# Seasonality — monthly demand multiplier per leaf category. Drives both browsing
# and purchasing volume by month, so the dataset shows real seasonal spikes.
# Months not listed default to 1.0.
# ─────────────────────────────────────────────────────────────────────────────

SEASONAL_WEIGHTS = {
    "occasionwear": {11: 1.6, 12: 2.3, 1: 0.7, 2: 0.8, 3: 1.0, 4: 1.3},
    "dresses":      {11: 0.8, 12: 0.9, 1: 0.8, 2: 0.9, 3: 1.2, 4: 1.5},
    "knitwear":     {11: 1.6, 12: 1.5, 1: 1.3, 2: 1.1, 3: 0.8, 4: 0.5},
    "outerwear":    {11: 1.7, 12: 1.4, 1: 1.5, 2: 1.2, 3: 0.8, 4: 0.5},
    "denim":        {11: 1.0, 12: 0.9, 1: 1.2, 2: 1.0, 3: 1.0, 4: 1.0},
    "tops":         {11: 1.0, 12: 1.1, 1: 0.9, 2: 1.0, 3: 1.1, 4: 1.1},
    "trousers":     {11: 1.1, 12: 1.0, 1: 1.0, 2: 1.0, 3: 1.0, 4: 1.0},
    "bags":         {11: 1.1, 12: 1.8, 1: 0.8, 2: 0.9, 3: 0.9, 4: 1.0},
    "jewellery":    {11: 1.2, 12: 2.0, 1: 0.7, 2: 1.1, 3: 0.9, 4: 1.0},
    "scarves_wraps": {11: 1.5, 12: 1.9, 1: 1.2, 2: 0.9, 3: 0.6, 4: 0.4},
}


def seasonal_weight(cat_id: str, month: int) -> float:
    """Demand multiplier for a category in a given month (default 1.0)."""
    return SEASONAL_WEIGHTS.get(cat_id, {}).get(month, 1.0)


# Categories with elevated return rates (fit/occasion driven).
RETURN_RATE = {
    "occasionwear": 0.35, "denim": 0.30, "dresses": 0.20, "trousers": 0.18,
    "outerwear": 0.15, "knitwear": 0.12, "tops": 0.10,
    "bags": 0.04, "jewellery": 0.06, "scarves_wraps": 0.05,
}
RETURN_REASONS = ["Too small", "Too large", "Not as pictured", "Changed mind",
                  "Faulty", "Quality not as expected"]

# Commercially sensible cross-sell. When a basket contains the key category, a
# complementary item from one of the mapped categories may be added — this is
# what creates a learnable "customers also bought" signal in Stage 5.
COMPLEMENTS = {
    "dresses": ["jewellery", "bags", "scarves_wraps"],
    "occasionwear": ["jewellery", "bags", "scarves_wraps"],
    "knitwear": ["tops", "trousers", "scarves_wraps"],
    "outerwear": ["knitwear", "scarves_wraps"],
    "trousers": ["tops", "knitwear"],
    "denim": ["tops", "knitwear"],
    "tops": ["trousers", "denim"],
}
P_CROSS_SELL = 0.45  # chance a complementary item is added to a converting basket

# ─────────────────────────────────────────────────────────────────────────────
# Behavioural / funnel parameters
# ─────────────────────────────────────────────────────────────────────────────

P_CUSTOMER_ACTIVE = 0.72          # known customers that browse at all in the window
MEAN_SESSIONS_KNOWN = 3.2         # Poisson mean sessions for an active known customer
MEAN_SESSIONS_ANON = 1.4          # Poisson mean sessions for an anonymous visitor

# Within a known-customer session, chance of each deterministic identity signal.
P_LOGIN = 0.28                    # logs in
P_EMAIL_SOURCED = 0.16            # arrived via an email link (encoded customer id)
P_LOYALTY_SIGNUP = 0.015          # signs up to loyalty this session

# Cookie behaviour — the basis for the *probabilistic* identity signals.
P_COOKIE_RESET = 0.18             # a visitor's cookie churns between sessions
P_SECOND_DEVICE = 0.35            # visitor uses a second device (own cookie/UA/IP)
P_SHARED_HOUSEHOLD_IP = 0.06      # session shares a household IP with another visitor

# Funnel conversion (per session).
P_ADD_TO_CART = 0.22
P_PURCHASE_GIVEN_CART = 0.35      # -> ~7.7% session purchase rate
P_SEARCH = 0.30                   # session includes a search
P_MARKETPLACE_ORDER = 0.15        # share of orders that are Mirakl marketplace orders

TRAFFIC_SOURCES = ["organic", "direct", "paid_search", "email", "social", "affiliate"]
TRAFFIC_SOURCE_WEIGHTS = [0.30, 0.22, 0.18, 0.12, 0.13, 0.05]

DEVICE_TYPES = ["mobile", "desktop", "tablet"]
DEVICE_WEIGHTS = [0.63, 0.30, 0.07]
USER_AGENTS = {
    "mobile": ["Mozilla/5.0 (iPhone; CPU iPhone OS 17_5) Safari/604.1",
               "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/125.0 Mobile"],
    "desktop": ["Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0",
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_5) Safari/17.5"],
    "tablet": ["Mozilla/5.0 (iPad; CPU OS 17_5) Safari/604.1"],
}

UK_REGIONS = ["North West", "North East", "Yorkshire", "West Midlands", "East Midlands",
              "South East", "South West", "London", "East of England", "Scotland", "Wales"]
POSTCODE_AREAS = ["M", "L", "LS", "S", "B", "NG", "SW", "SE", "BR", "CB", "G", "CF", "NE"]

LOYALTY_TIERS = [None, "Bronze", "Silver", "Gold"]

# Name pools (small, deterministic — enough variety for 5k customers).
FIRST_NAMES = ["Emma", "Olivia", "Sophie", "Charlotte", "Grace", "Amelia", "Jessica",
               "Hannah", "Lucy", "Chloe", "Megan", "Rebecca", "Laura", "Katie", "Rachel",
               "Sarah", "Emily", "Hollie", "Abigail", "Georgia", "Alice", "Ruth", "Nadia",
               "Priya", "Aisha", "Fiona", "Claire", "Danielle", "Bethany", "Zoe"]
LAST_NAMES = ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Evans",
              "Thomas", "Roberts", "Walker", "Wright", "Green", "Hall", "Wood", "Clarke",
              "Patel", "Khan", "Hughes", "Edwards", "Turner", "Hill", "Moore", "Ward",
              "Cooper", "Bailey", "Murphy", "Kelly", "Shaw", "Ellis", "Marsh"]


# ─────────────────────────────────────────────────────────────────────────────
# RNG helpers
# ─────────────────────────────────────────────────────────────────────────────

# Fixed offsets give each generator an independent, reproducible stream.
RNG_OFFSETS = {
    "catalogue": 1, "customers": 2, "events": 3, "orders": 4, "search": 5, "email": 6,
}


def child_rng(name: str) -> np.random.Generator:
    """Return a deterministic RNG for a named generator module."""
    return np.random.default_rng(SEED + RNG_OFFSETS[name])


def window_days() -> int:
    return (WINDOW_END - WINDOW_START).days
