from dataclasses import replace
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from ingestion.rba.fx import parse_f11

FIXTURE = Path(__file__).parent / "fixtures" / "rba_f11_1_sample.csv"


@pytest.fixture(scope="module")
def rates():
    return parse_f11(FIXTURE)


def by_key(rates):
    return {(r.series_id, r.rate_date): r for r in rates}


def test_parses_every_non_blank_cell(rates):
    # Fixture has 3 dates x 23 series, with 4 blank cells on each 2023 date and 2 on 23-Oct-2026.
    assert len(rates) == 3 * 23 - 4 - 4 - 2


def test_reads_values_as_decimal_with_metadata(rates):
    usd = by_key(rates)[("FXRUSD", date(2023, 1, 3))]
    assert usd.value == Decimal("0.6828")
    assert usd.units == "USD"
    assert usd.title == "A$1=USD"
    assert usd.publication_date == date(2026, 10, 23)


def test_skips_blank_cells(rates):
    assert ("FXRUAED", date(2023, 1, 3)) not in by_key(rates)


def test_hash_ignores_publication_date(rates):
    r = rates[0]
    assert replace(r, publication_date=date(2030, 1, 1)).hash == r.hash
    assert replace(r, value=r.value + 1).hash != r.hash


def test_rejects_file_without_series_id_row(tmp_path):
    bad = tmp_path / "bad.csv"
    bad.write_text("Title,A$1=USD\n03-Jan-2023,0.6828\n")
    with pytest.raises(ValueError, match="Series ID"):
        parse_f11(bad)
