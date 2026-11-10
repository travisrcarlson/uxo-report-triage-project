# Triaging UXO Reports with an AI Agent

A system that helps the duty officer of a call centre triage reports of unexploded ordnance (UXO) found by members of the public. For each report, made of a photo, a place and a short description, it proposes an urgency level (immediate, same day or planned) and a flag when an explosive ordnance disposal (EOD) specialist must see the photo before anyone goes. The duty officer makes every decision.

It is the Industry-Integrated AI Systems Synthesis project (Project 7) of the AI Mastery Capstone, part of the Master of Science in Artificial Intelligence of the Udacity Institute of AI & Technology.

> **Status, 10 November 2026:** the photo reader, the generated images, the call-out rules, the reports, the reference answers, the agent and the notebook are in place. The runs with the model and the evaluation come next; this README is completed at the end.

## The setting
The call centre is modelled on Switzerland's national reporting centre for UXO, which the Swiss Army's KAMIR command runs ([Swiss Armed Forces](https://www.vtg.admin.ch/de/kampfmittelbeseitiger-schweizer-armee-kamir)). The public sent in 855 reports of munitions finds in 2025 ([blue News, 17 June 2026](https://www.bluewin.ch/en/news/army-cleared-227-unexploded-ordnances-last-year-3284723.html)). The public rule is never to touch a find, to mark the place and to report it: by phone on 117, with the Army's Blindgänger app or with its online form ([Swiss Armed Forces](https://www.vtg.admin.ch/de/blindgaenger)).

This is a student project. It is not affiliated with the Swiss Armed Forces, and the reports in it are invented.

## How it will work
1. **Photo reader.** The convolutional network from the author's earlier project on photos of unexploded ordnance gives the item one of five categories with a confidence, or "unknown".
2. **Unfamiliar items.** Images the reader never trained on, among them images made by the author's earlier generative adversarial network and labelled as generated, should come back "unknown".
3. **Agent.** An agent built like the author's earlier land release agent reads each report through tools and proposes the urgency and the flag.
4. **Rules floor.** Coded rules set the lowest urgency allowed and the flag from the report's facts; the agent can raise the urgency but never go below the floor.
5. **Advice.** The only advice given to the person who reported is the official public message; any advice on handling an item is blocked.
6. **Sign-off sheet.** One page per report for the duty officer, who decides.

## How to run
Needs Python 3.13 and Git. `requirements.txt` was generated on Python 3.13 with the CPU build of PyTorch, which comes from PyTorch's own package index; the install line below adds that index. In Windows PowerShell:

```powershell
git clone https://github.com/travisrcarlson/uxo-report-triage-project.git
cd uxo-report-triage-project
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
jupyter notebook uxo_report_triage.ipynb
```

In Jupyter, choose **Kernel > Restart Kernel and Run All Cells**. To run the agent, set the environment variable `OPENAI_API_KEY` to an OpenAI key in the same PowerShell window before starting Jupyter; the key is never written to the repository. Without a key, the notebook runs everything except the agent's model calls and reads the runs saved in `runs/`.

If PowerShell blocks the activation script, run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once. On macOS or Linux, activate with `source .venv/bin/activate`; on macOS, also change `torch==2.14.1+cpu` in `requirements.txt` to `torch==2.14.1` before installing.

The tests of the floor and the agent's safeguards need no key: `python -m pytest tests`, or `python -m triage.selftest`.

## Repository
| Path | What it holds |
|---|---|
| `uxo_report_triage.ipynb` | The notebook: data checks, the photo reader's results, the reports, the floor, the agent's safeguard tests, the runs and the evaluation |
| `triage/` | The code: photo reader (`photo_reader.py`), generated images (`generated_images.py`), census table (`municipalities.py`), reports (`reports.py`), floor (`floor.py`), advice (`advice.py`), agent (`agent.py`), sign-off sheet (`sheets.py`), runs (`runner.py`) and evaluation (`evaluation.py`) |
| `rules/callout_rules.md` | The call-out rules, the floor and the advice message |
| `prompts/system_prompt.md` | The agent's instructions |
| `reports/` | The 36 invented reports (`reports.json`, one Markdown file each), their test photos and where each photo came from (`photos.csv`), and the reference answers (`reference.csv`) |
| `data/` | The crops, the generated images and the census table, with their sources (`data/README.md`) |
| `models/` | The trained photo reader and generator |
| `tests/` | Offline tests of the floor, the advice checks and the safeguards |

## Data and licences
- CTX-UXO (Craioveanu and Stamatescu, National University of Science and Technology Politehnica Bucharest), [Zenodo record 17052675](https://zenodo.org/records/17052675), CC BY 4.0.
- SULAND (Vivoli et al., 2024, University of Florence) with the SULAND_v2 labels (Lekhak et al., Rochester Institute of Technology), CC BY 4.0, used through the earlier project's generated images.

Files derived from these datasets keep the CC BY 4.0 licence and the attribution above.

## Safety
Everything stays at a general level: item categories and counts, with no identification detail, no technical data on munitions and no advice on handling items. The system never says that an item is safe, and the lowest urgency it proposes is "planned".
