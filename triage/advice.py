"""The advice block, and the code checks on the words of a report and of the agent.

- `advice()` is the one message every person who reports gets, read from `rules/callout_rules.md` so that the code
  and the rules cannot drift apart. It is the only advice the system gives.
- `filter_handling_advice` removes, from text the agent writes, sentences that advise handling an item (as in
  P6) and sentences that say an item is safe.
- `asks_how_to_handle` finds a person asking how to move, open or make the item safe (rule R8).
- `scan_for_instructions` finds sentences in a report that address the system and tell it what to decide.
"""
import re
from functools import lru_cache
from pathlib import Path

RULES_FILE = Path("rules") / "callout_rules.md"
ADVICE_HEADING = "## Advice to the person who reported"
REMOVED = "[Removed: advice on handling the item is not given; only the EOD team deals with the item.]"
REMOVED_CLAIM = "[Removed: the system never says that an item is safe.]"


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
                  r"cover(?:ing)?|wrap(?:ping)?|wash(?:ing)?|clean(?:ing)?|submerg(?:e|ing)|soak(?:ing)?|hit(?:ting)?")
HANDLING_OBJECTS = (r"(?:it|them|those|these|"
                    r"(?:the|any|an|a|each|every|such|this|that)\s+(?:items?|objects?|shells?|bombs?|grenades?|"
                    r"ordnance|munitions?|explosives?|devices?|finds?|things?|box|cartridges?))")
VERB_OBJECT = re.compile(rf"\b(?:{HANDLING_VERBS})\s+(?:\w+\s+)?{HANDLING_OBJECTS}\b", re.I)
MAKE_SAFE = re.compile(r"\b(?:defus\w*|disarm\w*|neutrali[sz]\w*|render(?:ing)?\s+\w+\s+safe|make\s+\w+\s+safe)\b", re.I)
PASSIVE = re.compile(r"\b(?:it|they|them|the\s+(?:items?|objects?|finds?|box))\s+(?:can|could|should|may|must|might|"
                     r"will|is to|are to|needs? to)\s+(?:\w+\s+)?be\s+(?:moved|carried|picked up|lifted|taken|brought|"
                     r"put|placed|removed|thrown|buried|collected|opened|cleaned|washed|submerged|soaked|covered|"
                     r"wrapped|handled|touched|kicked|dropped|shaken|turned)\b", re.I)
# What the words just before a handling verb say about it.
REPORTED = re.compile(r"\b(?:asks|asked|asking|wants to know|wanted to know|wonders|wondered|wondering|how to|"
                      r"how (?:can|could|do|should) (?:i|we|he|she|they)|whether)\b", re.I)
NEGATED = re.compile(r"(?:\bnot|\bnever|\bcannot|n't|\bno one|\bnobody|\bnor)\s+(?:\w+\s+)?$", re.I)
NEGATED_LIST = re.compile(r"^\s*(?:please\s+)?(?:do not|don't|never|you must not|you should not|nobody should|"
                          r"no one should)\b", re.I)
EXPERT_SUBJECT = re.compile(r"\b(?:eod|team|teams|specialists?|technicians?|experts?|operators?|police)\s+(?:will|would|"
                            r"can|could|should|must|may|might|is going to|are going to|to)?\s*(?:\w+\s+)?$", re.I)
MODAL_SUBJECT = re.compile(r"\b(?:you|he|she|they|people|someone|anyone|the\s+(?:caller|person|reporter|finder|farmer|"
                           r"teacher|owner|staff|pupils|guests?|residents?|workers?|crew|divers?|hikers?|keeper|"
                           r"foreman|family|neighbours?))\s+(?:can|could|should|may|must|might|need to|needs to|"
                           r"have to|has to|ought to|is to|are to)\s+(?:\w+\s+)?$", re.I)
TELL_TO = re.compile(r"\b(?:tell|ask|advise|instruct|let|have|get|allow)\s+(?:\w+\s+){0,2}(?:to\s+)?$", re.I)
CLAUSE_START = re.compile(r"(?:[,:\-–—]|\b(?:then|please|just|simply|first|now|also|instead))$", re.I)
IMPERATIVE_START = re.compile(r"^\s*(?:please\s+)?(?:mark|keep|stay|move|take|put|place|carry|pick|lift|bring|leave|"
                              r"cover|wrap|throw|bury|open|clean|wash|call|tell|ask|send|check|look|go|get|make|try|"
                              r"let|remove|collect|hold|turn|drop|kick|shake|soak|submerge|touch|handle|hit)\b", re.I)


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=[.!?;])\s+|\n", text or "") if s.strip()]


