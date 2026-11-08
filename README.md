# Triaging UXO Reports with an AI Agent

A system that helps the duty officer of a call centre triage reports of unexploded ordnance (UXO) found by members of the public. For each report, made of a photo, a place and a short description, it proposes an urgency level (immediate, same day or planned) and a flag when an explosive ordnance disposal (EOD) specialist must see the photo before anyone goes. The duty officer makes every decision.

It is the Industry-Integrated AI Systems Synthesis project (Project 7) of the AI Mastery Capstone, part of the Master of Science in Artificial Intelligence of the Udacity Institute of AI & Technology.

> **Status, 8 November 2026:** the repository has just been started. The notebook, the data and the results are added step by step; this README is completed at the end.

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

## Data and licences
- CTX-UXO (Craioveanu and Stamatescu, National University of Science and Technology Politehnica Bucharest), [Zenodo record 17052675](https://zenodo.org/records/17052675), CC BY 4.0.
- SULAND (Vivoli et al., 2024, University of Florence) with the SULAND_v2 labels (Lekhak et al., Rochester Institute of Technology), CC BY 4.0, used through the earlier project's generated images.

Files derived from these datasets keep the CC BY 4.0 licence and the attribution above.

## Safety
Everything stays at a general level: item categories and counts, with no identification detail, no technical data on munitions and no advice on handling items. The system never says that an item is safe, and the lowest urgency it proposes is "planned".
