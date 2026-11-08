"""Census data for the place rule: each Swiss municipality's population, area and degree of urbanisation.

The project's EOD specialist asked for census population density as a factor for the place (8 November 2026), and
chose the official urban/rural class: Eurostat's degree of urbanisation (DEGURBA), which classes every local
administrative unit as a city (densely populated), a town or suburb (intermediate density) or a rural area (thinly
populated), from the census population grid. A find in a city counts as a much-used place.

Source: Eurostat, correspondence table "EU-27-LAU-2025-NUTS-2024.xlsx" (sheet CH: 2,131 Swiss municipalities,
population for 2024), downloaded on 8 November 2026 from https://ec.europa.eu/eurostat/web/nuts/local-administrative-units.
Reuse is authorised provided the source is acknowledged (Eurostat copyright notice). Changes made here: only the
Swiss sheet is kept, the columns are renamed, the area is converted to km2 and the density is computed; Eurostat is
not responsible for this extract.
"""
import hashlib
from pathlib import Path

import pandas as pd

DATA_DIR = Path("data")
MUNICIPALITIES_CSV = "ch_municipalities_degurba.csv"
SHA256 = "23f1f6d8d27d0bb75d17a2a80b0507f65743e9649cc47447c74064f29b23bd18"
CITY = 1        # DEGURBA class 1: cities (densely populated areas)


def load_municipalities(data_dir=DATA_DIR):
    """The municipalities table, checked: its checksum, one row per municipality, every class 1 to 3, population and area > 0."""
    path = Path(data_dir) / MUNICIPALITIES_CSV
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise ValueError(f"{path} differs from its recorded checksum")
    table = pd.read_csv(path)
    assert table.bfs_number.is_unique, "a municipality appears twice"
    assert table.degurba.isin([1, 2, 3]).all(), "a class outside 1 to 3"
    assert (table.population > 0).all() and (table.area_km2 > 0).all(), "a population or area of zero"
    return table


def densely_populated(table, municipality):
    """True when the named municipality is a city in Eurostat's degree of urbanisation (class 1).

    The name must match one municipality exactly; an unknown name raises an error rather than guess.
    """
    rows = table[table.municipality == municipality]
    if len(rows) != 1:
        raise KeyError(f"{municipality!r} matches {len(rows)} municipalities")
    return int(rows.degurba.iloc[0]) == CITY
