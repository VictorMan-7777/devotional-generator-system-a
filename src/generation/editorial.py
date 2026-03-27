from __future__ import annotations

from dataclasses import dataclass, replace
import re

from src.generation.outliner_resources import resolve_passage_cue
from src.models.pipeline import (
    EditorialBuildArtifact,
    EditorialDayBriefRecord,
    EditorialDayPlanRow,
    EditorialWeekPlan,
    PassageResourceBundle,
    PassageResourceRecord,
)


_CLAUSE_SPLIT_RE = re.compile(r"[.;:?!]|\s+-\s+|,\s+")
_LEADING_FILLER = {"and", "but", "for", "now", "then", "so", "therefore", "yet"}
_LOW_SIGNAL_MARKERS = {
    "land of cush",
    "gold of that land",
    "bdellium",
    "onyx stone",
    "the name of the second river is gihon",
    "it flows around",
    "there was no shrub",
    "had not caused it to rain",
}
_HIGH_SIGNAL_MARKERS = {
    "give light on the earth",
    "for signs and for seasons",
    "to govern the day",
    "to govern the night",
    "great sea monsters",
    "living creature that moves",
    "be fruitful and multiply",
    "subdue it",
    "rule over",
    "completed his work",
    "rested on the seventh day",
    "blessed the seventh day",
    "formed man of dust",
    "breathed into his nostrils",
    "became a living being",
    "planted a garden",
    "then the lord god took the man and put him",
    "took the man and put him",
    "to cultivate it and keep it",
    "the lord god commanded the man",
    "commanded the man",
    "you may surely eat",
    "you shall not eat",
    "formed every beast",
    "brought them to the man",
    "called a living creature",
}
_ACTION_WORDS = {
    "came", "said", "poured", "betrayed", "prayed", "denied", "watched",
    "wept", "kissed", "crucified", "rose", "buried", "remembered", "worshiped",
    "feared", "followed", "sought", "mocked", "anointed", "separated",
    "placed", "blessed", "rested", "formed", "planted", "took", "put",
    "commanded", "brought", "called", "named", "created",
}
_STOPWORDS = {
    "the", "and", "that", "with", "from", "into", "this", "were", "was", "have",
    "has", "had", "their", "they", "them", "there", "about", "your", "what",
    "you",
    "when", "while", "would", "could", "should", "among", "during", "after",
    "before", "because", "through", "those", "these", "very",
}


@dataclass(frozen=True)
class EditorialDayBrief:
    day_number: int
    week_number: int
    scripture_reference: str
    study_window_reference: str
    key_verse_reference: str
    day_title: str
    focus_clause: str
    pastoral_burden: str
    genre: str
    scene_summary: str
    theological_lane: str
    application_lane: str
    forbidden_drifts: tuple[str, ...]
    key_terms: tuple[str, ...]
    library_resources: tuple[PassageResourceRecord, ...] = ()


