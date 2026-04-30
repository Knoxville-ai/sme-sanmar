"""Tests for the SDL CSV mainframe-color resolver."""

from __future__ import annotations

from pathlib import Path

import pytest

from skills.sanmar.ftp_resolver import lookup_mainframe_color


_SDL_CSV = (
    '"UNIQUE_KEY","PRODUCT_TITLE","PRODUCT_DESCRIPTION","STYLE#","AVAILABLE_SIZES",'
    '"COLOR_NAME","SIZE","INVENTORY_KEY","SIZE_INDEX","SANMAR_MAINFRAME_COLOR"\n'
    '"100_3","Port & Co Tee","desc","PC55","S-4XL",'
    '"Black","L","100","3","BLACK"\n'
    '"100_4","Port & Co Tee","desc","PC55","S-4XL",'
    '"Black","XL","100","4","BLACK"\n'
    '"101_3","Port & Co Tee","desc","PC55","S-4XL",'
    '"Athletic Heather","L","101","3","ATHHTHR"\n'
    '"102_3","Port & Co Tee","desc","PC55","S-4XL",'
    '"Navy","L","102","3","NAVY"\n'
    '"200_3","Other Tee","desc","ST350","S-4XL",'
    '"Black","L","200","3","BLACK"\n'
)


@pytest.fixture
def sdl_csv(tmp_path: Path) -> Path:
    p = tmp_path / "SanMar_SDL_N.csv"
    p.write_text(_SDL_CSV, encoding="utf-8")
    return p


def test_resolve_marketing_color_to_mainframe(sdl_csv: Path) -> None:
    res = lookup_mainframe_color(
        style="PC55", color="Athletic Heather", size="L", csv_path=sdl_csv
    )
    assert res.status == "matched"
    assert len(res.matches) == 1
    m = res.matches[0]
    assert m.mainframe_color == "ATHHTHR"
    assert m.color_name == "Athletic Heather"
    assert m.inventory_key == "101"
    assert m.size_index == "3"


def test_resolve_is_case_insensitive(sdl_csv: Path) -> None:
    res = lookup_mainframe_color(
        style="pc55", color="black", size="l", csv_path=sdl_csv
    )
    assert res.status == "matched"
    assert res.matches[0].mainframe_color == "BLACK"


def test_resolve_without_size_collapses_duplicate_mainframe_colors(sdl_csv: Path) -> None:
    """Black exists in L and XL — same mainframe color, distinct sizes.

    Without a size filter the result should still be 'matched' because
    only one *mainframe color* is involved.
    """

    res = lookup_mainframe_color(style="PC55", color="Black", csv_path=sdl_csv)
    assert res.status == "matched"
    assert {m.mainframe_color for m in res.matches} == {"BLACK"}
    assert {m.size for m in res.matches} == {"L", "XL"}


def test_resolve_not_found(sdl_csv: Path) -> None:
    res = lookup_mainframe_color(
        style="PC55", color="Tangerine Sunset", size="L", csv_path=sdl_csv
    )
    assert res.status == "not_found"
    assert res.matches == []


def test_resolve_unknown_style(sdl_csv: Path) -> None:
    res = lookup_mainframe_color(
        style="DOESNOTEXIST", color="Black", size="L", csv_path=sdl_csv
    )
    assert res.status == "not_found"


def test_resolve_csv_missing_raises(tmp_path: Path) -> None:
    from skills.sanmar.ftp_resolver import SanMarFTPError

    with pytest.raises(SanMarFTPError):
        lookup_mainframe_color(
            style="PC55",
            color="Black",
            csv_path=tmp_path / "missing.csv",
        )


def test_lookup_records_as_of_timestamp(sdl_csv: Path) -> None:
    res = lookup_mainframe_color(
        style="PC55", color="Black", size="L", csv_path=sdl_csv
    )
    assert res.as_of is not None
    assert res.source_file.endswith("SanMar_SDL_N.csv")
