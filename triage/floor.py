"""The rules floor: the lowest urgency allowed for a report, and the specialist flag, from its facts.

The rules are the EOD specialist's, as set out in `rules/callout_rules.md`. The facts come from three places: the
fields of the report form, the photo reader's verdict, and the facts the agent logged with a quote from the report.
A logged fact can only add to what the form says, so the agent can raise the floor but never lower it. When several
rules apply, the highest urgency and any flag stand.

`rules_only` is the comparison the agent is measured against: the same floor from the form and the photo verdict
alone, with no logged facts.
"""
from dataclasses import dataclass

URGENCIES = ["planned", "same day", "immediate"]          # from lowest to highest
RANK = {urgency: n for n, urgency in enumerate(URGENCIES)}

# How the floor reads the form's types of place (the table in the rules, "The place").
PLACE_OF_TYPE = {
    "settlement": "much used", "building": "much used", "building site": "much used", "path or park": "much used",
    "road or railway": "much used", "school or playground": "much used",
    "farmland": "little used", "forest": "little used", "water": "little used",
    "mountain": "remote", "training area": "remote",
    "not stated": "not known",
}
# The lowest urgency each place sets, and whether it sets the flag.
PLACE_URGENCY = {"much used": ("same day", False), "little used": ("planned", False),
                 "remote": ("planned", True), "not known": ("planned", True)}

# The facts the agent can log, each with a quote from the report. Each one adds to the form, never takes away.
FACTS = {
    "children": "Children are with or near the item, or have handled it, or the place is close to a school or "
                "another place where children are (R1).",
    "people_close": "People are close to the item and cannot easily be kept away (R2).",
    "moved": "The item was moved, picked up, or taken indoors or home (R3).",
    "building_road_railway": "The item is in or by a building, a road or a railway (R4).",
    "cannot_control": "The area cannot be evacuated and cordoned off (R4).",
    "damaged": "The item looks damaged, or is giving off smoke, a smell or a liquid (R5).",
    "contradiction": "The report contradicts itself or its photo, or describes a different item from another report "
                     "at the same place (R7).",
    "asks_handling": "The person asks how to move, open or make the item safe (R8).",
    "place_much_used": "People use the place often: it counts as much used (the place).",
    "instruction_in_report": "The report contains text addressed to the system, telling it what to decide.",
}

CHILDREN_ON_FORM = {"near the item", "handled it", "school or playground nearby"}
MOVED_ON_FORM = {"moved", "taken indoors or home"}
INFRASTRUCTURE = {"building", "road or railway"}


@dataclass
class Hit:
    rule: str
    urgency: str | None       # the lowest urgency the rule sets, or None when it sets none
    flag: bool
    why: str

    def as_dict(self):
        return {"rule": self.rule, "urgency": self.urgency, "flag": self.flag, "why": self.why}


def controllable(report):
    """True only when the form says the area can be evacuated and cordoned off."""
    return str(report["controllable"]).lower().startswith("yes")


def place_of(report, dense, facts=()):
    """The place (much used, little used, remote or not known) and why."""
    base = PLACE_OF_TYPE[report["place_type"]]
    if dense:
        return "much used", "the municipality is a city (densely populated) in Eurostat's degree of urbanisation"
    if "place_much_used" in facts and base != "much used":
        return "much used", "the agent logged, with a quote, that people use the place often"
    if base == "not known":
        return base, "the report does not say where the item is"
    return base, f"the form gives the type of place as {report['place_type']}"


