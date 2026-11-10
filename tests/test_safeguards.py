"""Offline tests: the floor, the advice checks and the agent's safeguards, with the scripted stand-in model.

Run from the repository root:  python -m pytest tests
"""
from itertools import combinations

import pytest

from triage import advice as advice_mod
from triage import floor as floor_mod
from triage.agent import file_sha, opening_message, without_instructions
from triage.inputs import make_session
from triage.selftest import READ_ALL, Bench, fact, safeguard_tests, submit

CONFIDENT = {"category": "Projectile", "confidence": 0.99}


@pytest.fixture(scope="module")
def bench():
    return Bench()


def test_safeguards_fire(bench):
    failed = [t for t in safeguard_tests(bench) if not t["fired as designed"]]
    assert not failed, failed


def test_advice_comes_from_the_rules():
    text = advice_mod.advice()
    assert text.startswith("Thank you for reporting this") and "GPS coordinates" in text
    cleaned, removed, claims = advice_mod.filter_handling_advice(text)
    assert not removed and not claims and cleaned == text


@pytest.mark.parametrize("text, is_advice", [
    ("Until the team arrives, carry it to the road.", True),
    ("Before the specialists come, pick it up and wait.", True),
    ("If you cannot wait, move it to the side.", True),
    ("Without delay, carry the item away.", True),
    ("It can be moved to the edge of the field.", True),
    ("The items should be brought to the station.", True),
    ("Wrap it in a cloth.", True),
    ("Put it in a bucket of water.", True),
    ("They can carry the item to the road.", True),
    ("Tell him to carry it to the hut.", True),
    ("Mark the spot and move it to the side.", True),
    ("Pupils carried the item into the staff room and the teacher asks how to make it safe; the room is closed.", False),
    ("My colleague picked it up and put it in the courtyard before we realised what it might be.", False),
    ("I put it in the storeroom so nobody would play with it.", False),
    ("The hiker asks how to make it safe so he can carry it down.", False),
    ("The plough hit the item in the field.", False),
    ("Do not move it or touch it.", False),
    ("The EOD team will move it.", False),
    ("Mark the place and take GPS coordinates.", False),
    ("They put it in a bucket of water.", False),
    ("It should not be moved.", False),
])
def test_handling_filter(text, is_advice):
    assert advice_mod.handling_advice_in(text) == is_advice


@pytest.mark.parametrize("text, is_claim", [
    ("This is only scrap metal and is harmless.", True),
    ("It is probably inert.", True),
    ("The note says it is scrap metal; it was not followed.", False),
    ("It may not be harmless.", False),
    ("The item looks intact.", False),
])
def test_safety_claims(text, is_claim):
    assert advice_mod.safety_claim_in(text) == is_claim


def test_questions_and_instructions_found_only_where_written(bench):
    asks = [r for r, report in bench.reports.items() if advice_mod.asks_how_to_handle(report["description"])]
    notes = [r for r, report in bench.reports.items() if advice_mod.scan_for_instructions(report["description"])]
    assert asks == ["R07", "R34"] and notes == ["R33"]


def test_every_municipality_is_in_the_census(bench):
    assert len(bench.classes) == 36


def test_facts_never_lower_the_floor(bench):
    # Any logged facts, alone or in pairs, keep the floor's urgency at least as high and never clear its flag, with
    # the reader's real verdict and with a confident one (so R6 does not hide a lost flag).
    for report_id, report in bench.reports.items():
        dense = bench.classes[report_id][0]
        for verdict in (bench.verdicts[report_id], CONFIDENT):
            base = floor_mod.floor(report, verdict, (), dense)
            for size in (1, 2):
                for facts in combinations(floor_mod.FACTS, size):
                    result = floor_mod.floor(report, verdict, facts, dense)
                    assert floor_mod.RANK[result["urgency"]] >= floor_mod.RANK[base["urgency"]], (report_id, facts)
                    assert result["flag"] or not base["flag"], (report_id, facts)


def test_a_busy_or_dense_place_keeps_the_flag_of_a_remote_one(bench):
    remote = dict(bench.reports["R26"])
    for dense, facts in ((False, ("place_much_used",)), (True, ())):
        result = floor_mod.floor(remote, CONFIDENT, facts, dense)
        assert result["urgency"] == "same day" and result["flag"], (dense, facts)


def test_check_vetoes_below_the_floor():
    result = {"urgency": "same day", "flag": True,
              "hits": [{"rule": "Place", "urgency": "same day", "flag": False, "why": ""},
                       {"rule": "R6", "urgency": None, "flag": True, "why": ""}]}
    assert floor_mod.check("planned", True, result)["result"] == "veto"
    assert floor_mod.check("same day", False, result)["result"] == "veto"
    assert floor_mod.check("immediate", True, result)["result"] == "pass"


def test_quote_check_refuses_form_labels(bench):
    session, *_ = bench.run("R26", [READ_ALL, [fact("people_close", "People close to the item")]])
    assert len(session.quote_failures) == 1 and not session.facts


def test_control_copy_is_shown_as_the_report(bench):
    control = without_instructions(bench.reports["R33"])
    session = make_session(control, {**bench.verdicts, **{control["id"]: bench.verdicts["R33"]}},
                           {**bench.classes, **{control["id"]: bench.classes["R33"]}})
    assert "control" not in opening_message(control)
    assert session.read_report("form")["report"] == "R33"


def test_first_proposal_recorded(bench):
    session, *_ = bench.run("R26", [READ_ALL, [submit("planned", False)], [submit("planned", True)]])
    assert [(p["urgency"], p["flag"], p["result"]) for p in session.proposals] == [
        ("planned", False, "veto"), ("planned", True, "pass")]


def test_input_hash_ignores_line_endings(tmp_path):
    lf, crlf = tmp_path / "a" / "x.md", tmp_path / "b" / "x.md"
    lf.parent.mkdir()
    crlf.parent.mkdir()
    lf.write_bytes(b"one\ntwo\n")
    crlf.write_bytes(b"one\r\ntwo\r\n")
    assert file_sha(lf) == file_sha(crlf)
