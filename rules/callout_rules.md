# Call-out rules

The rules the agent looks up and the coded floor applies to every report. They are this project's own rules,
written for a call centre modelled on the Swiss Armed Forces' national reporting centre for unexploded ordnance (UXO);
they are not the procedure of any real service. The public guidance quoted comes from the Swiss Army's own pages.

> **Status:** drafted by Claude from the public guidance, then set by the project's EOD specialist, who answered each
> rule, Claude's readings of his answers and the choice of census data on 8 November 2026. The advice and the
> sign-off sheet were updated on 10 November 2026 from his notes on his reference answers, with his agreement. Two
> readings of the report form's types of place are Claude's and await his confirmation (marked below).

## The public guidance
- "Blindgänger nie berühren" (never touch unexploded ordnance), then mark the place and report the find: by phone on
  117, with the Army's Blindgänger app, or with the online form; keeping a find as a souvenir is forbidden
  ([Swiss Armed Forces, Blindgänger](https://www.vtg.admin.ch/de/blindgaenger)).
- "Nicht berühren oder bewegen" (do not touch or move it) ([Swiss Armed Forces, 17 June 2026](https://www.vtg.admin.ch/de/newnsb/E0oKISSoFiFMOKGC_rvXx)).
- Marking means placing a clearly visible marker, such as tape or a cloth wedged between stones, or a bottle on a stick
  ([Merkblatt "Wie markiere ich Blindgänger richtig?"](https://www.vtg.admin.ch/dam/de/sd-web/x3fPBnbTqKV9/Merkblatt_Blg_markieren.pdf)).

## Urgency levels
| Level | Meaning |
|---|---|
| Immediate | A team goes now. |
| Same day | A team goes today. |
| Planned | A team goes on a planned date. |

There is no level below planned: every report of a possible explosive item gets a response, and the system never
says that an item is safe.

## Specialist flag
The flag means that a person, an EOD specialist or the duty officer, confirms the report before anyone goes. The
floor below sets it; the agent may also set it, and only the duty officer may clear it.

## The place
Where the item is and who can reach it decide how many people could come across it, so the place sets the urgency
when no other rule does (the EOD specialist, 8 November 2026: "Population-dense areas, because they'll have a higher
probability of encounter, will get higher priority").

| Place | Examples | Lowest urgency |
|---|---|---|
| Much used | A village or town, a busy path or road, a public park, a building site, a station | Same day |
| Little used | Farmland, forest with paths, a quiet hillside | Planned |
| Remote | High mountains away from paths, a closed military training area | Planned, and the flag, so a person confirms |

The population of the municipality is a second factor, from census data (the EOD specialist, 8 November 2026: "we
could likely pull census data as well to determine population density in the area"). He chose the official
urban/rural class: a find in a municipality that Eurostat's degree of urbanisation classes as a city (densely
populated) counts as much used, whatever the report says about the spot. The class comes from Eurostat's table of
local administrative units, which classes 135 of Switzerland's 2,131 municipalities as cities (`data/README.md`).

The report form records the type of place; the floor reads it as follows. The agent may raise a place to much used
when it logs a fact, with a quote from the report, showing that people use it; it can never lower one.

| Type of place on the form | Place |
|---|---|
| Settlement, building, building site, path or park, road or railway, school or playground | Much used |
| Farmland, forest | Little used |
| Water | Little used (to be confirmed) |
| Mountain, training area | Remote |
| Not stated | Not known: planned, and the flag, so a person confirms (to be confirmed) |

> **To be confirmed by the EOD specialist:** the table above does not name water, and the form can leave the place
> out. Claude reads water as little used unless the report shows people there, and a place not stated like a remote
> one, planned with the flag. Both readings were made after his reference answers were recorded.

## The floor
Coded rules set the lowest urgency allowed, and the flag, from the report's facts: the fields of the report form, the
photo reader's verdict, and the facts the agent logged with a quote that appears in the report. The agent may raise
the urgency but never go below the floor; a proposal below it is vetoed. When several rules apply, the highest
urgency and any flag stand.

| Rule | When | Lowest urgency | Flag |
|---|---|---|---|
| R1 | Children are with or near the item, or have handled it, or the place is close to a school or another place where children are, such as a playground or a kindergarten | Immediate | Yes |
| R2 | People are close to the item and cannot easily be kept away: a path in use, a road, a building site, a garden | Immediate | — |
| R3 | The item was moved, picked up, or taken indoors or home | Same day | Yes |
| R4a | The item is in or by a building, a road or a railway, the area cannot be evacuated and cordoned off (or the report does not say), and the place is much used or densely populated | Immediate | — |
| R4b | The item is in or by a building, a road or a railway, in any other case | Same day | — |
| R5 | The item looks damaged, or is giving off smoke, a smell or a liquid | Immediate | Yes |
| R6 | The photo reader says "unknown", or there is no usable photo | Set by the place (above) | Yes |
| R7 | The report contradicts itself or its photo, or two reports describe different items at one place | — | Yes: the duty officer decides |
| R8 | The person asks how to move, open or make the item safe | — | — (the advice below answers, every time) |
| — | None of the above | Set by the place (above) | — |

## Advice to the person who reported
Every report gets this message as the call centre's first answer (the EOD specialist, 8 November 2026: "the marking
and evacuation protocols should be in place for all occurrences"). It is the only advice the system gives: anything
else, and above all any advice on handling the item, is blocked and replaced with it. When a person asks how to move,
open or make the item safe (R8), the answer is this message again. The thanks and the request for the location and
photos of the surroundings come from his notes on his reference answers (agreed on 10 November 2026: "totally agree").

> Thank you for reporting this; it was the right thing to do. Do not do anything to the item: do not touch it, move it
> or open it. Move away from it, do not go back, and keep other people away. If you can do it without going closer,
> mark the place where you are with something clearly visible, such as tape, a cloth or a bottle on a stick. If you
> can, send us your location from your phone (its GPS coordinates) and photos of the surroundings taken from where you
> are, so the team can find the place. Stay where you can be reached on the number you gave, and follow what the call
> centre tells you about clearing the area and where to meet the team.

## Marking and evacuation on the sign-off sheet
For every report the sheet states what the report says about marking, and whether the area can be evacuated and
cordoned off; the duty officer decides whether to clear the area. The sheet also reminds the duty officer to ask the
police to help clear and cordon off the area where that is needed (from the EOD specialist's notes on his reference
answers, agreed on 10 November 2026).