def advises(prefix, sentence):
    """True when the words before a handling verb make it advice: an imperative, or a modal or 'tell ... to'."""
    tail = prefix.rstrip()
    if not tail or CLAUSE_START.search(tail):
        return True
    if re.search(r"\band$", tail) and IMPERATIVE_START.search(sentence):
        return True
    return bool(MODAL_SUBJECT.search(prefix) or TELL_TO.search(prefix))


def handling_advice_in(sentence):
    """True when the sentence advises handling the item. A negated verb ("do not move it"), the EOD team as the one
    who acts ("the team will move it"), a reported question ("asks how to make it safe") and a past event ("picked it
    up and put it in the courtyard") are not advice."""
    low = sentence.replace("’", "'").lower()
    for match in [*VERB_OBJECT.finditer(low), *MAKE_SAFE.finditer(low)]:
        prefix = low[:match.start()]
        clause = re.split(r":", prefix)[-1]
        if REPORTED.search(prefix) or NEGATED.search(prefix) or NEGATED_LIST.search(clause):
            continue
        if EXPERT_SUBJECT.search(prefix):
            continue
        if advises(prefix, low):
            return True
    for match in PASSIVE.finditer(low):
        if not re.search(r"\b(?:not|never)\b|n't", match.group(0)) and not REPORTED.search(low[:match.start()]):
            return True
    return False


SAFE_CLAIM = re.compile(r"\b(?:harmless|is safe|are safe|safe to (?:touch|handle|move|carry|keep|leave|approach)|"
                        r"not dangerous|no danger|no risk|little risk|low risk|inert|scrap(?: metal)?|a dud|"
                        r"is empty|are empty|not explosive|not live|deactivated|defused|nothing to worry)\b", re.I)
SAFE_NEGATED = re.compile(r"\b(?:not|never|no|cannot|can't|unlikely to be|may not be|might not be)\s+(?:\w+\s+){0,2}$",
                          re.I)
SAFE_REPORTED = re.compile(r"\b(?:says|said|claims|claimed|states|stated|calls it|according to|the note|the text|"
                           r"note in|asks|asked|believes|believed|thinks|thought)\b", re.I)


def safety_claim_in(sentence):
    """True when the sentence says, in its own voice, that the item is safe, harmless, empty or scrap."""
    low = sentence.lower()
    for match in SAFE_CLAIM.finditer(low):
        prefix = low[:match.start()]
        if not (SAFE_NEGATED.search(prefix) or SAFE_REPORTED.search(prefix)):
            return True
    return False


QUOTED = re.compile(r"\u201c[^\u201d]*\u201d|\"[^\"]*\"|\u2018[^\u2019]*\u2019")


def filter_handling_advice(text):
    """Remove the sentences that advise handling an item, and those that say an item is safe.

    Words in quotation marks are the report's or the person's, quoted by the agent, so they are not checked. Returns
    the cleaned text, the advice removed and the claims removed. The agent writes only for the duty officer, so a
    removal is shown on the sign-off sheet; the person who reported only ever gets the fixed advice."""
    quotes = []

    def protect(match):
        quotes.append(match.group(0))
        return f"QUOTED{len(quotes) - 1}X"

    def restore(sentence):
        return re.sub(r"QUOTED(\d+)X", lambda m: quotes[int(m.group(1))], sentence)

    kept, removed_advice, removed_claims = [], [], []
    for sentence in sentences(QUOTED.sub(protect, text or "")):
        if handling_advice_in(sentence):
            removed_advice.append(restore(sentence))
            kept.append(REMOVED)
        elif safety_claim_in(sentence):
            removed_claims.append(restore(sentence))
            kept.append(REMOVED_CLAIM)
        else:
            kept.append(restore(sentence))
    return " ".join(kept), removed_advice, removed_claims


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