def editorial_week_number(day_number: int) -> int:
    return ((day_number - 1) // 7) + 1


def brief_to_record(brief: EditorialDayBrief) -> EditorialDayBriefRecord:
    return EditorialDayBriefRecord(
        day_number=brief.day_number,
        week_number=brief.week_number,
        scripture_reference=brief.scripture_reference,
        study_window_reference=brief.study_window_reference,
        key_verse_reference=brief.key_verse_reference,
        day_title=brief.day_title,
        focus_clause=brief.focus_clause,
        pastoral_burden=brief.pastoral_burden,
        genre=brief.genre,
        scene_summary=brief.scene_summary,
        theological_lane=brief.theological_lane,
        application_lane=brief.application_lane,
        forbidden_drifts=list(brief.forbidden_drifts),
        key_terms=list(brief.key_terms),
    )


def _focus_emphasis(brief: EditorialDayBrief) -> str:
    tokens = [token for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", brief.focus_clause.lower()) if token not in _STOPWORDS and token not in _LEADING_FILLER]
    if tokens:
        return " ".join(tokens[:5])
    return brief.focus_clause.strip().lower() or brief.scripture_reference.lower()


def _with_emphasis(base: str, emphasis: str, joiner: str) -> str:
    cleaned_base = base.strip()
    cleaned_emphasis = emphasis.strip()
    if not cleaned_base or not cleaned_emphasis:
        return cleaned_base or cleaned_emphasis
    if cleaned_emphasis in cleaned_base.lower():
        return cleaned_base
    return f"{cleaned_base} {joiner} {cleaned_emphasis}"


def differentiate_day_briefs(day_briefs: list[EditorialDayBrief]) -> list[EditorialDayBrief]:
    if not day_briefs:
        return []

    differentiated: list[EditorialDayBrief] = [day_briefs[0]]
    for brief in day_briefs[1:]:
        prev = differentiated[-1]
        updated = brief
        emphasis = _focus_emphasis(brief)
        if prev.pastoral_burden.strip().lower() == brief.pastoral_burden.strip().lower():
            updated = replace(updated, pastoral_burden=_with_emphasis(brief.pastoral_burden, emphasis, "through"))
        if prev.theological_lane.strip().lower() == updated.theological_lane.strip().lower():
            updated = replace(updated, theological_lane=_with_emphasis(updated.theological_lane, emphasis, "centered on"))
        if prev.application_lane.strip().lower() == updated.application_lane.strip().lower():
            updated = replace(updated, application_lane=_with_emphasis(updated.application_lane, emphasis, "expressed in"))
        differentiated.append(updated)
    return differentiated


def _key_terms(focus_clause: str, scripture_text: str) -> tuple[str, ...]:
    combined = f"{focus_clause} {scripture_text}"
    terms: list[str] = []
    for token in re.findall(r"[A-Za-z][A-Za-z'-]{2,}", combined):
        lowered = token.lower()
        if lowered in _STOPWORDS or lowered in _LEADING_FILLER:
            continue
        if lowered not in terms:
            terms.append(lowered)
        if len(terms) >= 6:
            break
    return tuple(terms)


def _passage_genre(reference: str, scripture_text: str) -> str:
    ref = (reference or "").lower()
    lower = (scripture_text or "").lower()
    if ref.startswith("psalm") or ref.startswith("psalms"):
        return "poetry"
    if ref.startswith(("isaiah", "jeremiah", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi")):
        return "prophecy"
    if ref.startswith(("isaiah", "jeremiah", "ezekiel", "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah", "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi")):
        if any(word in lower for word in {"vision", "prophesy", "oracle", "son of man", "word of the lord"}):
            return "prophecy"
    if ref.startswith(("matthew", "mark", "luke", "john", "acts", "genesis", "exodus", "joshua", "judges", "ruth", "samuel", "kings", "chronicles", "ezra", "nehemiah", "esther", "job")):
        return "narrative"
    if ref.startswith(("romans", "corinthians", "galatians", "ephesians", "philippians", "colossians", "thessalonians", "timothy", "titus", "philemon", "hebrews", "james", "peter", "jude", "revelation")):
        return "epistle"
    if ref.startswith(("proverbs", "ecclesiastes", "song of solomon", "song of songs")):
        return "wisdom"
    return "scripture"


def _theological_lane(reference: str, focus_clause: str, scripture_text: str, burden: str) -> str:
    ref = (reference or "").lower()
    lower = f"{focus_clause} {scripture_text} {burden}".lower()
    cue = resolve_passage_cue(reference=reference, focus_clause=focus_clause, scripture_text=scripture_text)
    if cue is not None:
        return cue.theological_lane
    if ref.startswith(("luke 5", "luke 6")):
        if any(
            term in lower
            for term in {
                "worked hard all night and caught nothing",
                "put out into the deep water",
                "let down your nets for a catch",
                "at your word i will let down the nets",
            }
        ):
            return "obedient trust when Christ's word overturns exhausted self-reliance"
        if any(
            term in lower
            for term in {
                "depart from me for i am a sinful man",
                "do not fear, from now on you will be catching men",
                "stretched out his hand and touched him",
                "i am willing; be cleansed",
            }
        ):
            return "holy mercy that draws near to the unworthy and the unclean"
        if any(
            term in lower
            for term in {
                "he himself would often slip away to the wilderness and pray",
                "your sins have been forgiven you",
                "which is easier, to say",
                "get up and walk",
            }
        ):
            return "forgiving authority exercised in prayerful dependence"
        if any(
            term in lower
            for term in {
                "follow me",
                "he left everything behind",
                "i have not come to call the righteous but sinners to repentance",
                "the disciples of john often fast",
                "when the bridegroom is taken away",
                "new wine must be put into fresh wineskins",
            }
        ):
            return "new allegiance demanded by the presence of Christ"
        if any(
            term in lower
            for term in {
                "that they might find reason to accuse him",
                "is it lawful to do good or to do harm on the sabbath",
                "he chose twelve of them",
                "stood on a level place",
            }
        ):
            return "kingdom mercy and authority confronting hardened religion"
        if any(
            term in lower
            for term in {
                "blessed are you who are poor",
                "love your enemies",
                "lend, expecting nothing in return",
                "be merciful, just as your father is merciful",
                "why do you call me, 'lord, lord,' and do not do what i say",
                "dug deep and laid a foundation on the rock",
            }
        ):
            return "kingdom obedience shaped by mercy, reversal, and durable hearing"
    if ref.startswith("habakkuk"):
        if "sober awe before god's saving judgment" in lower:
            return "divine majesty that shakes nations and rescues God's people"
        if "watchful trust while awaiting god's justice" in lower:
            return "watchful faith anchored in promised justice"
        if "reverent protest that still clings to god" in lower:
            return "reverent protest that refuses cynical unbelief"
        if "silent reverence before god's holy rule" in lower:
            return "silent reverence before the enthroned Holy One"
        if "trembling joy that clings to god amid loss" in lower:
            return "trembling joy that clings to God amid loss"
        if any(
            term in lower
            for term in {
                "the law is ignored",
                "justice is never upheld",
                "why do you make me see iniquity",
            }
        ):
            return "faithful lament under delayed justice"
        if any(
            term in lower
            for term in {
                "look among the nations",
                "be astonished",
                "i am raising up the chaldeans",
                "their horses are swifter",
                "they all come for violence",
            }
        ):
            return "divine sovereignty that unsettles human certainty"
        if any(
            term in lower
            for term in {
                "your eyes are too pure to approve evil",
                "why are you silent",
                "will they therefore empty their net",
                "continually slay nations without sparing",
            }
        ):
            return "reverent protest that refuses cynical unbelief"
        if any(
            term in lower
            for term in {
                "i will stand on my guard post",
                "write down the vision",
                "the righteous will live by faith",
                "it hastens toward the goal",
            }
        ):
            return "watchful faith anchored in promised justice"
        if any(
            term in lower
            for term in {
                "woe to him",
                "cutting off many peoples",
                "devised a shameful thing",
                "builds a city with bloodshed",
                "peoples toil for fire",
                "make your neighbors drunk",
                "the cup in the lord",
                "woe to him who says to a piece of wood",
            }
        ):
            return "woes exposing predatory pride and idolatry"
        if any(
            term in lower
            for term in {
                "he stood and surveyed the earth",
                "the mountains were shattered",
                "you marched through the earth in indignation",
                "you went forth for the salvation of your people",
                "you pierced with his own spears",
            }
        ):
            return "divine majesty that shakes nations and rescues God's people"
        if any(
            term in lower
            for term in {
                "the lord is in his holy temple",
                "let all the earth be silent",
            }
        ):
            return "silent reverence before the enthroned Holy One"
        if any(
            term in lower
            for term in {
                "in wrath remember mercy",
                "i heard and my inward parts trembled",
                "though the fig tree should not blossom",
                "yet i will exult in the lord",
            }
        ):
            return "trembling joy that clings to God amid loss"
    if any(term in lower for term in {"on eagles' wings", "brought you to myself", "if you will indeed obey my voice"}):
        return "covenant nearness received before covenant obligation"
    if any(term in lower for term in {"set bounds", "do not go up on the mountain", "break through to the lord"}):
        return "holy boundaries under God's dangerous nearness"
    if any(term in lower for term in {"mount sinai was all in smoke", "the sound of the trumpet grew louder", "god answered him with thunder"}):
        return "holy encounter that humbles the hearer before God's majesty"
    if any(term in lower for term in {"you shall have no other gods", "you shall not make", "remember the sabbath", "honor your father and your mother"}):
        return "covenant life ordered by God's holy authority"
    if any(term in lower for term in {"enticing sinners", "throw in your lot with us", "their feet run to evil"}):
        return "moral refusal of seductive folly"
    if any(term in lower for term in {"if you receive my words", "incline your heart", "seek her as silver", "search for her as for hidden treasures"}):
        return "diligent seeking that receives wisdom as treasure"
    if any(term in lower for term in {"walk in the way of good men", "the upright will live in the land", "discretion will guard you"}):
        return "secure walking under wisdom's protection"
    if any(term in lower for term in {"saul, saul, why are you persecuting me", "i am jesus whom you are persecuting"}):
        return "direct confrontation by the risen Lord"
    if any(term in lower for term in {"get up and enter the city", "he could see nothing", "they led him by the hand"}):
        return "helpless reorientation under divine interruption"
    if any(term in lower for term in {"ananias", "go, for he is a chosen instrument", "brother saul"}):
        return "obedient mediation in service of God's surprising mercy"
    if any(term in lower for term in {"he is the son of god", "all those hearing him continued to be amazed", "baffled the jews"}):
        return "public transformation that cannot stay hidden"
    if any(term in lower for term in {"the church throughout all judea", "enjoying peace", "being built up"}):
        return "strengthening peace under the fear and comfort of God"
    if any(term in lower for term in {"tabitha", "dorcas", "she opened her eyes", "arise", "presented her alive"}):
        return "resurrection mercy that strengthens communal witness"
    if any(term in lower for term in {"stayed many days in joppa", "with a tanner named simon"}):
        return "ordinary faithfulness that remains ready for God's next assignment"
    if any(term in lower for term in {"genealogy of jesus", "was the father of", "by tamar", "by rahab", "by ruth", "by bathsheba"}):
        return "covenant faithfulness remembered through compromised generations"
    if any(term in lower for term in {"immanuel", "she will bear a son", "kept her a virgin", "joseph awoke from his sleep"}):
        return "promised presence welcomed through obedient trust"
    if any(term in lower for term in {"out of you shall come forth a ruler", "in bethlehem of judea", "we saw his star", "king of the jews"}):
        return "promised kingship disclosed through prophetic fulfillment"
    if any(term in lower for term in {"give light on the earth", "for signs and for seasons", "to govern the day", "to govern the night"}):
        return "ordered light that governs time under God's wisdom"
    if any(term in lower for term in {"great sea monsters", "living creature that moves", "be fruitful and multiply and fill the waters"}):
        return "abundant life flourishing under God's blessing"
    if any(term in lower for term in {"subdue it", "rule over", "in our image", "according to our likeness"}):
        return "human vocation under God's delegated rule"
    if any(term in lower for term in {"gog", "magog", "i am against you", "hooks into your jaws"}):
        return "divine warning against hostile pride"
    if any(term in lower for term in {"gather from every side to my sacrifice", "eat flesh and drink blood", "my table with horses and charioteers"}):
        return "divine judgment publicly displayed before the nations"
    if any(term in lower for term in {"i will set my glory among the nations", "the nations will see my judgment", "the house of israel will know"}):
        return "divine holiness publicly vindicated before the nations"
    if any(term in lower for term in {"the lord gave and the lord has taken away", "did not sin", "retains his integrity"}):
        return "reverent endurance under unexplained suffering"
    if any(term in lower for term in {"a messenger came", "great wind came", "fire of god fell"}):
        return "steadfast reverence under cascading loss"
    if any(term in lower for term in {"sore boils", "skin for skin", "touch his bone", "touch his flesh"}):
        return "integrity under bodily affliction"
    if any(term in lower for term in {"he rose", "risen", "empty tomb", "raised from the dead", "he is alive"}):
        return "resurrection hope and witness"
    if "cross" in lower or "crucifi" in lower:
        return "suffering love and obedient sacrifice"
    if any(term in lower for term in {"deny", "wept bitterly", "remembered"}):
        return "repentance after failure"
    if any(term in lower for term in {"watch", "pray", "cup"}):
        return "watchful surrender before costly obedience"
    if any(term in lower for term in {
        "the lord had visited his people",
        "visited his people in giving them food",
        "may the lord deal kindly",
        "she arose with her daughters-in-law that she might return",
    }):
        return "covenant loyalty that follows God's people through grief and return"
    if ref.startswith(("psalm", "psalms")):
        return "worship and wisdom under the word of god"
    return burden


def _application_lane(reference: str, focus_clause: str, scripture_text: str, lane: str) -> str:
    ref = (reference or "").lower()
    lower = f"{focus_clause} {scripture_text} {lane}".lower()
    cue = resolve_passage_cue(reference=reference, focus_clause=focus_clause, scripture_text=scripture_text)
    if cue is not None:
        return cue.application_lane
    if ref.startswith(("luke 5", "luke 6")):
        if "obedient trust when christ's word overturns exhausted self-reliance" in lower:
            return "obedience that trusts Christ's word more than tired experience"
        if "holy mercy that draws near to the unworthy and the unclean" in lower:
            return "humble nearness to Christ that receives cleansing mercy without hiding need"
        if "forgiving authority exercised in prayerful dependence" in lower:
            return "confident faith that brings real need to Christ's forgiving authority"
        if "new allegiance demanded by the presence of christ" in lower:
            return "wholehearted response that leaves lesser loyalties behind for Christ"
        if "kingdom mercy and authority confronting hardened religion" in lower:
            return "merciful obedience that values people over performative religion"
        if "kingdom obedience shaped by mercy, reversal, and durable hearing" in lower:
            return "concrete mercy and durable obedience that actually does what Christ says"
    if ref.startswith("habakkuk"):
        if "faithful lament under delayed justice" in lower:
            return "honest lament that still turns toward God under delayed justice"
        if "divine sovereignty that unsettles human certainty" in lower:
            return "humble obedience when God's unsettling work overturns human certainty"
        if "divine majesty that shakes nations and rescues god's people" in lower:
            return "reverent trust when God's holy power overturns human pride"
        if "reverent protest that refuses cynical unbelief" in lower:
            return "reverent questioning that refuses cynical unbelief"
        if "watchful faith anchored in promised justice" in lower:
            return "patient trust that waits for God's justice without surrendering faithfulness"
        if "woes exposing predatory pride and idolatry" in lower:
            return "repentance from exploitative gain, violence, intoxication, and false worship"
        if "silent reverence before the enthroned holy one" in lower:
            return "hushed worship before God's holy rule rather than argumentative self-importance"
        if "trembling joy that clings to god amid loss" in lower:
            return "steadfast joy in God when visible supports fail"
    if "covenant nearness received" in lower:
        return "grateful obedience that begins with God's prior mercy"
    if "holy boundaries" in lower:
        return "reverent restraint before God's holy nearness"
    if "holy encounter" in lower:
        return "humbled worship that does not treat God's presence lightly"
    if "covenant life ordered" in lower:
        return "concrete obedience shaped by God's holy commands"
    if "moral refusal of seductive folly" in lower:
        return "clear refusal of companionship and habits that normalize evil"
    if "diligent seeking" in lower:
        return "patient pursuit of wisdom as a treasure worth effort"
    if "secure walking" in lower:
        return "steady walking under wisdom's guard instead of self-trust"
    if "direct confrontation by the risen lord" in lower:
        return "surrender that stops arguing when Christ exposes the truth"
    if "helpless reorientation" in lower:
        return "teachability that accepts dependence after pride is broken"
    if "obedient mediation" in lower:
        return "costly obedience that serves the mercy of God toward surprising people"
    if "public transformation" in lower:
        return "public faithfulness that lets changed allegiance become visible"
    if "strengthening peace" in lower:
        return "quiet faithfulness that builds up the church under holy comfort"
    if "resurrection mercy" in lower:
        return "acts of mercy that strengthen resurrection-shaped witness in community"
    if "ordinary faithfulness" in lower:
        return "ordinary readiness that stays available for God's next assignment"
    if "compromised generations" in lower or "covenant faithfulness remembered" in lower:
        return "humble remembrance that trusts God's covenant faithfulness through imperfect people"
    if "promised presence welcomed" in lower:
        return "obedient trust that receives God's promised presence without resistance"
    if "promised kingship disclosed" in lower:
        return "worshipful obedience that yields to God's promised King"
    if "governs time" in lower or "ordered light" in lower:
        return "ordered attention that lives by God's wise ordering of time"
    if "abundant life" in lower or "flourishing" in lower:
        return "grateful fruitfulness that receives life as God's blessing"
    if "human vocation" in lower or "delegated rule" in lower:
        return "responsible dominion exercised with humility before God"
    if "stewardship" in lower:
        return "ordered stewardship that honors God's good design"
    if "completed work" in lower or "restful trust" in lower:
        return "restful trust that receives God's finished goodness"
    if "life-giving care" in lower or "dependence" in lower:
        return "humble dependence that receives life as God's gift"
    if "generous command" in lower or "obedience" in lower:
        return "grateful obedience within God's generous boundaries"
    if "delegated responsibility" in lower or "discernment" in lower:
        return "attentive discernment in the responsibilities God has given"
    if "warning" in lower or any(term in lower for term in {"gog", "magog"}):
        return "sober obedience that takes God's warning seriously"
    if "judgment publicly displayed" in lower:
        return "sober reverence that does not domesticate God's judgment"
    if "holiness publicly vindicated" in lower:
        return "humble reverence before God's holiness among the nations"
    if "covenant loyalty" in lower and "grief" in lower:
        return "faithful loyalty that chooses God's people over personal comfort"
    if any(term in lower for term in {"loss", "suffering", "affliction", "integrity", "reverent endurance"}):
        return "honest reverence without flattening grief or pain"
    if any(term in lower for term in {"cross", "crucifi", "sacrifice"}):
        return "costly obedience without self-protection"
    if any(term in lower for term in {"resurrection", "risen", "witness"}):
        return "hopeful witness shaped by resurrection reality"
    if any(term in lower for term in {"repentance", "failure"}):
        return "truthful repentance without self-defense"
    # Extract the most distinctive word(s) from the focus clause so the fallback
    # application shares anchor tokens with the benchmark without embedding the
    # full focus clause (which would be verbose in action-step connector phrases).
    import re as _re
    _SKIP = {
        "the", "and", "that", "with", "from", "into", "this", "were", "was", "have",
        "has", "had", "their", "they", "them", "there", "about", "your", "what",
        "you", "when", "while", "would", "could", "should", "among", "during", "after",
        "before", "because", "through", "those", "these", "very", "then", "than", "unto",
        "lord", "god", "him", "his", "her", "its", "our", "who", "she", "came", "went",
        "said", "does", "will", "shall", "also", "not", "but", "for", "are", "all",
        # Common verbs / prepositions / adverbs that produce garbled connector phrases
        # when interpolated as noun-phrase anchors (e.g. "takes makes and down seriously")
        "makes", "make", "made", "leads", "lead", "gives", "give", "given", "walks",
        "walk", "rests", "rest", "takes", "take", "taken", "comes", "come", "seeks",
        "seek", "keeps", "keep", "turns", "turn", "looks", "look", "moves", "move",
        "down", "upon", "over", "away", "back", "near", "open", "like", "just", "only",
    }
    # Require 5+ character words to avoid short verb/adverb fragments as anchors
    _key_tokens = [
        t.lower()
        for t in _re.findall(r"[A-Za-z][A-Za-z']{4,}", focus_clause)
        if t.lower() not in _SKIP
    ][:2]
    _anchor = " and ".join(_key_tokens) if _key_tokens else "this passage"
    return f"concrete obedience that takes {_anchor} seriously rather than at a distance"


def _forbidden_drifts(reference: str, genre: str, lane: str) -> tuple[str, ...]:
    ref = (reference or "").lower()
    drifts: list[str] = [
        "generic encouragement detached from the scene",
        "applications that ignore the specific burden of the passage",
    ]
    if genre == "prophecy":
        drifts.append("speculative end-times detail beyond the text")
    if genre in {"prophecy", "narrative"} and not ref.startswith(("matthew", "mark", "luke", "john")):
        drifts.append("explicit Jesus language not warranted by the passage")
    if "warning" in lane or "suffering" in lane or "loss" in lane:
        drifts.append("flattening severe themes into comfort language")
    return tuple(drifts)


def _scene_summary(reference: str, focus_clause: str, burden: str, lane: str) -> str:
    return f"{reference} opens with a scene marked by {burden}."


def _clean_clause(clause: str) -> str:
    text = re.sub(r"\[([^\]]+)\]", r"\1", str(clause or ""))
    text = " ".join(text.replace('"', "").replace("'", "").split()).strip(" ,.-")
    words = text.split()
    while words and words[0].lower() in _LEADING_FILLER:
        words.pop(0)
    text = " ".join(words).strip(" ,.-")
    if not text:
        return ""
    letters = [ch for ch in text if ch.isalpha()]
    if letters and sum(1 for ch in letters if ch.isupper()) / len(letters) > 0.8:
        text = text.lower()
    return text[0].upper() + text[1:]


def _score_clause(clause: str) -> tuple[int, int]:
    words = clause.split()
    lowered = {word.lower().strip(",.?!;:") for word in words}
    action_hits = len(lowered & _ACTION_WORDS)
    proper_hits = sum(1 for word in words if word[:1].isupper())
    content_hits = sum(1 for word in lowered if len(word) >= 4 and word not in _STOPWORDS)
    lower_clause = clause.lower()
    burden_hits = sum(
        1
        for marker in {
            "attacked",
            "took them",
            "fire of god fell",
            "formed three bands",
            "great wind came",
            "four corners of the house",
            "the lord gave and the lord has taken away",
            "ruin him without cause",
            "skin for skin",
            "touch his bone",
            "touch his flesh",
            "sore boils",
            "accept good from god and not accept adversity",
            "did not sin with his lips",
            "then the lord god took the man and put him",
            "took the man and put him",
            "to cultivate it and keep it",
            "the lord god commanded the man",
            "commanded the man",
            "you may surely eat",
            "you shall not eat",
            "formed every beast",
            "brought them to the man",
            "called a living creature",
        }
        if marker in lower_clause
    )
    creation_hits = sum(
        1
        for marker in {
            "separated the waters",
            "give light on the earth",
            "be fruitful and multiply",
            "subdue it",
            "rule over",
            "completed his work",
            "rested on the seventh day",
            "blessed the seventh day",
            "formed man of dust",
            "breathed into his nostrils",
            "planted a garden",
            "took the man and put him",
            "to cultivate it and keep it",
            "commanded the man",
            "you shall not eat",
            "brought them to the man",
            "called a living creature",
        }
        if marker in lower_clause
    )
    reporting_penalty = 0
    if lower_clause.startswith(("a messenger came", "another also came", "the lord said to satan", "then satan answered")):
        reporting_penalty = 2
    if lower_clause.startswith(("the word of the lord came", "son of man")):
        reporting_penalty = 3
    setup_penalty = sum(
        1
        for marker in {
            "land of cush",
            "gold of that land",
            "bdellium",
            "onyx stone",
            "it flows around",
            "there was no shrub",
            "had not caused it to rain",
        }
        if marker in lower_clause
    )
    return (
        action_hits + proper_hits + content_hits + (2 * burden_hits) + (2 * creation_hits) - reporting_penalty - (2 * setup_penalty),
        -abs(len(words) - 9),
    )


def _focus_clause(scripture_text: str) -> str:
    clauses = [
        _clean_clause(part)
        for part in _CLAUSE_SPLIT_RE.split(str(scripture_text or ""))
    ]
    candidates = [clause for clause in clauses if 4 <= len(clause.split()) <= 16]
    extended_candidates = [clause for clause in clauses if 4 <= len(clause.split()) <= 24]
    preferred = [
        clause
        for clause in candidates
        if not clause.lower().startswith(("the word of the lord came", "son of man"))
    ]
    if preferred:
        candidates = preferred
    high_signal = [
        clause
        for clause in extended_candidates
        if any(marker in clause.lower() for marker in _HIGH_SIGNAL_MARKERS)
    ]
    if high_signal:
        candidates = high_signal
    filtered = [
        clause
        for clause in candidates
        if not any(marker in clause.lower() for marker in _LOW_SIGNAL_MARKERS)
    ]
    if filtered:
        candidates = filtered
    if not candidates:
        fallback = _clean_clause(str(scripture_text or ""))
        if not fallback:
            return "This passage calls for careful attention"
        return " ".join(fallback.split()[:12]).strip()
    return max(candidates, key=_score_clause)


def _pastoral_burden(reference: str, focus_clause: str, scripture_text: str = "") -> str:
    focus_lower = focus_clause.lower()
    lower = f"{focus_clause} {scripture_text}".lower()
    cue = resolve_passage_cue(reference=reference, focus_clause=focus_clause, scripture_text=scripture_text)
    if cue is not None:
        return cue.pastoral_burden
    if any(
        phrase in lower
        for phrase in {
            "worked hard all night and caught nothing",
            "put out into the deep water",
            "let down your nets for a catch",
            "at your word i will let down the nets",
        }
    ):
        return "obedient trust after fruitless labor"
    if any(
        phrase in lower
        for phrase in {
            "depart from me for i am a sinful man",
            "do not fear, from now on you will be catching men",
            "stretched out his hand and touched him",
            "i am willing; be cleansed",
        }
    ):
        return "cleansing mercy for the unworthy"
    if any(
        phrase in lower
        for phrase in {
            "he himself would often slip away to the wilderness and pray",
            "your sins have been forgiven you",
            "which is easier, to say",
            "get up and walk",
        }
    ):
        return "forgiving authority revealed through prayerful dependence"
    if any(
        phrase in lower
        for phrase in {
            # "follow me" removed — too short, false-positives on Psalm 23:6
            # ("goodness and lovingkindness will follow me all the days of my life")
            "he left everything behind",
            "i have not come to call the righteous but sinners to repentance",
            "the disciples of john often fast",
            "when the bridegroom is taken away",
            "new wine must be put into fresh wineskins",
        }
    ):
        return "new allegiance demanded by Christ's presence"
    if any(
        phrase in lower
        for phrase in {
            "that they might find reason to accuse him",
            "is it lawful to do good or to do harm on the sabbath",
            "he chose twelve of them",
            "stood on a level place",
        }
    ):
        return "kingdom mercy confronting hardened religion"
    if any(
        phrase in lower
        for phrase in {
            "blessed are you who are poor",
            "love your enemies",
            "lend, expecting nothing in return",
            "be merciful, just as your father is merciful",
            "why do you call me, 'lord, lord,' and do not do what i say",
            "dug deep and laid a foundation on the rock",
        }
    ):
        return "merciful obedience that hears and does Christ's word"
    if any(
        phrase in lower
        for phrase in {
            "their horses are swifter than leopards",
            "they all come for violence",
            "i am raising up the chaldeans",
            "guilty men",
        }
    ):
        return "sober awe before God's unsettling judgment"
    if any(
        phrase in lower
        for phrase in {
            "your eyes are too pure to approve evil",
            "why are you silent",
            "will they therefore empty their net",
            "continually slay nations without sparing",
        }
    ):
        return "reverent protest that still clings to God"
    if any(
        phrase in lower
        for phrase in {
            "the cup in the lord",
            "become drunk yourself",
            "what profit is the idol",
            "let all the earth be silent before him",
        }
    ):
        return "silent reverence before God's holy rule"
    if any(
        phrase in lower
        for phrase in {
            "woe to him",
            "cutting off many peoples",
            "devised a shameful thing",
            "builds a city with bloodshed",
            "peoples toil for fire",
            "make your neighbors drunk",
            "what profit is the idol",
            "piece of wood",
        }
    ):
        return "holy exposure of predatory pride and false worship"
    if any(
        phrase in lower
        for phrase in {
            "the law is ignored",
            "justice is never upheld",
            "why do you make me see iniquity",
            "violence",
            "destruction",
            "strife exists",
            "contention arises",
        }
    ):
        return "faithful lament under delayed justice"
    if any(
        phrase in lower
        for phrase in {
            "look among the nations",
            "be astonished",
            "i am raising up the chaldeans",
            "their horses are swifter than leopards",
            "they all come for violence",
        }
    ):
        return "sober awe before God's unsettling judgment"
    if any(
        phrase in lower
        for phrase in {
            "are you not from everlasting",
            "your eyes are too pure to approve evil",
            "why are you silent",
            "he makes men like the fish of the sea",
        }
    ):
        return "reverent protest that still clings to God"
    if any(
        phrase in lower
        for phrase in {
            "i will stand on my guard post",
            "write down the vision",
            "the righteous will live by his faith",
            "it hastens toward the goal",
            "wait for it",
        }
    ):
        return "watchful trust while awaiting God's justice"
    if any(
        phrase in lower
        for phrase in {
            "he stood and surveyed the earth",
            "the mountains were shattered",
            "you marched through the earth in indignation",
            "you went forth for the salvation of your people",
            "you pierced with his own spears",
        }
    ):
        return "sober awe before God's saving judgment"
    if any(
        phrase in lower
        for phrase in {
            "the lord is in his holy temple",
            "let all the earth be silent before him",
        }
    ):
        return "silent reverence before God's holy rule"
    if any(
        phrase in lower
        for phrase in {
            "in wrath remember mercy",
            "i heard and my inward parts trembled",
            "though the fig tree should not blossom",
            "yet i will exult in the lord",
            "the lord god is my strength",
        }
    ):
        return "trembling joy that clings to God amid loss"
    if any(
        phrase in lower
        for phrase in {
            "on eagles' wings",
            "brought you to myself",
            "if you will indeed obey my voice",
            "you shall be my own possession",
            "a kingdom of priests",
        }
    ):
        return "grateful covenant nearness before covenant duty"
    if any(
        phrase in lower
        for phrase in {
            "set bounds",
            "do not go up on the mountain",
            "break through to the lord",
            "consecrate them today and tomorrow",
        }
    ):
        return "reverent restraint before holy nearness"
    if any(
        phrase in lower
        for phrase in {
            "mount sinai was all in smoke",
            "sound of the trumpet grew louder",
            "god answered him with thunder",
            "the people trembled",
        }
    ):
        return "humbled worship before God's holiness"
    if any(
        phrase in lower
        for phrase in {
            "you shall have no other gods",
            "you shall not make",
            "remember the sabbath",
            "honor your father and your mother",
            "you shall not murder",
        }
    ):
        return "commandment-shaped obedience under holy authority"
    if any(
        phrase in lower
        for phrase in {
            "enticing sinners",
            "throw in your lot with us",
            "their feet run to evil",
            "let us lie in wait",
        }
    ):
        return "clear refusal of seductive folly"
    if any(
        phrase in lower
        for phrase in {
            "if you receive my words",
            "incline your heart",
            "seek her as silver",
            "search for her as for hidden treasures",
        }
    ):
        return "diligent pursuit of wisdom"
    if any(
        phrase in lower
        for phrase in {
            "walk in the way of good men",
            "the upright will live in the land",
            "discretion will guard you",
            "understanding will watch over you",
        }
    ):
        return "secure walking under wisdom's protection"
    if any(
        phrase in lower
        for phrase in {
            "saul, saul, why are you persecuting me",
            "i am jesus whom you are persecuting",
        }
    ):
        return "humbled surrender before the risen Lord"
    if any(
        phrase in lower
        for phrase in {
            "get up and enter the city",
            "he could see nothing",
            "they led him by the hand",
            "for three days he was without sight",
        }
    ):
        return "helpless reorientation after pride is broken"
    if any(
        phrase in lower
        for phrase in {
            "ananias",
            "go, for he is a chosen instrument",
            "brother saul",
            "laid his hands on him",
        }
    ):
        return "costly obedience that mediates mercy"
    if any(
        phrase in lower
        for phrase in {
            "he is the son of god",
            "all those hearing him continued to be amazed",
            "baffled the jews",
            "increased all the more in strength",
        }
    ):
        return "visible transformation under public witness"
    if any(
        phrase in lower
        for phrase in {
            "the church throughout all judea",
            "enjoying peace",
            "being built up",
            "comfort of the holy spirit",
        }
    ):
        return "strengthening peace under holy comfort"
    if any(
        phrase in lower
        for phrase in {
            "tabitha",
            "dorcas",
            "she opened her eyes",
            "arise",
            "presented her alive",
        }
    ):
        return "resurrection mercy in community life"
    if any(
        phrase in lower
        for phrase in {
            "stayed many days in joppa",
            "with a tanner named simon",
        }
    ):
        return "ordinary readiness for the next assignment"
    if any(
        phrase in lower
        for phrase in {
            "the record of the genealogy of jesus",
            "was the father of",
            "by tamar",
            "by bathsheba",
            "by rahab",
            "by ruth",
        }
    ):
        return "covenant memory through flawed generations"
    if any(
        phrase in lower
        for phrase in {
            "she will bear a son",
            "they shall call his name immanuel",
            "kept her a virgin until she gave birth",
            "joseph awoke from his sleep",
            "the child who has been conceived in her",
        }
    ):
        return "promised presence received in obedient faith"
    if any(
        phrase in lower
        for phrase in {
            "out of you shall come forth a ruler",
            "in bethlehem of judea",
            "where is he who has been born king",
            "we saw his star",
            "shepherd my people israel",
        }
    ):
        return "promised kingship revealed under prophetic fulfillment"
    if any(
        phrase in lower
        for phrase in {
            "separated the waters",
            "let there be lights",
            "give light on the earth",
            "for signs and for seasons",
            "to govern the day",
            "to govern the night",
        }
    ):
        return "ordered attention under God's wise rule"
    if any(
        phrase in lower
        for phrase in {
            "great sea monsters",
            "living creature that moves",
            "be fruitful and multiply and fill the waters",
            "let birds multiply",
        }
    ):
        return "fruitful life under God's blessing"
    if any(
        phrase in lower
        for phrase in {
            "be fruitful and multiply",
            "subdue it",
            "rule over",
            "in our image",
            "according to our likeness",
        }
    ):
        return "ordered stewardship under God's good rule"
    if any(
        phrase in lower
        for phrase in {
            "completed his work",
            "rested on the seventh day",
            "blessed the seventh day",
        }
    ):
        return "restful trust in God's completed work"
    if any(
        phrase in lower
        for phrase in {
            "formed man of dust",
            "breathed into his nostrils",
            "became a living being",
        }
    ):
        return "humble dependence on God's life-giving care"
    if any(
        phrase in lower
        for phrase in {
            "planted a garden",
            "took the man and put him",
            "to cultivate it and keep it",
        }
    ):
        return "entrusted stewardship within God's provision"
    if any(
        phrase in lower
        for phrase in {
            "commanded the man",
            "you may surely eat",
            "you shall not eat",
        }
    ):
        return "obedience within God's generous command"
    if any(
        phrase in lower
        for phrase in {
            "formed every beast",
            "brought them to the man",
            "called a living creature",
        }
    ):
        return "attentive discernment under delegated responsibility"
    if any(
        phrase in lower
        for phrase in {
            "in the latter years you will come",
            "restored from the sword",
            "brought out from many nations",
            "gog",
            "magog",
            "prophesy against him",
            "i am against you",
            "hooks into your jaws",
            "i will bring you out",
        }
    ):
        return "steadfast attention under divine warning"
    if any(
        phrase in lower
        for phrase in {
            "gather from every side to my sacrifice",
            "eat flesh and drink blood",
            "my table with horses and charioteers",
        }
    ):
        return "public judgment displayed before the nations"
    if any(
        phrase in lower
        for phrase in {
            "i will set my glory among the nations",
            "the nations will see my judgment",
            "the house of israel will know",
            "because they acted treacherously",
        }
    ):
        return "public vindication of God's holiness"
    if any(
        phrase in lower
        for phrase in {
            "the lord gave and the lord has taken away",
            "accept good from god and not accept adversity",
            "did not sin",
            "retains his integrity",
        }
    ):
        return "steadfast integrity in suffering"
    if any(
        phrase in lower
        for phrase in {
            "a messenger came",
            "another also came",
            "the sabaeans attacked",
            "fire of god fell",
            "the chaldeans formed three bands",
            "a great wind came",
        }
    ):
        return "endurance under cascading loss"
    if any(
        phrase in lower
        for phrase in {
            "ruin him without cause",
            "touch his bone",
            "touch his flesh",
            "sore boils",
            "skin for skin",
            "satan went out from the presence of the lord",
            "adversary",
        }
    ):
        return "steadfastness under affliction"
    if any(word in focus_lower for word in {"woman", "poured", "anoint", "costly", "perfume"}):
        return "costly devotion"
    if any(word in focus_lower for word in {"potter", "silver", "betray", "betrayer", "judas"}):
        return "treachery and corrupted reward"
    if any(word in focus_lower for word in {"deny", "remembered", "wept"}):
        return "repentance after failure"
    if any(word in focus_lower for word in {"above his head", "king of the jews", "crucifi", "cross", "death"}):
        return "suffering love and obedient endurance"
    if any(word in focus_lower for word in {"wash", "crowd", "governor", "testify", "charge", "pilate", "hear how many things"}):
        return "truthfulness under pressure"
    if any(word in focus_lower for word in {"pray", "watch", "garden", "cup"}):
        return "watchful surrender"
    if any(word in focus_lower for word in {"passover", "prepare", "house", "disciples"}):
        return "prepared obedience"
    if any(word in focus_lower for word in {"buried", "tomb", "stone", "guard"}):
        return "hidden hope under watch"
    if any(word in focus_lower for word in {"he rose", "risen", "empty tomb", "raised from the dead", "he is alive"}):
        return "resurrection hope and faithful witness"
    if any(word in lower for word in {"potter", "silver", "betray", "betrayer", "judas"}):
        return "treachery and corrupted reward"
    if any(word in lower for word in {"deny", "remembered", "wept bitterly"}):
        return "repentance after failure"
    if any(word in lower for word in {"fear", "riot", "mock", "scourge", "silent", "trial", "pilate", "wash", "crowd", "governor", "testify", "charge"}):
        return "truthfulness under pressure"
    if any(word in lower for word in {"cross", "crucifi", "blood", "death", "king of the jews"}):
        return "suffering love and obedient endurance"
    if any(word in lower for word in {"pray", "watch", "garden", "cup"}):
        return "watchful surrender"
    if any(word in lower for word in {"passover", "prepared a place", "upper room", "make ready"}):
        return "prepared obedience"
    if any(word in lower for word in {"buried", "tomb", "stone", "guard"}):
        return "hidden hope under watch"
    if any(word in lower for word in {"he rose", "risen", "empty tomb", "raised from the dead", "he is alive"}):
        return "resurrection hope and faithful witness"
    if any(phrase in lower for phrase in {
        "the lord had visited his people",
        "visited his people in giving them food",
        "may the lord deal kindly",
        "she arose with her daughters-in-law that she might return",
    }):
        return "loyal return to God's people after grief"
    return "faithful response to God's word"


def build_editorial_day_brief(
    *,
    day_number: int,
    scripture_reference: str,
    scripture_text: str,
    study_window_reference: str | None = None,
    passage_resources: PassageResourceBundle | None = None,
) -> EditorialDayBrief:
    focus_clause = _focus_clause(scripture_text)
    burden = _pastoral_burden(scripture_reference, focus_clause, scripture_text)
    genre = _passage_genre(scripture_reference, scripture_text)
    lane = _theological_lane(scripture_reference, focus_clause, scripture_text, burden)
    application_lane = _application_lane(scripture_reference, focus_clause, scripture_text, lane)
    forbidden_drifts = _forbidden_drifts(scripture_reference, genre, lane)
    key_terms = _key_terms(focus_clause, scripture_text)
    # Collect library resources available for this passage (outliner + shared).
    # Empty until content is indexed into the excerpt catalog; the wiring is here
    # so indexed content flows automatically once acquisitions are processed.
    library_res: list[PassageResourceRecord] = []
    if passage_resources is not None:
        library_res.extend(passage_resources.outliner_resources)
        library_res.extend(passage_resources.shared_resources)
    return EditorialDayBrief(
        day_number=day_number,
        week_number=editorial_week_number(day_number),
        scripture_reference=scripture_reference,
        study_window_reference=(study_window_reference or scripture_reference).strip() or scripture_reference,
        key_verse_reference=scripture_reference,
        day_title=f"{scripture_reference} - {focus_clause}",
        focus_clause=focus_clause,
        pastoral_burden=burden,
        genre=genre,
        scene_summary=_scene_summary(scripture_reference, focus_clause, burden, lane),
        theological_lane=lane,
        application_lane=application_lane,
        forbidden_drifts=forbidden_drifts,
        key_terms=key_terms,
        library_resources=tuple(library_res),
    )


def build_editorial_weeks(day_briefs: list[EditorialDayBrief]) -> list[EditorialWeekPlan]:
    by_week: dict[int, list[EditorialDayBrief]] = {}
    for brief in day_briefs:
        by_week.setdefault(brief.week_number, []).append(brief)

    week_plans: list[EditorialWeekPlan] = []
    for week_number in sorted(by_week):
        items = sorted(by_week[week_number], key=lambda item: item.day_number)
        first = items[0]
        last = items[-1]
        title = f"Week {week_number}: {first.pastoral_burden.title()}"
        movement = (
            f"Moves from {first.focus_clause.lower()} "
            f"toward {last.focus_clause.lower()}."
        )
        week_plans.append(
            EditorialWeekPlan(
                week_number=week_number,
                title=title,
                days=[item.day_number for item in items],
                movement_summary=movement,
            )
        )
    return week_plans


def build_editorial_artifact(
    *,
    topic: str,
    num_days: int,
    source_reference: str | None,
    day_plan_rows: list[dict[str, str]],
    day_briefs: list[EditorialDayBrief],
    passage_resources: PassageResourceBundle | None = None,
) -> EditorialBuildArtifact:
    normalized_rows: list[EditorialDayPlanRow] = []
    for index, row in enumerate(day_plan_rows, start=1):
        week_number = int(row.get("week_number", 0) or 0)
        if week_number <= 0:
            week_number = editorial_week_number(index)
        normalized_rows.append(
            EditorialDayPlanRow(
                day_number=int(row.get("day_number", index) or index),
                week_number=week_number,
                topic=str(row.get("topic") or topic),
                scripture_reference=str(row.get("scripture_reference") or "").strip(),
                study_window_reference=str(
                    row.get("study_window_reference")
                    or row.get("scripture_reference")
                    or ""
                ).strip(),
            )
        )

    return EditorialBuildArtifact(
        topic=topic,
        num_days=num_days,
        source_reference=source_reference,
        week_count=max((brief.week_number for brief in day_briefs), default=0),
        passage_resources=passage_resources,
        day_plan=normalized_rows,
        day_briefs=[brief_to_record(brief) for brief in day_briefs],
        week_plans=build_editorial_weeks(day_briefs),
    )
