"""The sign-off sheet: one page per report and run for the duty officer, who decides.

It is laid out so that the duty officer checks the photo and the facts before reading the proposal: the photo comes
first, each fact shows where it came from, the floor shows which rules set it, and what the agent did not use is
listed.
"""
from triage import floor as floor_mod

FORM_FACTS = [("people_close", "People close to the item"), ("children", "Children"), ("moved", "Item moved"),
              ("condition", "Condition of the item"), ("place_type", "Type of place")]


def yes_no(value):
    return "yes" if value else "no"


def cell(text):
    return str(text).replace("|", "/").replace("\n", " ")


def signoff_sheet(session, label, model, generated_photo=False):
    """The sheet as Markdown. generated_photo marks a test photo made by P5's GAN, so it is labelled as generated."""
    report, final, check = session.report, session.final, session.final_check
    verdict = session.verdict
    if verdict is None:
        photo = "no photo"
    elif verdict["category"] == "unknown":
        photo = f"unknown (confidence {verdict['confidence']:.2f}, below the reader's cut-off)"
    else:
        photo = f"{verdict['category']} (confidence {verdict['confidence']:.2f})"
    degurba = f"; Eurostat: {session.degurba_class}" if session.degurba_class else ""
    source = "fallback to the floor, with the flag" if final["fallback"] else "agent's proposal, within the floor"
    photo_line = "- Photo: none"
    if verdict is not None:
        photo_line = (f"- Photo: attached, taken from where the reporter stood "
                      f"(`reports/photos/{report.get('control_of', report['id'])}.png`)")
        if generated_photo:
            photo_line += ". GENERATED: in this test the photo is an image made by P5's GAN, not a real photo"
    lines = [f"# Sign-off sheet: {report['id']}, {label}", "",
             f"Received: {report['received']} ({report['channel']}), from a {report['reporter']}  ",
             f"Municipality: {report['municipality']}{degurba}  ",
             f"Place: {report['place']}  ",
             f"Model: {model}", "",
             "## Check 1: look at the photo yourself",
             photo_line,
             f"- The photo reader says: {photo}. The reader names one of five categories or says unknown; it never "
             "says that an item is safe.", "",
             "## Check 2: the facts and where they come from",
             "| Fact | From | Words |", "|---|---|---|"]
    for key, name in FORM_FACTS:
        lines.append(f"| {name} | form | {cell(report[key])} |")
    for fact in session.facts:
        lines.append(f"| {fact.fact} | agent, step {fact.step} | \"{cell(fact.quote)}\" (found in the report) |")
    for failure in session.quote_failures:
        lines.append(f"| {failure['fact']} | agent, step {failure['step']} | \"{cell(failure['quote'])}\" "
                     "(refused: not in the report) |")
    lines += ["", "Reporter's words:", "", "> " + cell(report["description"]), "",
              "## Check 3: the floor",
              "| Rule | Lowest urgency | Flag | Why |", "|---|---|---|---|"]
    for rule in check["rules"]:
        lines.append(f"| {rule['rule']} | {rule['urgency'] or '-'} | {yes_no(rule['flag'])} | {cell(rule['why'])} |")
    lines += ["", "## Check 4: marking, evacuation and the police",
              f"- Marked: {report['marked']}",
              f"- Area can be evacuated and cordoned off: {report['controllable']}",
              "- Ask the police to help clear and cordon off the area where that is needed.", "",
              "## Proposal",
              f"- Urgency: **{final['urgency']}** (floor: {check['floor_urgency']})",
              f"- Specialist flag: **{yes_no(final['flag'])}** (floor: {yes_no(check['floor_flag'])})",
              f"- Source: {source}",
              f"- Agent's confidence: {final['confidence']}", "",
              "Agent's summary:", "", "> " + cell(final["summary"]), "",
              "## Advice sent to the person who reported", "", "> " + final["advice"], "",
              "- The person asked how to handle the item (R8): "
              + ("; ".join(f"\"{q}\"" for q in session.handling_questions) + "; answered with the advice above"
                 if session.handling_questions else "no"),
              f"- Advice on handling removed from the agent's text: {'; '.join(session.advice_removed) or 'none'}",
              "- Claims that the item is safe removed from the agent's text: "
              + ("; ".join(session.claims_removed) or "none"), "",
              "## Flags",
              "- Text in the report addressed to the system, found by the code: "
              + ("; ".join(f"\"{t}\"" for t in session.instructions) or "none"),
              "- Flags reported by the agent:" + ("".join(f"\n  - {cell(f)}" for f in final["flags"]) or " none"),
              "- Vetoes during the run: " + ("; ".join(f"{v['urgency']} with flag {yes_no(v['flag'])} at step "
                                                       f"{v['step']}: {'; '.join(v['reasons'])}"
                                                       for v in session.vetoes) or "none"),
              f"- Quote check failures: {len(session.quote_failures)}; tool errors: {len(session.tool_errors)}", "",
              "## What the agent did not use",
              "- Report sections not read: "
              + (", ".join(s for s in ("form", "description") if s not in session.sections_read) or "none"),
              f"- Photo verdict read: {yes_no(session.photo_read)}",
              f"- Rule topics looked up: {', '.join(dict.fromkeys(session.rules_read)) or 'none'}", "",
              "## Sign-off", "",
              "Duty officer: ______________________  ",
              f"Decision: agree / change the urgency to ____________ / {'clear' if final['flag'] else 'set'} the flag  ",
              "Date and time: ______________", "",
              "*This proposal comes from an AI agent working inside coded rules. It is not final until the duty "
              "officer signs it.*"]
    assert final["urgency"] in floor_mod.URGENCIES
    return "\n".join(lines) + "\n"
