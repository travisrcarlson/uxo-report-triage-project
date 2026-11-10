"""The advice block, and the code checks on the words of a report and of the agent.

- `advice()` is the one message every person who reports gets, read from `rules/callout_rules.md` so that the code
  and the rules cannot drift apart. It is the only advice the system gives.
- `filter_handling_advice` removes sentences that advise handling an item from text the agent writes, as in P6.
- `asks_how_to_handle` finds a person asking how to move, open or make the item safe (rule R8).
- `scan_for_instructions` finds sentences in a report that address the system and tell it what to decide.
"""
import re
from functools import lru_cache
from pathlib import Path

RULES_FILE = Path("rules") / "callout_rules.md"
ADVICE_HEADING = "## Advice to the person who reported"
REMOVED = "[Removed: advice on handling the item is not given; only the EOD team deals with the item.]"


@lru_cache(maxsize=None)
def advice(rules_file=RULES_FILE):
    """The advice message: the quoted lines of the rules' advice section, joined."""
    text = Path(rules_file).read_text(encoding="utf-8")
    if ADVICE_HEADING not in text:
        raise ValueError(f"{rules_file} has no section {ADVICE_HEADING!r}")
    section = text.split(ADVICE_HEADING, 1)[1].split("\n## ", 1)[0]
    quoted = [line[1:].strip() for line in section.splitlines() if line.startswith(">")]
    if not quoted:
        raise ValueError(f"{rules_file}: the advice section quotes no message")
    return " ".join(quoted)


HANDLING_VERBS = (r"pick(?:ing)?(?:\s+up)?|lift(?:ing)?|carry(?:ing)?|mov(?:e|ing)|remov(?:e|ing)|throw(?:ing)?|"
                  r"bury(?:ing)?|burn(?:ing)?|dig(?:ging)?(?:\s+(?:up|out))?|pull(?:ing)?|cut(?:ting)?|"
                  r"unscrew(?:ing)?|detonat(?:e|ing)|blow(?:ing)?(?:\s+up)?|destroy(?:ing)?|take|taking|"
                  r"collect(?:ing)?|handl(?:e|ing)|touch(?:ing)?|put(?:ting)?|plac(?:e|ing)|open(?:ing)?|"
                  r"bring(?:ing)?|drop(?:ping)?|kick(?:ing)?|shak(?:e|ing)|turn(?:ing)?|hold(?:ing)?|"
                  r"cover(?:ing)?|wash(?:ing)?|clean(?:ing)?|submerg(?:e|ing)|soak(?:ing)?|hit(?:ting)?")
HANDLING_OBJECTS = (r"(?:it|them|those|these|"
                    r"(?:the|any|an|a|each|every|such|this|that)\s+(?:items?|objects?|shells?|bombs?|grenades?|"
                    r"ordnance|munitions?|explosives?|devices?|finds?|things?|box|cartridges?))")
HANDLING = [re.compile(rf"\b(?:{HANDLING_VERBS})\s+(?:\w+\s+)?{HANDLING_OBJECTS}\b", re.I),
            re.compile(r"\b(?:defus\w*|disarm\w*|neutrali[sz]\w*|render(?:ing)?\s+\w+\s+safe|make\s+\w+\s+safe)\b",
                       re.I)]
NEGATION = re.compile(r"\b(?:not|never|no one|nobody|don't|do not|should not|must not|cannot|can't|avoid|without|"
                      r"nor)\b", re.I)
EXPERTS = re.compile(r"\b(?:EOD|explosive ordnance disposal|the team|our team|teams?|specialists?|technicians?|"
                     r"experts?|qualified|operators?)\b", re.I)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n", text or "") if s.strip()]


def filter_handling_advice(text):
    """Remove sentences that advise handling an item. Returns the cleaned text and the sentences removed."""
    kept, removed = [], []
    for sentence in sentences(text):
        plain = sentence.replace("’", "'")
        advice_found = False
        for pattern in HANDLING:
            for match in pattern.finditer(plain):
                before = plain[max(0, match.start() - 45):match.start()]
                if not (NEGATION.search(before) or EXPERTS.search(before)):
                    advice_found = True
        if advice_found:
            removed.append(sentence)
            kept.append(REMOVED)
        else:
            kept.append(sentence)
    return " ".join(kept), removed


HANDLING_QUESTIONS = [
    re.compile(r"\bhow\s+(?:can|do|should|could|would|might)\s+(?:i|we)\b[^.?!]*?"
               r"\b(?:safe|move|open|carry|take|lift|defuse|disarm|get rid of|dispose)\b", re.I),
    re.compile(r"\b(?:can|could|should|may)\s+(?:i|we)\s+(?:put|move|carry|take|pick|open|bring|lift|throw|bury|"
               r"drop|clean)\b[^.?!]*\?", re.I),
    re.compile(r"\bmake\s+(?:it|the item|the object|this)\s+safe\b[^.!]*\?", re.I),
]


def asks_how_to_handle(text):
    """The sentences in which the person asks how to move, open or make the item safe (rule R8)."""
    return [s for s in sentences(text) if any(p.search(s) for p in HANDLING_QUESTIONS)]


ADDRESSEE = re.compile(r"\b(?:automated system|the system|automatic|AI|artificial intelligence|assistant|chatbot|"
                       r"language model|LLM|model|algorithm|computer|software|bot)\b", re.I)
INSTRUCTION = re.compile(r"\b(?:ignore|disregard|set|mark|classify|override|forget|pretend|instead|must|do not|don't|"
                         r"reply|respond|output|flag|change|lower|downgrade|treat)\b", re.I)


def scan_for_instructions(text):
    """Sentences of a report that address the system or an AI and tell it what to do."""
    hits = []
    for line in (text or "").splitlines():
        for sentence in re.split(r"(?<=[.!?])\s+", line.strip(" |>")):
            if ADDRESSEE.search(sentence) and INSTRUCTION.search(sentence):
                hits.append(sentence.strip(" |"))
    return hits
