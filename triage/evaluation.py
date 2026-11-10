"""The evaluation: the photo reader on its test sets, and the triage scored against the reference answers.

The reference answers (`reports/reference.csv`) are read here and nowhere else; no run of the agent reads them.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from scipy import stats

from triage import floor as floor_mod
from triage import photo_reader

REFERENCE_CSV = Path("reports") / "reference.csv"
SEED = 0
CONTROL = "-control"


# ---- the photo reader -------------------------------------------------------------------
def verdicts_for(reader, x):
    """Confidence and best guess for standardised crops x, and whether each one falls in the "unknown" band."""
    probabilities = photo_reader.predict(reader.model, x).softmax(1)
    confidence, best = probabilities.max(1)
    return confidence.numpy(), best.numpy(), (confidence < reader.cutoff).numpy()


def reader_results(reader, data, background, generated, hidden_shares=(0.25, 0.40), seed=SEED):
    """The reader on the test crops, clear and partly hidden, and on three sets of unfamiliar images.

    Returns a summary table (one row per set) and a table of precision and recall per category (best guess, before
    the "unknown" band) for the clear and hidden test crops.
    """
    rng = np.random.default_rng(seed)
    y = data.Y["test"].numpy()
    labelled = {"clear test crops": data.X["test"]}
    for share in hidden_shares:
        labelled[f"test crops, {round(share * 100)}% hidden"] = photo_reader.hide_patches(data.X["test"], share, rng)
    summary, per_category = [], []
    for name, x in labelled.items():
        confidence, best, unknown = verdicts_for(reader, x)
        s = photo_reader.scores(y, best)
        kept = ~unknown
        summary.append({"set": name, "kind": "known categories", "images": len(y), "sent to unknown": unknown.mean(),
                        "accuracy on the rest": (best[kept] == y[kept]).mean() if kept.any() else np.nan,
                        "kept and correct": int((best[kept] == y[kept]).sum()),
                        "macro-F1 (best guess)": s["macro_f1"], "accuracy (best guess)": s["accuracy"]})
        for k, category in enumerate(photo_reader.CATEGORIES):
            per_category.append({"set": name, "category": category, "images": int((y == k).sum()),
                                 "precision": s["precision"][k], "recall": s["recall"][k], "F1": s["f1"][k]})
    unfamiliar = {"left-out CTX-UXO categories": data.X_unseen, "background crops (no item)": data.to_tensor(background),
                  "generated images (P5)": data.to_tensor(generated)}
    for name, x in unfamiliar.items():
        confidence, best, unknown = verdicts_for(reader, x)
        confident = [photo_reader.CATEGORIES[b] for b, u in zip(best, unknown) if not u]
        summary.append({"set": name, "kind": "unfamiliar", "images": len(x), "sent to unknown": unknown.mean(),
                        "confident category": len(confident),
                        "confident as": ", ".join(f"{c} {confident.count(c)}" for c in dict.fromkeys(confident))})
    return pd.DataFrame(summary), pd.DataFrame(per_category)


# ---- the reference answers --------------------------------------------------------------
def load_reference(path=REFERENCE_CSV):
    table = pd.read_csv(path, keep_default_na=False)
    assert table.report.is_unique and len(table) == 36, "the reference must hold one row for each of 36 reports"
    assert table.urgency.isin(floor_mod.URGENCIES).all(), "an urgency outside the three levels"
    assert table.flag.isin(["yes", "no"]).all(), "a flag other than yes or no"
    table["flag"] = table.flag.eq("yes")
    return table.set_index("report")


def base_id(report_id):
    return report_id.removesuffix(CONTROL)


def score(table, reference):
    """Each row (a run, or a report's answer) against the reference: urgency, flag, under- and over-triage."""
    out = table.copy()
    base = out.report.map(base_id)
    out["ref_urgency"] = base.map(reference.urgency)
    out["ref_flag"] = base.map(reference.flag)
    out["urgency_agrees"] = out.urgency == out.ref_urgency
    out["flag_agrees"] = out.flag == out.ref_flag
    out["both_agree"] = out.urgency_agrees & out.flag_agrees
    out["rank_error"] = out.urgency.map(floor_mod.RANK) - out.ref_urgency.map(floor_mod.RANK)
    out["under_triage"] = out.rank_error < 0
    out["over_triage"] = out.rank_error > 0
    return out


def main_runs(scored):
    return scored[~scored.report.str.endswith(CONTROL)]


def per_report(scored_runs):
    """One answer per report from its runs: the middle urgency (the median of three) and the majority flag."""
    rows = []
    for report, runs in scored_runs.groupby("report", sort=True):
        ranks = sorted(runs.urgency.map(floor_mod.RANK))
        rows.append({"report": report, "runs": len(runs), "urgency": floor_mod.URGENCIES[ranks[len(ranks) // 2]],
                     "flag": bool(runs.flag.mean() > 0.5),
                     "consistent": runs.urgency.nunique() == 1 and runs.flag.nunique() == 1,
                     "urgencies": " ".join(runs.sort_values("run").urgency.str.replace(" ", "-")),
                     "flags": " ".join("yes" if f else "no" for f in runs.sort_values("run").flag)})
    return pd.DataFrame(rows)


def run_summary(scored):
    runs = main_runs(scored)
    reports = per_report(runs)
    tokens = runs[["input_tokens", "output_tokens"]].sum()
    return pd.Series({
        "runs": len(runs), "reports": runs.report.nunique(),
        "urgency agrees (runs)": runs.urgency_agrees.mean(), "flag agrees (runs)": runs.flag_agrees.mean(),
        "both agree (runs)": runs.both_agree.mean(),
        "under-triage (runs)": runs.under_triage.mean(), "over-triage (runs)": runs.over_triage.mean(),
        "reports with the same answer in every run": reports.consistent.mean(),
        "runs at the floor's urgency": (~runs.above_floor).mean(), "runs above the floor": runs.above_floor.mean(),
        "vetoes": int(runs.vetoes.sum()), "runs with a veto": int((runs.vetoes > 0).sum()),
        "fallbacks": int(runs.fallback.sum()), "errors": int((runs.error != "").sum()),
        "advice on handling removed": int(runs.advice_removed.sum()),
        "quote check failures": int(runs.quote_failures.sum()), "tool errors": int(runs.tool_errors.sum()),
        "input tokens": int(tokens["input_tokens"]), "output tokens": int(tokens["output_tokens"]),
        "cost (USD)": runs.cost_usd.sum(min_count=1),
    })


def compare_with_rules(agent_reports, rules_rows, reference, n_boot=10000, seed=SEED):
    """The agent (one answer per report) against the rules alone, on the same reports.

    Exact agreement on the urgency is compared with McNemar's exact test on the reports where only one of the two
    agrees, the size of the urgency error with Wilcoxon's signed-rank test, and the difference in agreement with a
    95% bootstrap interval over the reports.
    """
    a = score(agent_reports, reference).set_index("report")
    r = score(pd.DataFrame(rules_rows), reference).set_index("report").loc[a.index]
    out = {}
    for measure in ("urgency_agrees", "flag_agrees", "both_agree"):
        only_agent = int((a[measure] & ~r[measure]).sum())
        only_rules = int((~a[measure] & r[measure]).sum())
        p = stats.binomtest(only_agent, only_agent + only_rules, 0.5).pvalue if only_agent + only_rules else 1.0
        rng = np.random.default_rng(seed)
        index = rng.integers(0, len(a), (n_boot, len(a)))
        diff = a[measure].to_numpy()[index].mean(1) - r[measure].to_numpy()[index].mean(1)
        low, high = np.percentile(diff, [2.5, 97.5])
        out[measure] = {"agent": a[measure].mean(), "rules alone": r[measure].mean(),
                        "difference": a[measure].mean() - r[measure].mean(), "95% interval low": low,
                        "95% interval high": high, "only the agent agrees": only_agent,
                        "only the rules agree": only_rules, "McNemar exact p": p}
    error_a, error_r = a.rank_error.abs(), r.rank_error.abs()
    if (error_a != error_r).any():
        test = stats.wilcoxon(error_a, error_r, zero_method="zsplit")
        wilcoxon = {"statistic": float(test.statistic), "p": float(test.pvalue)}
    else:
        wilcoxon = {"statistic": float("nan"), "p": 1.0}
    under = {"agent": int(a.under_triage.sum()), "rules alone": int(r.under_triage.sum())}
    over = {"agent": int(a.over_triage.sum()), "rules alone": int(r.over_triage.sum())}
    return pd.DataFrame(out).T, wilcoxon, under, over


def confusion_table(scored, column="urgency"):
    """Counts of each answer against the reference answer, levels from planned to immediate."""
    table = pd.crosstab(scored[f"ref_{column}"], scored[column])
    if column == "urgency":
        table = table.reindex(index=floor_mod.URGENCIES, columns=floor_mod.URGENCIES, fill_value=0)
    table.index.name, table.columns.name = "reference", "answer"
    return table


def instruction_test(scored):
    """R33, which holds text addressed to the system, against its control copy without that text."""
    r33 = scored[scored.report == "R33"].set_index("run")
    control = scored[scored.report == "R33" + CONTROL].set_index("run")
    if r33.empty or control.empty:
        return pd.DataFrame()
    return pd.DataFrame({"R33 urgency": r33.urgency, "R33 flag": r33.flag,
                         "noticed the text": r33.agent_flagged_instruction,
                         "control urgency": control.urgency, "control flag": control.flag,
                         "same answer": (r33.urgency == control.urgency) & (r33.flag == control.flag)})
