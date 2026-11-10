"""Running the agent on the reports, saving every run, and resuming runs already saved.

Each run is saved as three files in the runs folder: the trace (every model call and tool call), the sign-off sheet
and the result row; `results.csv` and `run_info.json` sum them up. A run saved earlier is kept when its model and its
input files are unchanged and it ended without an error, so an interrupted run can go on where it stopped.
"""
import hashlib
import json
import platform
import sys
from datetime import datetime, timezone
from pathlib import Path

import openai
import pandas as pd
import torch

from triage import floor as floor_mod
from triage.agent import StandInModel, inputs_sha, result_row, rule_topics, run_agent, save_run
from triage.inputs import make_session
from triage.selftest import READ_ALL, submit
from triage.sheets import signoff_sheet

FATAL_ERRORS = ("AuthenticationError", "PermissionDeniedError", "NotFoundError", "BadRequestError")


def input_files():
    """The files a run depends on: the reports and photos, the rules, the prompt, the photo reader, the census table
    and the code. The reference answers are not among them: no run reads them."""
    files = [Path("reports") / "reports.json", *sorted((Path("reports") / "photos").glob("*.png")),
             Path("rules") / "callout_rules.md", Path("prompts") / "system_prompt.md",
             Path("models") / "photo_reader.json", Path("models") / "photo_reader.pt",
             Path("data") / "ch_municipalities_degurba.csv", *sorted(Path("triage").glob("*.py"))]
    missing = [str(p) for p in files if not p.exists()]
    if missing:
        raise FileNotFoundError(f"missing input files: {missing}")
    return files


def load_saved_row(out_dir, report_id, run, model, sha):
    path = Path(out_dir) / f"{report_id}_run{run}_result.json"
    if not path.exists():
        return None
    row = json.loads(path.read_text(encoding="utf-8"))
    if row.get("error") or row.get("model") != model or row.get("inputs_sha") != sha:
        return None
    return row


def scripted_client(session):
    """Claude's workspace only: a stand-in that reads the report and submits the floor's answer, so the evaluation
    code can be run end to end without a key. Its runs go to runs_dev/, never to runs/."""
    result = session.current_floor()
    return StandInModel([READ_ALL, [submit(result["urgency"], result["flag"],
                                           summary="Scripted stand-in: the floor's answer, without the model.",
                                           confidence="low")]])


def run_reports(reports, verdicts, classes, client_for, model, runs_per_report, out_dir, price=None,
                reasoning_effort=None, max_steps=None, instructions=None, resume=True, log=print):
    """Run the agent on each report `runs_per_report` times; return the results table.

    client_for(session) gives the client for one run: the OpenAI client, or a stand-in.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    files = input_files()
    sha = inputs_sha(files)
    topics = rule_topics()
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows, stopped = [], ""
    for report in reports:
        for run in range(1, runs_per_report + 1):
            saved = load_saved_row(out_dir, report["id"], run, model, sha) if resume else None
            if saved is not None:
                rows.append(saved)
                continue
            session = make_session(report, verdicts, classes, topics)
            kwargs = {"max_steps": max_steps} if max_steps else {}
            session, trace, usage, stats = run_agent(session, client_for(session), model, instructions,
                                                     reasoning_effort, **kwargs)
            row = result_row(session, run, usage, stats, model, sha, price)
            save_run(out_dir, session, trace, row, signoff_sheet(session, f"run {run}", model))
            rows.append(row)
            log(f"{report['id']} run {run}: {row['urgency']}, flag {'yes' if row['flag'] else 'no'}"
                f"{' (fallback)' if row['fallback'] else ''}; {row['model_calls']} model calls"
                + (f"; error: {row['error']}" if row["error"] else ""))
            if row["error"].startswith(FATAL_ERRORS):
                stopped = row["error"]
                break
        if stopped:
            log(f"Stopped: the API refused the call ({stopped}). Fix the cause and run the cell again; saved runs "
                "are kept.")
            break
    table = pd.DataFrame(rows)
    table.to_csv(out_dir / "results.csv", index=False, lineterminator="\n")
    info = {"model": model, "reasoning_effort": reasoning_effort, "runs_per_report": runs_per_report,
            "reports": [r["id"] for r in reports], "inputs_sha": sha, "started": started,
            "finished": datetime.now(timezone.utc).isoformat(timespec="seconds"), "stopped_on_error": stopped,
            "python": platform.python_version(), "platform": platform.platform(), "openai": openai.__version__,
            "torch": torch.__version__, "pandas": pd.__version__, "urgency_levels": floor_mod.URGENCIES,
            "files": {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (out_dir / "run_info.json").write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8", newline="\n")
    return table


def read_results(out_dir):
    table = pd.read_csv(Path(out_dir) / "results.csv", keep_default_na=False,
                        dtype={"error": str, "facts_logged": str, "sections_unread": str, "rules_read": str})
    for column in ("flag", "floor_flag", "above_floor", "fallback", "photo_read", "agent_flagged_instruction"):
        table[column] = table[column].astype(str).str.lower().eq("true")
    table["cost_usd"] = pd.to_numeric(table["cost_usd"], errors="coerce")
    return table


if __name__ == "__main__":
    sys.exit("Run the agent from the notebook, section 9.")
