"""The rules-only comparison: what the floor alone gives each report, from the form and the photo verdict.

The agent is measured against it on the same reports: the agent can only add facts from the reporter's words, and
raise the urgency, so any difference between the two comes from what the agent read.
"""
from triage import advice as advice_mod
from triage import floor as floor_mod


def rules_only_rows(reports, verdicts, classes):
    rows = []
    for report in reports:
        dense, name = classes[report["id"]]
        verdict = verdicts[report["id"]]
        answer = floor_mod.rules_only(report, verdict, dense,
                                      asks_handling=bool(advice_mod.asks_how_to_handle(report["description"])))
        rows.append({"report": report["id"], "urgency": answer["urgency"], "flag": answer["flag"],
                     "rules": " ".join(answer["rules"]), "place_type": report["place_type"], "degurba": name,
                     "photo_verdict": "none" if verdict is None else verdict["category"],
                     "photo_confidence": None if verdict is None else verdict["confidence"]})
    return rows
