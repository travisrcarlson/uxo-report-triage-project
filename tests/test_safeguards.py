"""Offline tests: the floor, the advice checks and the agent's safeguards, with the scripted stand-in model.

Run from the repository root:  python -m pytest tests
"""
from itertools import combinations

import pytest

from triage import advice as advice_mod
from triage import floor as floor_mod
from triage.selftest import Bench, safeguard_tests


@pytest.fixture(scope="module")
def bench():
    return Bench()


def test_safeguards_fire(bench):
    failed = [t for t in safeguard_tests(bench) if not t["fired as designed"]]
    assert not failed, failed


def test_advice_comes_from_the_rules():
    text = advice_mod.advice()
    assert text.startswith("Thank you for reporting this") and "GPS coordinates" in text
    cleaned, removed = advice_mod.filter_handling_advice(text)
    assert not removed and cleaned == text


@pytest.mark.parametrize("text, removed", [
    ("Do not move it or touch it.", 0),
    ("The EOD team will move it.", 0),
    ("Put it in a bucket of water.", 1),
    ("They can carry the item to the road.", 1),
    ("Mark the place and take GPS coordinates.", 0),
])
def test_handling_filter(text, removed):
    assert len(advice_mod.filter_handling_advice(text)[1]) == removed


def test_questions_and_instructions_found_only_where_written(bench):
    asks = [r for r, report in bench.reports.items() if advice_mod.asks_how_to_handle(report["description"])]
    notes = [r for r, report in bench.reports.items() if advice_mod.scan_for_instructions(report["description"])]
    assert asks == ["R07", "R34"] and notes == ["R33"]


def test_every_municipality_is_in_the_census(bench):
    assert len(bench.classes) == 36


def test_facts_never_lower_the_floor(bench):
    # Any logged facts, alone or in pairs, keep the floor's urgency at least as high and never clear its flag.
    for report_id, report in bench.reports.items():
        dense = bench.classes[report_id][0]
        base = floor_mod.floor(report, bench.verdicts[report_id], (), dense)
        for size in (1, 2):
            for facts in combinations(floor_mod.FACTS, size):
                result = floor_mod.floor(report, bench.verdicts[report_id], facts, dense)
                assert floor_mod.RANK[result["urgency"]] >= floor_mod.RANK[base["urgency"]], (report_id, facts)
                assert result["flag"] or not base["flag"], (report_id, facts)


def test_check_vetoes_below_the_floor():
    result = {"urgency": "same day", "flag": True,
              "hits": [{"rule": "Place", "urgency": "same day", "flag": False, "why": ""},
                       {"rule": "R6", "urgency": None, "flag": True, "why": ""}]}
    assert floor_mod.check("planned", True, result)["result"] == "veto"
    assert floor_mod.check("same day", False, result)["result"] == "veto"
    assert floor_mod.check("immediate", True, result)["result"] == "pass"
