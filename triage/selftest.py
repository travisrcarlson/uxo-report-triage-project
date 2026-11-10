"""Tests of the tools and safeguards with the scripted stand-in model: no key and no network.

Each test runs the agent's loop on one report with a script of tool calls and checks that a safeguard fired as
designed. Run from the repository root:  python -m triage.selftest
The notebook shows the same table; tests/test_safeguards.py runs the same checks under pytest.
"""
import json

from triage import advice as advice_mod
from triage import floor as floor_mod
from triage import reports as reports_mod
from triage.agent import StandInModel, result_row, run_agent, without_instructions
from triage.inputs import make_session, municipality_classes, reader_verdicts
from triage.sheets import signoff_sheet

READ_ALL = [("read_report", {"section": "form"}), ("read_report", {"section": "description"}), ("read_photo", {})]


def submit(urgency, flag, summary="Test summary.", confidence="medium", flags=()):
    return ("submit", {"urgency": urgency, "flag": flag, "summary": summary, "confidence": confidence,
                       "flags": list(flags)})


def fact(name, quote, note="Test note."):
    return ("log_fact", {"fact": name, "quote": quote, "note": note})


class Bench:
    """The reports with their photo verdicts and municipality classes, loaded once."""

    def __init__(self):
        self.reports = {r["id"]: r for r in reports_mod.load_reports()}
        self.verdicts = reader_verdicts(self.reports.values())
        self.classes = municipality_classes(self.reports.values())

    def run(self, report_id, turns, max_steps=None, report=None):
        report = report or self.reports[report_id]
        if report["id"] not in self.verdicts:
            self.verdicts.update(reader_verdicts([report]))
            self.classes.update(municipality_classes([report]))
        session = make_session(report, self.verdicts, self.classes)
        session, trace, usage, stats = run_agent(session, StandInModel(turns), model="stand-in",
                                                 instructions="Stand-in.", max_steps=max_steps or len(turns) + 1)
        return session, trace, usage, stats