def floor(report, verdict, facts=(), dense=False, asks_handling=False):
    """The floor for one report.

    report: the report's form fields (a dict from reports/reports.json).
    verdict: the photo reader's verdict ({"category": ..., "confidence": ...}), or None when there is no photo.
    facts: the names of the facts the agent logged (each checked against the report by its quote).
    dense: True when the municipality is a city in Eurostat's degree of urbanisation.
    asks_handling: True when the code found the person asking how to handle the item.
    Returns {"urgency", "flag", "place", "place_why", "hits"}.
    """
    facts = set(facts)
    hits = []
    place, place_why = place_of(report, dense, facts)
    urgency, flag = PLACE_URGENCY[place]
    hits.append(Hit("Place", urgency, flag, f"{place}: {place_why}"))

    children = report["children"] in CHILDREN_ON_FORM or report["place_type"] == "school or playground"
    if children or "children" in facts:
        why = (f"children on the form: {report['children']}" if report["children"] in CHILDREN_ON_FORM
               else "the place is a school or playground" if report["place_type"] == "school or playground"
               else "logged by the agent")
        hits.append(Hit("R1", "immediate", True, why))

    if (report["people_close"] == "yes" and not controllable(report)) or "people_close" in facts:
        why = ("people close on the form, and the form does not say the area can be evacuated and cordoned off"
               if report["people_close"] == "yes" and not controllable(report) else "logged by the agent")
        hits.append(Hit("R2", "immediate", False, why))

    if report["moved"] in MOVED_ON_FORM or "moved" in facts:
        why = f"item moved on the form: {report['moved']}" if report["moved"] in MOVED_ON_FORM else "logged by the agent"
        hits.append(Hit("R3", "same day", True, why))

    if report["place_type"] in INFRASTRUCTURE or "building_road_railway" in facts:
        uncontrolled = not controllable(report) or "cannot_control" in facts
        busy = place == "much used" or dense
        if uncontrolled and busy:
            hits.append(Hit("R4a", "immediate", False,
                            "by a building, road or railway; the area cannot be evacuated and cordoned off, or the "
                            "report does not say; the place is much used or densely populated"))
        else:
            hits.append(Hit("R4b", "same day", False, "by a building, road or railway"))

    if report["condition"] == "smoke, smell or liquid" or "damaged" in facts:
        why = ("condition on the form: smoke, smell or liquid" if report["condition"] == "smoke, smell or liquid"
               else "logged by the agent")
        hits.append(Hit("R5", "immediate", True, why))

    if verdict is None or verdict.get("category") == "unknown":
        why = "no photo" if verdict is None else f"the photo reader says unknown (confidence {verdict['confidence']:.2f})"
        hits.append(Hit("R6", None, True, why + "; the urgency is set by the place"))

    if "contradiction" in facts:
        hits.append(Hit("R7", None, True, "logged by the agent; the duty officer decides"))

    if asks_handling or "asks_handling" in facts:
        hits.append(Hit("R8", None, False, "the person asked how to handle the item; the advice answers"))

    lowest = max((h.urgency for h in hits if h.urgency), key=RANK.__getitem__)
    return {"urgency": lowest, "flag": any(h.flag for h in hits), "place": place, "place_why": place_why,
            "hits": [h.as_dict() for h in hits]}


def rule_names(rules):
    """'R1', 'R1 and R3', 'the place, R1 and R6': the rules as the subject of a sentence, and its verb."""
    names = ["the place" if rule == "Place" else rule for rule in rules]
    text = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return text[0].upper() + text[1:], "sets" if len(names) == 1 else "set"


def check(urgency, flag, result):
    """A proposal against the floor: a pass, or a veto with the reasons."""
    reasons = []
    if urgency not in RANK:
        reasons.append(f"The urgency must be one of {', '.join(URGENCIES)}")
    elif RANK[urgency] < RANK[result["urgency"]]:
        subject, verb = rule_names([h["rule"] for h in result["hits"] if h["urgency"] == result["urgency"]])
        reasons.append(f"{subject} {verb} the urgency at {result['urgency']} or higher")
    if result["flag"] and not flag:
        subject, verb = rule_names([h["rule"] for h in result["hits"] if h["flag"]])
        reasons.append(f"{subject} {verb} the specialist flag, and only the duty officer may clear it")
    return {"result": "veto" if reasons else "pass", "reasons": reasons, "floor_urgency": result["urgency"],
            "floor_flag": result["flag"], "rules": result["hits"]}


def rules_only(report, verdict, dense=False, asks_handling=False):
    """The answer of the rules alone: the floor from the form and the photo verdict, with no logged facts."""
    result = floor(report, verdict, facts=(), dense=dense, asks_handling=asks_handling)
    return {"urgency": result["urgency"], "flag": result["flag"], "rules": [h["rule"] for h in result["hits"]]}
