"""What a run needs for each report: the photo reader's verdict and the municipality's degree of urbanisation.

Both are computed by code before the agent starts, so every run, and the rules-only comparison, sees the same ones.
"""
from triage import municipalities, photo_reader, reports as reports_mod
from triage.agent import ReportSession, rule_topics


def reader_verdicts(reports, reader=None):
    """{report id: the photo reader's verdict, or None when the report has no photo}."""
    reader = reader or photo_reader.PhotoReader.load()
    verdicts = {}
    for report in reports:
        image = reports_mod.load_photo(report.get("control_of", report["id"]))
        verdicts[report["id"]] = None if image is None else reader.read(image[None])[0]
    return verdicts


def municipality_classes(reports, table=None):
    """{report id: (densely populated, the class's name)} from Eurostat's degree of urbanisation."""
    table = municipalities.load_municipalities() if table is None else table
    out = {}
    for report in reports:
        dense = municipalities.densely_populated(table, report["municipality"])
        name = table.loc[table.municipality == report["municipality"], "degurba_class"].iloc[0]
        out[report["id"]] = (dense, name)
    return out


def make_session(report, verdicts, classes, topics=None):
    dense, name = classes[report["id"]]
    return ReportSession(report, verdicts[report["id"]], dense, name, topics if topics is not None else rule_topics())