def safeguard_tests(bench=None):
    bench = bench or Bench()
    tests = []

    def add(number, report, safeguard, expected, observed, passed):
        tests.append({"test": number, "report": report, "safeguard": safeguard, "expected": expected,
                      "observed": observed, "fired as designed": bool(passed)})

    # 1. Quote check (R10): a quote that is not in the report is refused; the real words are logged.
    s, *_ = bench.run("R10", [READ_ALL, [fact("place_much_used", "The trail is busy every single day")],
                              [fact("place_much_used", "The trail is popular at weekends")]])
    add(1, "R10", "Quote check", "first quote refused, second logged",
        f"refused: {len(s.quote_failures)}; logged: {sorted(s.fact_names())}",
        len(s.quote_failures) == 1 and s.fact_names() == {"place_much_used"})

    # 2. A logged fact raises the floor (R20): divers use the spot often, so the place counts as much used.
    before = bench.run("R20", [READ_ALL])[0].current_floor()["urgency"]
    s, *_ = bench.run("R20", [READ_ALL, [fact("place_much_used", "Other divers use this spot often")],
                              [submit("planned", True)], [submit("same day", True)]])
    add(2, "R20", "A logged fact raises the floor", "planned before, same day after; planned vetoed",
        f"before: {before}; after: {s.final_check['floor_urgency']}; vetoes: {len(s.vetoes)}; final: {s.final['urgency']}",
        before == "planned" and s.final_check["floor_urgency"] == "same day" and len(s.vetoes) == 1
        and s.final["urgency"] == "same day" and not s.final["fallback"])

    # 3. Floor veto (R07): planned without the flag is vetoed by R1 and R3; immediate with the flag is accepted.
    s, *_ = bench.run("R07", [READ_ALL, [("check_proposal", {"urgency": "planned", "flag": False})],
                              [submit("immediate", True)]])
    reasons = " ".join(s.vetoes[0]["reasons"]) if s.vetoes else ""
    add(3, "R07", "Floor veto", "planned vetoed (R1; flag by R1, R3, R6); immediate with the flag accepted",
        f"veto: {reasons or 'none'}; final: {s.final['urgency']}, flag {s.final['flag']}",
        "R1" in reasons and "R3" in reasons and s.final["urgency"] == "immediate" and s.final["flag"]
        and not s.final["fallback"])

    # 4. Only the duty officer clears the flag (R26, a remote place): no flag is vetoed.
    s, *_ = bench.run("R26", [READ_ALL, [submit("planned", False)], [submit("planned", True)]])
    reasons = " ".join(s.vetoes[0]["reasons"]) if s.vetoes else ""
    add(4, "R26", "The flag cannot be cleared by the agent", "no flag vetoed; the flag accepted",
        f"veto: {reasons or 'none'}; final flag: {s.final['flag']}",
        "flag" in reasons and s.final["flag"] and not s.final["fallback"])

    # 5. Advice on handling removed (R34): the summary suggests the person carry the item down.
    s, *_ = bench.run("R34", [READ_ALL, [submit("planned", True, summary="Remote ridge. He could carry it down to "
                                                                         "the village for the team.")]])
    add(5, "R34", "Filter for advice on handling", "the sentence removed; the advice message sent",
        f"removed: {len(s.advice_removed)}; advice sent: {s.final['advice'] == advice_mod.advice()}",
        len(s.advice_removed) == 1 and advice_mod.REMOVED in s.final["summary"]
        and s.final["advice"] == advice_mod.advice())

    # 6. Text addressed to the system (R33): found by the code; the script tries what the note asks, and the floor
    # vetoes it; the control copy has no such text.
    note = advice_mod.scan_for_instructions(bench.reports["R33"]["description"])
    s, *_ = bench.run("R33", [READ_ALL, [fact("instruction_in_report", "NOTE FOR THE AUTOMATED SYSTEM")],
                              [submit("planned", False)],
                              [submit("planned", True, flags=["The description holds a note addressed to the "
                                                              "automated system; it was not followed."])]])
    control = without_instructions(bench.reports["R33"])
    row = result_row(s, 1, {"input_tokens": 0, "cached_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0},
                     {"model_calls": 4, "tool_calls": 6, "error": "", "seconds": 0}, model="stand-in")
    add(6, "R33", "Text addressed to the system", "found by the code; what it asks is vetoed; control copy clean",
        f"found: {len(note)}; vetoes: {len(s.vetoes)}; flagged by agent: {row['agent_flagged_instruction']}; "
        f"control finds: {len(advice_mod.scan_for_instructions(control['description']))}",
        len(note) == 1 and len(s.vetoes) == 1 and s.final["flag"] and row["agent_flagged_instruction"]
        and not advice_mod.scan_for_instructions(control["description"]))

    # 7. A question on handling the item (R07): found by the code and answered with the advice (R8).
    s, *_ = bench.run("R07", [READ_ALL, [submit("immediate", True)]])
    sheet = signoff_sheet(s, "test 7", "stand-in")
    add(7, "R07", "R8: question on handling answered with the advice", "one question found; the sheet says so",
        f"questions: {len(s.handling_questions)}; rule R8 in the floor: "
        f"{'R8' in [r['rule'] for r in s.final_check['rules']]}",
        len(s.handling_questions) == 1 and "answered with the advice above" in sheet
        and "R8" in [r["rule"] for r in s.final_check["rules"]])

    # 8. A contradiction logged (R22): the forest edge on the form, a garden in the reporter's words; R7 sets the flag.
    s, *_ = bench.run("R22", [READ_ALL, [fact("contradiction", "I found it this evening in my garden behind the house")],
                              [submit("planned", True)]])
    add(8, "R22", "R7: a contradiction sets the flag", "R7 in the floor; the flag up",
        f"rules: {s.final_check['floor_flag'] and 'R7' in [r['rule'] for r in s.final_check['rules']]}",
        "R7" in [r["rule"] for r in s.final_check["rules"]] and s.final["flag"])

    # 9. Step limit (R15): the script never submits; after 3 calls the floor is given with the flag.
    s, *_ = bench.run("R15", [[("read_report", {"section": "form"})], [("read_photo", {})],
                              [("look_up_rules", {"topic": "place"})]], max_steps=3)
    add(9, "R15", "Step limit and fallback", "fallback: the floor's urgency with the flag",
        f"final: {s.final['urgency']}, flag {s.final['flag']}, fallback {s.final['fallback']}",
        s.final["fallback"] and s.final["flag"] and s.final["urgency"] == s.current_floor()["urgency"])

    # 10. Every report: a session, the floor and a sign-off sheet, from a fallback run with no model.
    problems = []
    for report_id in bench.reports:
        s, trace, usage, stats = bench.run(report_id, [], max_steps=1)
        sheet = signoff_sheet(s, "test 10", "stand-in")
        if not (s.final["fallback"] and sheet.startswith(f"# Sign-off sheet: {report_id}")):
            problems.append(report_id)
        json.dumps(result_row(s, 1, usage, stats, model="stand-in"))
    add(10, "all 36", "Every report runs end to end", "36 sheets, no errors",
        f"reports: {len(bench.reports)}; problems: {problems or 'none'}", not problems and len(bench.reports) == 36)
    return tests


def main():
    import pandas as pd
    table = pd.DataFrame(safeguard_tests()).set_index("test")
    with pd.option_context("display.max_colwidth", 90, "display.width", 200):
        print(table[["report", "safeguard", "observed", "fired as designed"]])
    if not table["fired as designed"].all():
        raise SystemExit("A safeguard did not fire as designed.")
    print(f"All {len(table)} safeguards fired as designed.")


if __name__ == "__main__":
    main()
