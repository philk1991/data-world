"""Product catalogue generator (PIM-style).

Produces three tables at three grains:
  - categories       : the department -> leaf-category hierarchy (dim_category source)
  - products         : product groups / styles (the parent of variants)
  - product_variants : the sellable SKU grain (product_group x colour x size)

Variant grain is what a real fashion PIM sells and what identity/ML reason over,
so this is the primary product table. ``product_group_id`` is carried on each
variant as the parent link.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C


def build_categories() -> pd.DataFrame:
    """One row per node in the (2-level) category hierarchy."""
    rows = []
    for dept, leaves in C.DEPARTMENTS.items():
        dept_id = C.category_id(dept)
        rows.append(dict(category_id=dept_id, category_name=dept, parent_category_id=None,
                         category_level=1, department=dept))
        for leaf in leaves:
            rows.append(dict(category_id=C.category_id(leaf), category_name=leaf,
                             parent_category_id=dept_id, category_level=2, department=dept))
    return pd.DataFrame(rows)


def build_catalogue(rng: np.random.Generator) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return (categories_df, products_df, variants_df)."""
    categories = build_categories()

    products = []
    variants = []
    pg_counter = 0
    sku_counter = 0

    for dept, leaves in C.DEPARTMENTS.items():
        for leaf in leaves:
            cat_id = C.category_id(leaf)
            for _ in range(C.GROUPS_PER_CATEGORY[leaf]):
                pg_counter += 1
                product_group_id = f"PG{pg_counter:04d}"

                brand_line = str(rng.choice(C.BRAND_LINES, p=C.BRAND_LINE_WEIGHTS))
                noun = str(rng.choice(C.CATEGORY_NOUNS[cat_id]))
                adjective = str(rng.choice(C.STYLE_ADJECTIVES))
                pattern = str(rng.choice(C.PATTERNS))
                fabric = str(rng.choice(C.FABRICS))
                price_band = str(rng.choice(C.PRICE_BANDS, p=[0.35, 0.45, 0.20]))
                lo, hi = C.PRICE_BAND_RANGE[price_band]
                base_price = round(float(rng.uniform(lo, hi)), 2)
                season = str(rng.choice(C.SEASONS))
                style_name = f"{adjective} {noun}"

                # A short synthetic PDP description — used later for embeddings.
                description = (
                    f"{style_name} in {fabric.lower()} with a {pattern.lower()} finish. "
                    f"Part of the {brand_line} {season} collection."
                )

                products.append(dict(
                    product_group_id=product_group_id,
                    style_name=style_name,
                    category_id=cat_id,
                    department=dept,
                    brand_line=brand_line,
                    pattern=pattern,
                    fabric=fabric,
                    price_band=price_band,
                    base_price=base_price,
                    season=season,
                    description=description,
                ))

                # Sizing depends on category (accessories are one-size) and brand
                # line (Petite uses the shorter petite range).
                if cat_id in C.ACCESSORY_CATEGORIES:
                    sizes, size_range = C.SIZE_ONE, "one_size"
                elif brand_line == "Petite":
                    sizes, size_range = C.SIZES_PETITE, "petite"
                else:
                    sizes, size_range = C.SIZES_STANDARD, "standard"

                n_colours = int(rng.integers(1, 4))  # 1..3 colourways
                colourways = list(rng.choice(C.COLOURS, size=n_colours, replace=False))

                for colour in colourways:
                    for size in sizes:
                        sku_counter += 1
                        # Small per-variant price jitter around the group base price.
                        price = round(base_price * float(rng.uniform(0.98, 1.05)), 2)
                        variants.append(dict(
                            variant_id=f"SKU{sku_counter:06d}",
                            product_group_id=product_group_id,
                            style_name=style_name,
                            category_id=cat_id,
                            department=dept,
                            brand_line=brand_line,
                            colour=str(colour),
                            size=size,
                            size_range=size_range,
                            pattern=pattern,
                            fabric=fabric,
                            price_band=price_band,
                            price=price,
                            season=season,
                            stock_level=int(rng.integers(0, 120)),
                            is_active=bool(rng.random() > 0.05),
                        ))

    return categories, pd.DataFrame(products), pd.DataFrame(variants)
