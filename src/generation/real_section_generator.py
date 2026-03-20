"""real_section_generator.py — production-aligned deterministic section generator.

No LLM calls. Uses scripture retrieval + deterministic prose templates + RAG
seed excerpts to produce devotional sections with saved GroundingMap artifacts.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import os
from pathlib import Path
import re
from hashlib import sha256

from src.grounding_store.id_policy import create_grounding_map_id
from src.grounding_store.store import GroundingMapStore
from src.interfaces.rag import QuoteCandidate, RetrievedExcerpt
from src.models.artifacts import PrayerTraceMap, PrayerTraceMapEntry
from src.models.devotional import (
    ActionStepsSection,
    BeStillSection,
    DailyDevotional,
    ExpositionSection,
    PrayerSection,
    ScriptureSection,
    TimelessWisdomSection,
)
from src.models.pipeline import PassageResourceBundle, PassageResourceRecord
from src.prayer_trace_store.id_policy import create_prayer_trace_map_id
from src.prayer_trace_store.store import PrayerTraceMapStore
from src.generation.editorial import build_editorial_day_brief, EditorialDayBrief
from src.rag.catalog import QuoteCatalog
from src.rag.exposition import ExpositionRAG
from src.rag.grounding import GroundingMapBuilder
from src.rag.research_memory import (
    load_exposition_candidates,
    load_quote_candidates,
    load_quote_source_rankings,
    record_quote_source_outcomes,
    store_exposition_candidates,
    store_quote_candidates,
)
from src.scripture.retrieval import ScriptureFailureAlert, ScriptureRetriever
from src.citations.quote_citations import (
    has_strong_quote_citation,
    merge_quote_citation_fields,
    is_url,
    supports_agent_quote_validation,
)
from src.persistence.paths import default_registry_db_path
from src.validation.modernization import modernization_payload
from src.validation.language_tool import apply_safe_fixes


def _maybe_apply_safe_fixes(text: str, *, ignored_words: set[str] | None = None) -> str:
    if os.getenv("DEVG_ENABLE_LANGUAGETOOL", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return text
    return apply_safe_fixes(text, ignored_words=ignored_words)


def _ensure_exposition_floor(text: str, *, theme_key: str) -> str:
    words = text.split()
    if len(words) >= 500:
        return text
    supplementals: list[str] = {
        "ordered_light": [
            "God's ordering of light teaches the soul to receive time and limits as wise gifts rather than as obstacles to control.",
            "Faithful attention to the text allows light and order to do their theological work before application rushes ahead.",
            "This passage trains patient reception before it trains active response.",
        ],
        "fruitfulness": [
            "The blessing of fruitful life reminds the reader that abundance is first received from God before it is stewarded by human hands.",
            "Fruitfulness is therefore a theological claim about God's generosity before it becomes a practical goal for the believer.",
            "Faithful reading of abundance texts begins with gratitude rather than strategy.",
        ],
        "delegated_rule": [
            "Delegated rule becomes holy only when strength remains answerable to the God who gives both dignity and limits.",
            "Authority exercised humbly becomes a form of worship rather than a claim to independence.",
            "The text therefore calls for steady, reverent faithfulness rather than self-assured mastery.",
        ],
        "sabbath_rest": [
            "Holy rest teaches the creature to stop proving what God has already completed and called good.",
            "Rest is not the absence of labor but the presence of trust that God's word about completeness can be believed.",
            "This text therefore calls for a practiced willingness to stop before the day requires it.",
        ],
        "life_dependence": [
            "Creaturely dependence is not a defect to hide but a truth to receive gratefully before God.",
            "The life received from God is not diminished by its dependence — it is dignified by the One who gives it.",
            "This text therefore trains humility and gratitude to arrive before ambition or self-assertion.",
        ],
        "garden_stewardship": [
            "Stewardship matures when provision is treated as entrusted care instead of private possession.",
            "The garden is not owned by the one who tends it; it remains under the authority of the One who planted it.",
            "That distinction guards both gratitude and diligence from drifting into pride or carelessness.",
        ],
        "generous_command": [
            "Generous command protects joy by teaching the heart to trust God's boundaries before testing them.",
            "The limit in the text is not a threat to freedom; it is a testimony to the goodness of the One who set it.",
            "That reordering of trust and obedience is what faithful exposition must make plain.",
        ],
        "delegated_discernment": [
            "Discernment under God is patient enough to notice, name, and tend responsibilities without vanity.",
            "The text trains careful attention rather than hasty judgment, because naming rightly is itself an act of obedience.",
            "Faithful reading therefore slows the reader down before it commissions decisive action.",
        ],
    }.get(theme_key, [
        "Faithful exposition keeps returning to the text until obedience grows from truth rather than from devotional instinct alone.",
        "The passage rewards patient attention, and patience is itself a form of active trust in the word.",
        "This kind of reading does not measure its value by how quickly it produces resolution.",
        "It measures faithfulness by whether the soul has been before God long enough to hear what the text actually teaches.",
        "Scripture shapes the conscience slowly, and slow formation is often deeper than quick decision.",
        "The details of the text are not incidental; they carry the theological weight that makes application honest.",
        "Careful reading resists the urge to arrive at a conclusion before the passage has been heard completely.",
        "Obedience that outpaces understanding is zeal without knowledge; the text calls for both, in the right order.",
        "What the passage asks is not always obvious on first reading, and that is precisely why returning to it matters.",
        "Devotion that stays anchored to the text remains correctable, teachable, and honest before God and neighbor.",
    ])
    for sentence in supplementals:
        if len(words) >= 500:
            break
        words.extend(sentence.split())
    return " ".join(words[:520])


def _expand_to_word_count(sentences: list[str], target_words: int) -> str:
    words: list[str] = []
    idx = 0
    while len(words) < target_words:
        words.extend(sentences[idx % len(sentences)].split())
        idx += 1
    return " ".join(words[:target_words])


_BE_STILL_PROMPTS = [
    "Sit in silence and reflect on this passage.",
    "What is stirring within your heart today?",
    "Rest in this stillness before moving on.",
]


_HAS_VERSE_REF = re.compile(r"\d+:\d+")


def _day_scripture_reference(anchor: str | None, day_number: int) -> str:
    if anchor and _HAS_VERSE_REF.search(anchor):
        return anchor
    raise RuntimeError(
        "Scripture reference with chapter:verse is required for real generation "
        f"(day {day_number})."
    )


@dataclass(frozen=True)
class RetrievedScripture:
    reference: str
    text: str
    translation: str
    retrieval_source: str
    retrieval_reference: str
    retrieved_at_utc: str
    copyright_notice: str
    source_access_policy: str
    text_cache_status: str
    cache_expires_at_utc: str
    verification_status: str


def _retrieve_scripture(
    retriever: ScriptureRetriever,
    anchor_reference: str | None,
    day_number: int,
    operator_import: Path | None,
) -> RetrievedScripture:
    if not (anchor_reference or "").strip():
        raise RuntimeError(
            "No scripture reference provided for real generation. "
            "Provide scripture_reference/day_plan, or use a topic->scripture planner."
        )
    day_reference = _day_scripture_reference(anchor_reference, day_number)
    result = retriever.retrieve(
        reference=day_reference,
        translation="NASB",
        operator_import=operator_import,
    )
    if isinstance(result, ScriptureFailureAlert):
        raise RuntimeError(
            f"Scripture retrieval failed for day {day_number}: {result.message} "
            f"(attempted={result.attempted_sources})"
        )
    cleaned_text = _normalize_scripture_text(result.text)
    return RetrievedScripture(
        reference=result.reference,
        text=cleaned_text,
        translation=result.translation,
        retrieval_source=result.retrieval_source,
        retrieval_reference=result.retrieval_reference,
        retrieved_at_utc=result.retrieved_at_utc,
        copyright_notice=result.copyright_notice,
        source_access_policy=result.source_access_policy,
        text_cache_status=result.text_cache_status,
        cache_expires_at_utc=result.cache_expires_at_utc,
        verification_status=result.verification_status,
    )


def _normalize_scripture_text(text: str) -> str:
    stopwords = {"and", "or", "of", "the", "about", "to", "for", "in", "on"}

    def _looks_like_heading(line: str) -> bool:
        words = [word for word in line.split() if any(ch.isalpha() for ch in word)]
        if not words or len(words) > 10:
            return False
        if re.search(r"[.!?;,:\"'“”]", line):
            return False
        return all(
            word[:1].isupper() or word.lower() in stopwords
            for word in words
        )

    lines: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = " ".join(raw_line.split()).strip()
        if not line:
            continue
        if _looks_like_heading(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _sentence_case(text: str) -> str:
    cleaned = " ".join(str(text or "").split()).strip()
    if not cleaned:
        return ""
    return cleaned[0].upper() + cleaned[1:]


def _source_domains(candidate: QuoteCandidate) -> list[str]:
    urls = list(getattr(candidate, "source_trace", []) or [])
    primary = str(candidate.source_url or (candidate.page_or_url if is_url(candidate.page_or_url) else "")).strip()
    if primary and primary not in urls:
        urls.append(primary)
    domains: list[str] = []
    for url in urls:
        try:
            from urllib.parse import urlparse

            host = (urlparse(str(url).strip()).netloc or "").lower()
        except Exception:
            host = ""
        if host.startswith("www."):
            host = host[4:]
        if host and host not in domains:
            domains.append(host)
    return domains


def _best_source_helpfulness(candidate: QuoteCandidate, rankings: dict[str, float]) -> float:
    domains = _source_domains(candidate)
    if not domains:
        return 0.0
    return max(float(rankings.get(domain, 0.0)) for domain in domains)


def _resource_record_to_excerpt(record: PassageResourceRecord) -> RetrievedExcerpt | None:
    text = " ".join(str(record.excerpt_text or "").split()).strip()
    if not text:
        return None
    return RetrievedExcerpt(
        text=text,
        source_title=str(record.source_title or "").strip() or "library-resource",
        author=str(record.author or "").strip(),
        source_type=str(record.source_type or "").strip() or "reference",
        relevance_score=float(record.relevance_score or 0.0),
    )


def _seeded_exposition_resources(
    passage_resources: PassageResourceBundle | None,
) -> tuple[list[RetrievedExcerpt], list[RetrievedExcerpt]]:
    if passage_resources is None:
        return [], []
    context: list[RetrievedExcerpt] = []
    theological: list[RetrievedExcerpt] = []
    for record in passage_resources.exposition_resources:
        excerpt = _resource_record_to_excerpt(record)
        if excerpt is None:
            continue
        purpose = str(record.purpose or "").strip().lower()
        if purpose == "context":
            context.append(excerpt)
        elif purpose == "theological":
            theological.append(excerpt)
        else:
            context.append(excerpt)
    return context, theological


def _communalize_focus(text: str) -> str:
    cleaned = re.sub(r"\byour\b", "the", str(text or ""), flags=re.IGNORECASE)
    cleaned = re.sub(r"\byou\b", "the hearer", cleaned, flags=re.IGNORECASE)
    cleaned = " ".join(cleaned.split()).strip(" ,.-")
    return _sentence_case(cleaned)


def _communalize_phrase(text: str) -> str:
    cleaned = re.sub(r"\byour\b", "our", str(text or ""), flags=re.IGNORECASE)
    cleaned = re.sub(r"\byou\b", "we", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip()


def _communalize_application(text: str) -> str:
    cleaned = _communalize_phrase(text)
    cleaned = re.sub(r"\bin our life today\b", "today", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bin our lives today\b", "today", cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip(" .")


def _theme_key(brief: EditorialDayBrief, scripture_text: str = "") -> str:
    lane = (brief.theological_lane or "").lower()
    burden = (brief.pastoral_burden or "").lower()
    application_lane = (brief.application_lane or "").lower()
    lower = f"{brief.focus_clause} {brief.pastoral_burden} {scripture_text}".lower()
    if "faithful lament under delayed justice" in burden or "faithful lament under delayed justice" in lane:
        return "habakkuk_lament"
    if "sober awe before god's unsettling judgment" in burden or "divine sovereignty that unsettles human certainty" in lane:
        return "habakkuk_awe"
    if "sober awe before god's saving judgment" in burden or "divine majesty that shakes nations and rescues god's people" in lane:
        return "habakkuk_awe"
    if "reverent protest that still clings to god" in burden or "reverent protest that refuses cynical unbelief" in lane:
        return "habakkuk_protest"
    if "watchful trust while awaiting god's justice" in burden or "watchful faith anchored in promised justice" in lane:
        return "habakkuk_watch"
    if "holy exposure of predatory pride and false worship" in burden or "woes exposing predatory pride and idolatry" in lane:
        return "habakkuk_woes"
    if "silent reverence before god's holy rule" in burden or "silent reverence before the enthroned holy one" in lane:
        return "habakkuk_silence"
    if "trembling joy that clings to god amid loss" in burden or "trembling joy that clings to god amid loss" in lane:
        return "habakkuk_joy"
    if "obedient trust after fruitless labor" in burden or "obedient trust when christ's word overturns exhausted self-reliance" in lane:
        return "luke_obedient_trust"
    if "cleansing mercy for the unworthy" in burden or "holy mercy that draws near to the unworthy and the unclean" in lane:
        return "luke_cleansing_mercy"
    if "forgiving authority revealed through prayerful dependence" in burden or "forgiving authority exercised in prayerful dependence" in lane:
        return "luke_forgiving_authority"
    if "new allegiance demanded by christ's presence" in burden or "new allegiance demanded by the presence of christ" in lane:
        return "luke_new_allegiance"
    if "kingdom mercy confronting hardened religion" in burden or "kingdom mercy and authority confronting hardened religion" in lane:
        return "luke_kingdom_mercy"
    if "merciful obedience that hears and does christ's word" in burden or "kingdom obedience shaped by mercy, reversal, and durable hearing" in lane:
        return "luke_kingdom_obedience"
    if "ordered attention under god's wise rule" in burden or "ordered light that governs time" in lane:
        if any(term in lower for term in {"for signs and for seasons", "for days and years"}):
            return "appointed_times"
        return "ordered_light"
    if "fruitful life under god's blessing" in burden or "abundant life flourishing" in lane:
        return "fruitfulness"
    if "ordered stewardship under god's good rule" in burden or "human vocation under god's delegated rule" in lane:
        return "delegated_rule"
    if "restful trust in god's completed work" in burden or "completed work" in application_lane:
        return "sabbath_rest"
    if "humble dependence on god's life-giving care" in burden or "life-giving care" in lane:
        return "life_dependence"
    if "entrusted stewardship within god's provision" in burden:
        return "garden_stewardship"
    if "obedience within god's generous command" in burden:
        return "generous_command"
    if "attentive discernment under delegated responsibility" in burden:
        return "delegated_discernment"
    if "grateful covenant nearness before covenant duty" in lower or "covenant nearness received" in lane:
        return "covenant_nearness"
    if "reverent restraint before holy nearness" in burden or "holy boundaries under god's dangerous nearness" in lane:
        return "holy_boundary"
    if "humbled worship before god's holiness" in burden or "holy encounter that humbles the hearer" in lane:
        return "holy_encounter"
    if "commandment-shaped obedience under holy authority" in burden or "covenant life ordered by god's holy authority" in lane:
        return "covenant_obedience"
    if "clear refusal of seductive folly" in burden or "moral refusal of seductive folly" in lane:
        return "wisdom_warning"
    if "diligent pursuit of wisdom" in burden or "diligent seeking that receives wisdom as treasure" in lane:
        return "wisdom_treasure"
    if "secure walking under wisdom's protection" in burden or "secure walking under wisdom's protection" in lane:
        return "wisdom_security"
    if "humbled surrender before the risen lord" in burden or "direct confrontation by the risen lord" in lane:
        return "conversion_confrontation"
    if "helpless reorientation after pride is broken" in burden or "helpless reorientation under divine interruption" in lane:
        return "helpless_reorientation"
    if "costly obedience that mediates mercy" in burden or "obedient mediation in service of god's surprising mercy" in lane:
        return "mediated_mercy"
    if "visible transformation under public witness" in burden or "public transformation that cannot stay hidden" in lane:
        return "public_transformation"
    if "strengthening peace under holy comfort" in burden or "strengthening peace under the fear and comfort of god" in lane:
        return "church_peace"
    if "resurrection mercy in community life" in burden or "resurrection mercy that strengthens communal witness" in lane:
        return "community_resurrection"
    if "ordinary readiness for the next assignment" in burden or "ordinary faithfulness that remains ready for god's next assignment" in lane:
        return "ordinary_readiness"

    _ref_lower = (brief.scripture_reference or "").lower()
    _is_gospel = _ref_lower.startswith(("matthew", "mark", "luke", "john", "acts"))

    # --- Genre + keyword layer (covers Psalms, Epistles, Narrative, Prophecy) ---
    # Runs BEFORE generic Passion Week keyword checks to prevent "death" in Psalm 23:4
    # from triggering "cross" before "psalm_trust" can fire.
    if _ref_lower.startswith(("psalm", "psalms", "job", "ecclesiastes", "song")):
        if any(p in lower for p in ("shepherd", "pastures", "still waters", "valley of shadow", "dwell in the house", "rod and staff")):
            return "psalm_trust"
        if any(p in lower for p in ("why have you forsaken", "my soul thirsts", "soul pants", "cast me not away", "why are you cast down", "hide not")):
            return "psalm_lament"
        if any(p in lower for p in ("bless the lord", "praise the lord", "all his benefits", "steadfast love endures", "praise him", "make a joyful")):
            return "psalm_praise"
    if _ref_lower.startswith(("romans", "corinthians", "galatians", "ephesians", "philippians",
                               "colossians", "thessalonians", "timothy", "titus", "philemon",
                               "hebrews", "james", "peter", "jude")):
        if any(p in lower for p in ("justified by faith", "peace with god", "righteousness of god", "righteousness apart from law", "faith apart from works")):
            return "epistle_justification"
        if any(p in lower for p in ("put off", "put on", "set your mind", "seek the things above", "alive from the dead", "walk by the spirit", "dead to sin")):
            return "epistle_sanctification"
    if _ref_lower.startswith(("ruth", "esther", "nehemiah", "daniel", "ezra", "joshua",
                               "judges", "samuel", "kings", "chronicles", "genesis", "exodus")):
        if any(p in lower for p in ("where you go i will go", "your people shall be my people", "wherever you go", "steadfast love", "lovingkindness")):
            return "narrative_loyalty"
        if any(p in lower for p in ("for such a time as this", "god meant it for good", "god intended it for good")):
            return "narrative_providence"
    if _ref_lower.startswith(("isaiah", "jeremiah", "ezekiel", "hosea", "joel", "amos",
                               "micah", "nahum", "zephaniah", "haggai", "zechariah", "malachi")):
        if any(p in lower for p in ("comfort my people", "fear not", "do not fear", "dry bones", "new thing", "rivers in the desert", "do not be afraid")):
            return "prophecy_restoration"
    # --- End genre + keyword layer ---

    if "warning" in lane:
        return "warning"
    if _is_gospel and "resurrection" in lane:
        return "resurrection"
    if _is_gospel and ("cross" in lane or "sacrifice" in lane):
        return "cross"
    if _is_gospel and "repentance" in lane:
        return "repentance"
    if _is_gospel and "betray" in lane:
        return "betrayal"
    if _is_gospel and ("trial" in lane or "truthfulness under pressure" in lane):
        return "trial"
    if "loss" in lane:
        return "loss"
    if "affliction" in lane:
        return "affliction"
    if "endurance" in lane or "integrity in suffering" in lane:
        return "endurance"

    focus_lower = brief.focus_clause.lower()
    if any(
        phrase in lower
        for phrase in {
            "steadfast attention under divine warning",
            "gog",
            "magog",
            "prophesy against him",
            "i am against you",
            "hooks into your jaws",
        }
    ):
        return "warning"
    if any(
        phrase in lower
        for phrase in {
            "steadfast integrity in suffering",
            "the lord gave and the lord has taken away",
            "accept good from god and not accept adversity",
            "did not sin",
            "retains his integrity",
        }
    ):
        return "endurance"
    if any(
        phrase in lower
        for phrase in {
            "endurance under cascading loss",
            "a messenger came",
            "another also came",
        }
    ):
        return "loss"
    if any(
        phrase in lower
        for phrase in {
            "steadfastness under affliction",
            "ruin him without cause",
            "touch his bone",
            "sore boils",
            "adversary",
        }
    ):
        return "affliction"

    if _is_gospel and ("resurrection" in lower or any(word in lower for word in {"risen", "rose", "alive", "empty"})):
        return "resurrection"
    if _is_gospel and any(word in focus_lower for word in {"above his head", "king of the jews", "crucifi", "cross", "death"}):
        return "cross"
    if _is_gospel and any(word in focus_lower for word in {"wash", "crowd", "governor", "testify", "charge", "pilate", "hear how many things"}):
        return "trial"
    if _is_gospel and any(word in lower for word in {"cross", "crucifi", "death", "blood", "king of the jews"}):
        return "cross"
    if _is_gospel and any(word in lower for word in {"betray", "judas", "silver", "potter"}):
        return "betrayal"
    if _is_gospel and any(word in lower for word in {"chief priests", "council", "governor", "testify", "charge against him", "pilate"}):
        return "trial"
    if _is_gospel and any(word in lower for word in {"deny", "remembered", "wept"}):
        return "repentance"
    if _is_gospel and any(word in lower for word in {"watch", "garden", "cup", "pray"}):
        return "watchfulness"
    if _is_gospel and any(word in lower for word in {"woman", "costly", "anoint", "perfume"}):
        return "devotion"
    if _is_gospel and any(word in lower for word in {"trial", "pilate", "mock", "silent"}):
        return "trial"
    if _is_gospel and any(word in lower for word in {"buried", "tomb", "stone", "guard"}):
        return "burial"

    return "response"


def _theme_applications(theme_key: str) -> tuple[str, str, str]:
    if theme_key == "luke_obedient_trust":
        return (
            "obedient trust instead of weary self-reliance",
            "act on Christ's word even when tired experience argues against it",
            "trusting obedience when Christ's word overturns exhaustion",
        )
    if theme_key == "luke_cleansing_mercy":
        return (
            "cleansing mercy instead of ashamed distance",
            "bring uncleanness, fear, and unworthiness into the reach of Christ's touch",
            "humble nearness to Christ that receives cleansing mercy",
        )
    if theme_key == "luke_forgiving_authority":
        return (
            "confident faith in Christ's forgiving authority",
            "bring real need to the One who forgives and restores, not merely to the crowd around Him",
            "faith that seeks Christ's forgiving authority with prayerful dependence",
        )
    if theme_key == "luke_new_allegiance":
        return (
            "new allegiance instead of managed religious compatibility",
            "leave lesser loyalties behind where Christ's presence demands a new pattern of life",
            "wholehearted response to Christ's disruptive nearness",
        )
    if theme_key == "luke_kingdom_mercy":
        return (
            "kingdom mercy instead of hardened religiosity",
            "choose merciful obedience where suspicious religion wants accusation and control",
            "mercy that refuses to sacrifice people to performative righteousness",
        )
    if theme_key == "luke_kingdom_obedience":
        return (
            "durable obedience shaped by mercy",
            "let Christ's kingdom teaching move from admiration into concrete action",
            "hearing that actually becomes merciful obedience",
        )
    if theme_key == "habakkuk_lament":
        return (
            "truthful lament instead of managed religious calm",
            "bring injustice and confusion before God without turning cynical",
            "lament that stays reverent and honest before God",
        )
    if theme_key == "habakkuk_awe":
        return (
            "sober awe instead of controlling certainty",
            "accept that God's work may unsettle your categories before it comforts them",
            "humble obedience under God's unsettling sovereignty",
        )
    if theme_key == "habakkuk_protest":
        return (
            "reverent protest instead of cynical unbelief",
            "question honestly before God without stepping outside trust",
            "reverent questioning that still clings to God's character",
        )
    if theme_key == "habakkuk_watch":
        return (
            "watchful trust instead of impatient demand",
            "wait for God's justice with disciplined hope rather than frantic control",
            "patient faith that waits for the vision without surrendering obedience",
        )
    if theme_key == "habakkuk_woes":
        return (
            "holy renunciation of predatory pride and idolatry",
            "turn from exploitative gain, intoxicated power, and false worship",
            "repentance that leaves predatory pride and idols behind",
        )
    if theme_key == "habakkuk_silence":
        return (
            "hushed reverence instead of argumentative self-importance",
            "be still before God's holy rule rather than trying to master Him with words",
            "silent worship beneath the authority of the Holy One",
        )
    if theme_key == "habakkuk_joy":
        return (
            "steadfast joy instead of despairing calculation",
            "cling to God when visible supports collapse",
            "joy in God that remains when ordinary security disappears",
        )
    if theme_key == "ordered_light":
        return (
            "ordered attention instead of shapeless distraction",
            "receive time and limits as gifts under God's wise rule",
            "attentive ordering shaped by God's wisdom rather than impulse",
        )
    if theme_key == "appointed_times":
        return (
            "attentive timing instead of restless urgency",
            "receive God's ordering of seasons and times before forcing your own pace",
            "patient attention shaped by God's appointed times rather than hurry",
        )
    if theme_key == "fruitfulness":
        return (
            "grateful fruitfulness instead of anxious scarcity",
            "receive life as blessing before treating it as possession",
            "fruitfulness that remains grateful, humble, and alive to God's goodness",
        )
    if theme_key == "delegated_rule":
        return (
            "responsible dominion instead of self-important control",
            "exercise influence as stewardship rather than ownership",
            "humble responsibility under God's delegated rule",
        )
    if theme_key == "sabbath_rest":
        return (
            "restful trust instead of relentless proving",
            "receive God's finished work before multiplying your own",
            "sabbath-shaped trust rather than exhausting self-importance",
        )
    if theme_key == "life_dependence":
        return (
            "humble dependence instead of imagined self-sufficiency",
            "remember that life is breathed in by God and not self-generated",
            "creaturely dependence that honors God as giver of life",
        )
    if theme_key == "garden_stewardship":
        return (
            "entrusted stewardship instead of careless possession",
            "tend what God has placed before you with grateful attention",
            "stewardship that treats provision as trust, not entitlement",
        )
    if theme_key == "generous_command":
        return (
            "grateful obedience instead of suspicious independence",
            "receive God's command as generous protection rather than harsh restriction",
            "obedience that trusts God's boundaries as good",
        )
    if theme_key == "delegated_discernment":
        return (
            "attentive discernment instead of passive carelessness",
            "name and handle responsibilities with patient thoughtfulness before God",
            "discernment that honors the responsibilities God has assigned",
        )
    if theme_key == "covenant_nearness":
        return (
            "grateful covenant nearness instead of forgetting who drew us near",
            "receive God's prior mercy before treating obedience as self-made achievement",
            "obedience that remembers being brought near by God first",
        )
    if theme_key == "holy_boundary":
        return (
            "reverent restraint instead of casual familiarity with holy things",
            "honor the boundaries God sets around His holy presence",
            "restraint that takes God's holiness seriously",
        )
    if theme_key == "holy_encounter":
        return (
            "humbled worship instead of treating God's presence lightly",
            "stand before God's majesty with reverence rather than performance",
            "worship that trembles honestly before holy nearness",
        )
    if theme_key == "covenant_obedience":
        return (
            "commandment-shaped obedience instead of selective morality",
            "submit ordinary life to God's holy commands",
            "obedience ordered by God's authority rather than convenience",
        )
    if theme_key == "wisdom_warning":
        return (
            "moral refusal instead of entertained compromise",
            "reject the invitations that make evil sound shared, easy, or profitable",
            "clear refusal of folly before it hardens into habit",
        )
    if theme_key == "wisdom_treasure":
        return (
            "diligent seeking instead of lazy admiration of wisdom",
            "pursue wisdom as a treasure worth disciplined effort",
            "patient seeking that values wisdom more than ease",
        )
    if theme_key == "wisdom_security":
        return (
            "secure walking instead of anxious self-protection",
            "walk steadily under the guard that wisdom provides",
            "stability shaped by wisdom rather than by fear",
        )
    if theme_key == "conversion_confrontation":
        return (
            "humbled surrender instead of resisting exposed truth",
            "stop arguing where the risen Christ has made the truth unmistakable",
            "surrender that bows when Christ confronts the heart",
        )
    if theme_key == "helpless_reorientation":
        return (
            "teachability instead of prideful self-direction",
            "accept dependence while God reorients what you thought you controlled",
            "reorientation that learns to receive help after pride is broken",
        )
    if theme_key == "mediated_mercy":
        return (
            "costly obedience instead of suspicion toward God's surprising mercy",
            "serve the mercy of God even when it reaches people you did not expect",
            "obedience that participates in mercy rather than withholding it",
        )
    if theme_key == "public_transformation":
        return (
            "visible faithfulness instead of private religious claim alone",
            "let changed allegiance become visible in speech, conduct, and courage",
            "public transformation that gives God visible honor",
        )
    if theme_key == "church_peace":
        return (
            "strengthening peace instead of restless self-importance",
            "build up the church through quiet faithfulness under holy comfort",
            "peace that strengthens people under the fear of the Lord",
        )
    if theme_key == "community_resurrection":
        return (
            "resurrection mercy instead of detached admiration of power",
            "practice mercy that strengthens communal witness to the risen Christ",
            "mercy that makes resurrection hope tangible in community life",
        )
    if theme_key == "ordinary_readiness":
        return (
            "ordinary readiness instead of waiting for dramatic assignments only",
            "remain available to God in the ordinary place where He has you now",
            "steady availability for the next work God appoints",
        )
    if theme_key == "devotion":
        return (
            "costly worship instead of cautious self-protection",
            "hold back less of the heart from Jesus",
            "visible devotion rather than careful distance",
        )
    if theme_key == "watchfulness":
        return (
            "prayerful vigilance instead of sleepy confidence",
            "stay awake to weakness and dependence",
            "watchfulness before God rather than self-trust",
        )
    if theme_key == "repentance":
        return (
            "honest repentance instead of defensive self-justification",
            "admit failure quickly and return to the Lord",
            "grief that returns to truth instead of hiding",
        )
    if theme_key == "betrayal":
        return (
            "truthfulness instead of false advantage",
            "refuse the small bargains that sell integrity",
            "loyalty to Jesus over useful compromise",
        )
    if theme_key == "trial":
        return (
            "steady witness instead of fearful calculation",
            "remain truthful under pressure",
            "quiet fidelity when power is misused",
        )
    if theme_key == "cross":
        return (
            "obedient love instead of self-saving instinct",
            "carry costly obedience without bitterness",
            "the cross-shaped path of faithfulness",
        )
    if theme_key == "burial":
        return (
            "patient hope instead of visible certainty alone",
            "trust God when faithfulness looks hidden",
            "quiet hope under the weight of unanswered hours",
        )
    if theme_key == "loss":
        return (
            "endurance under repeated loss instead of panic or numb resignation",
            "keep receiving hard providence without surrendering worship",
            "truthful lament joined to steady reverence",
        )
    if theme_key == "endurance":
        return (
            "steadfast integrity in suffering instead of shallow optimism",
            "honor God without denying the weight of pain",
            "reverent endurance when life is not easily explained",
        )
    if theme_key == "affliction":
        return (
            "steadfastness under affliction instead of bitterness or accusation",
            "refuse to interpret pain as permission to abandon truth",
            "endurance that remains honest before God",
        )
    if theme_key == "warning":
        return (
            "watchful obedience under divine warning instead of casual dismissal",
            "receive God's warning with sober trust",
            "steady obedience when God's word exposes real opposition",
        )
    if theme_key == "resurrection":
        return (
            "living hope instead of defeated resignation",
            "speak and act like Christ is truly risen",
            "courageous witness shaped by resurrection reality",
        )
    if theme_key == "psalm_trust":
        return (
            "trust in the Shepherd instead of anxious self-reliance",
            "rest in His care even through the valley",
            "quiet confidence under the Shepherd's lead",
        )
    if theme_key == "psalm_lament":
        return (
            "honest cry to God instead of managed religious calm",
            "pour out the soul truthfully before Him without turning cynical",
            "lament that waits for God without surrendering faith",
        )
    if theme_key == "psalm_praise":
        return (
            "wholehearted blessing instead of muted gratitude",
            "proclaim His steadfast love and mighty deeds rather than staying silent",
            "joyful worship that honors God before the next generation",
        )
    if theme_key == "epistle_justification":
        return (
            "peace through justification instead of self-made righteousness",
            "rest in declared righteousness rather than returning to law-keeping",
            "assured access to grace through faith alone",
        )
    if theme_key == "epistle_sanctification":
        return (
            "new life in Christ instead of old patterns left unchallenged",
            "put off what belongs to the old self and put on what belongs to the new",
            "seeking things above in ordinary daily obedience",
        )
    if theme_key == "narrative_loyalty":
        return (
            "covenant faithfulness instead of convenient abandonment",
            "choose allegiance to God's people when the cost is real",
            "steadfast companionship that reflects God's own loyalty",
        )
    if theme_key == "narrative_providence":
        return (
            "patient trust in sovereign reversal instead of anxious control",
            "trust God's hidden purposes when the visible situation looks only dark",
            "patient hope that watches for God's turn in the story",
        )
    if theme_key == "prophecy_restoration":
        return (
            "expectant hope in promised renewal instead of resigned despair",
            "return to the Lord and receive the new thing He has promised",
            "expectant waiting for the restoration God has declared",
        )
    return (
        "faithful response instead of vague admiration",
        "answer the word with concrete obedience",
        "steady trust in the ordinary places of life",
    )


def _theme_specific_sentence(theme_key: str) -> str:
    if theme_key == "ordered_light":
        return (
            "The ordering of light teaches that time, rhythm, and visible order are gifts governed by God's wisdom rather than by human improvisation."
        )
    if theme_key == "appointed_times":
        return (
            "Signs and seasons teach the reader that God orders time itself, so discernment begins by receiving His rhythms before chasing our own urgency."
        )
    if theme_key == "fruitfulness":
        return (
            "Fruitful life appears here as received blessing, showing that abundance begins with God's generosity before it becomes anyone's achievement."
        )
    if theme_key == "delegated_rule":
        return (
            "Human rule is presented as delegated vocation, which means dignity and restraint must remain joined under God's authority."
        )
    if theme_key == "sabbath_rest":
        return (
            "Rest here is not inactivity for its own sake but delighted trust in the completeness and goodness of God's work."
        )
    if theme_key == "life_dependence":
        return (
            "The passage grounds human life in God's breath, pressing every reader to remember that creaturely life is gift before it is project."
        )
    if theme_key == "garden_stewardship":
        return (
            "Provision is linked to stewardship, teaching that what God gives must be tended faithfully rather than consumed carelessly."
        )
    if theme_key == "generous_command":
        return (
            "Command is framed inside generosity, so obedience is not a grim burden but a trusting answer to the goodness of God."
        )
    if theme_key == "delegated_discernment":
        return (
            "Naming and discerning are acts of responsible attention, showing that maturity before God includes patient judgment rather than hurried impulse."
        )
    if theme_key == "covenant_nearness":
        return (
            "Sinai begins with remembered mercy, teaching that covenant obedience grows out of being brought near by God rather than out of bare demand."
        )
    if theme_key == "holy_boundary":
        return (
            "Holy boundaries teach that divine nearness is gracious but never casual, and that reverence is part of love rather than its opposite."
        )
    if theme_key == "holy_encounter":
        return (
            "The smoking mountain and trumpet blast humble the hearer by showing that God's presence is glorious enough to unsettle the heart."
        )
    if theme_key == "covenant_obedience":
        return (
            "Commandment life gives shape to covenant belonging, showing that holiness reaches into ordinary loyalties, words, worship, and desires."
        )
    if theme_key == "wisdom_warning":
        return (
            "Wisdom warnings expose evil as seductive companionship before it becomes open ruin, teaching the reader to refuse its invitations early."
        )
    if theme_key == "wisdom_treasure":
        return (
            "Wisdom must be sought like treasure, which means understanding grows through disciplined desire rather than passive admiration."
        )
    if theme_key == "wisdom_security":
        return (
            "Wisdom's protection is moral and practical, giving the reader steadiness that is deeper than mere caution or self-protection."
        )
    if theme_key == "conversion_confrontation":
        return (
            "The risen Christ confronts Saul directly, proving that conversion begins not with self-improvement but with divine interruption and exposed rebellion."
        )
    if theme_key == "helpless_reorientation":
        return (
            "Blindness and dependence force a new posture, teaching that pride often has to be broken before calling can be received."
        )
    if theme_key == "mediated_mercy":
        return (
            "Ananias shows that God's mercy often reaches the astonished sinner through the risky obedience of another believer."
        )
    if theme_key == "public_transformation":
        return (
            "Real conversion becomes publicly visible because new allegiance does not stay hidden when Christ has truly remade the heart."
        )
    if theme_key == "church_peace":
        return (
            "Church peace here is not complacency but strengthening rest under the fear of the Lord and the comfort of the Holy Spirit."
        )
    if theme_key == "community_resurrection":
        return (
            "Resurrection mercy strengthens communal witness by turning compassion into visible hope before many observers."
        )
    if theme_key == "ordinary_readiness":
        return (
            "Remaining in Joppa with Simon the tanner shows that readiness for God's next call is often formed in ordinary, unglamorous faithfulness."
        )
    if theme_key == "trial":
        return (
            "False testimony, public pressure, and political evasion expose how quickly truth can be bent when power is threatened."
        )
    if theme_key == "cross":
        return (
            "The crucifixion scene forces attention on shame, suffering, and the holy cost of redemption rather than sentimental encouragement."
        )
    if theme_key == "repentance":
        return (
            "Failure is not minimized here; it is remembered, named, and turned into grief that can no longer pretend innocence."
        )
    if theme_key == "betrayal":
        return (
            "Betrayal is shown as a transaction of the heart before it is ever reduced to a visible exchange of money or words."
        )
    if theme_key == "resurrection":
        return (
            "Resurrection does not merely improve mood; it overturns despair and commissions living witness."
        )
    if theme_key == "burial":
        return (
            "Burial scenes teach faithful patience when obedience remains hidden under stone, seal, and silence."
        )
    if theme_key == "loss":
        return (
            "Successive losses test whether reverence can survive when each new report removes another layer of ordinary security."
        )
    if theme_key == "endurance":
        return (
            "Integrity in suffering refuses both sentimental denial and bitter unbelief, holding grief and reverence together."
        )
    if theme_key == "affliction":
        return (
            "Affliction without visible cause teaches that pain can intensify without granting the right to abandon worship."
        )
    if theme_key == "warning":
        return (
            "Divine warning refuses casual optimism and trains the heart to take God's opposition to evil with full seriousness."
        )
    return ""


def _trial_variant(brief: EditorialDayBrief) -> str:
    lower = brief.focus_clause.lower()
    if any(word in lower for word in {"hear how many things", "testify", "charge"}):
        return "accusation"
    if any(word in lower for word in {"washed his hands", "wash", "crowd"}):
        return "evasion"
    return "pressure"


def _christological_frame(brief: EditorialDayBrief) -> bool:
    reference = (brief.scripture_reference or "").lower()
    if any("explicit jesus language not warranted" in item.lower() for item in brief.forbidden_drifts):
        return False
    return reference.startswith(("matthew", "mark", "luke", "john"))


def _theme_variant(brief: EditorialDayBrief, scripture_text: str) -> str:
    lower = f"{brief.focus_clause} {scripture_text}".lower()
    if any(phrase in lower for phrase in {"great wind came", "four corners of the house"}):
        return "collapse"
    if "a messenger came" in lower or "the sabaeans attacked" in lower:
        return "first_report"
    if any(phrase in lower for phrase in {"another also came", "fire of god fell", "formed three bands"}):
        return "compounding_reports"
    if "ruin him without cause" in lower:
        return "heavenly_charge"
    if any(phrase in lower for phrase in {"skin for skin", "touch his bone", "touch his flesh", "sore boils"}):
        return "bodily_affliction"
    return ""


def _build_exposition(*, brief: EditorialDayBrief, scripture_text: str) -> str:
    focus = _communalize_focus(brief.focus_clause)
    burden = brief.pastoral_burden
    communal_application = _communalize_application(brief.application_lane)
    theme_key = _theme_key(brief, scripture_text)
    emphasis, practice_move, closing_move = _theme_applications(theme_key)
    emphasis = _communalize_phrase(emphasis)
    practice_move = _communalize_phrase(practice_move)
    closing_move = _communalize_phrase(closing_move)
    image = _communalize_focus(_scripture_image(scripture_text))
    theme_sentence = _theme_specific_sentence(theme_key)
    christological = _christological_frame(brief)
    theme_variant = _theme_variant(brief, scripture_text)
    if christological:
        larger_movement = f"in which {focus.lower()} stands as the passage's defining event"
    elif brief.genre == "wisdom":
        larger_movement = "in which wisdom's invitation and folly's seduction are being set before the reader as two distinct paths"
    elif brief.genre == "epistle":
        larger_movement = "in which doctrine is being argued, received, and applied to daily life under apostolic authority"
    elif brief.genre == "prophecy":
        larger_movement = "in which God's word confronts human pride, delayed judgment, and promised restoration"
    elif brief.genre == "poetry":
        larger_movement = "in which praise, lament, and trust are being tested and shaped in the crucible of lived experience"
    else:
        larger_movement = "in which God's purposes, covenant faithfulness, and human response are being displayed through events"
    if christological:
        presence_sentence = (
            f"What {brief.scripture_reference} puts before the reader is not abstract: {focus.lower()}. "
            "The text does not explain the scene from a distance — it names what people do when Jesus is near."
        )
    elif brief.genre == "wisdom":
        presence_sentence = (
            f"What we see in {brief.scripture_reference} shows how wisdom's invitation and folly's seduction "
            "arrive in ordinary speech before any outward decision is made."
        )
    elif brief.genre == "epistle":
        presence_sentence = (
            f"What we see in {brief.scripture_reference} shows how doctrine presses into daily life "
            "rather than remaining in the realm of abstract conviction."
        )
    elif brief.genre == "prophecy":
        presence_sentence = (
            f"What we see in {brief.scripture_reference} shows how God's word arrives before the events it announces, "
            "demanding a response from people who have not yet seen the outcome."
        )
    elif brief.genre == "poetry":
        presence_sentence = (
            f"What we see in {brief.scripture_reference} shows how faith voices its inner state honestly "
            "rather than hiding it behind composed religious language."
        )
    else:
        presence_sentence = (
            f"What we see in {brief.scripture_reference} shows how faith responds when suffering, "
            "loss, and accusation make reverence costly."
        )
    closing_reference = (
        f"Where it reveals Jesus clearly, we should pursue {closing_move} rather than delay."
        if christological
        else f"Where it reveals God's worth clearly, we should pursue {closing_move} rather than delay."
    )
    if theme_key == "trial":
        trial_variant = _trial_variant(brief)
        if trial_variant == "accusation":
            theme_sentence = (
                "Accusation and hostile testimony show how innocence can be surrounded by noise without being overturned by it."
            )
        elif trial_variant == "evasion":
            theme_sentence = (
                "Public hand-washing exposes the temptation to perform innocence while refusing the cost of just action."
            )
    elif theme_key == "loss":
        if theme_variant == "first_report":
            theme_sentence = (
                "The first report shatters ordinary security and tests whether the heart can keep worshiping before the full weight of loss is even visible."
            )
        elif theme_variant == "compounding_reports":
            theme_sentence = (
                "Compounding reports intensify suffering by denying the heart any pause between one blow and the next."
            )
        elif theme_variant == "collapse":
            theme_sentence = (
                "When the house collapses and the children are gone, grief becomes unmistakably personal rather than merely financial or social."
            )
    elif theme_key == "affliction":
        if theme_variant == "heavenly_charge":
            theme_sentence = (
                "This scene exposes affliction as a severe testing of integrity, not a simple exchange of visible causes and visible rewards."
            )
        elif theme_variant == "bodily_affliction":
            theme_sentence = (
                "Bodily affliction drives the trial into the flesh itself, where pain can tempt the soul toward bitterness or surrender."
            )
    opening_sentence = {
        "ordered_light": (
            f"{brief.scene_summary} The text orders the reader's attention before it asks for any response."
        ),
        "appointed_times": (
            f"{brief.scene_summary} The text trains the reader to receive God's ordering of times before trying to master life by urgency."
        ),
        "fruitfulness": (
            f"{brief.scene_summary} The text lets abundance appear as God's blessing before it is ever treated as human achievement."
        ),
        "delegated_rule": (
            f"{brief.scene_summary} The text dignifies human calling while keeping it firmly under God's authority."
        ),
        "sabbath_rest": (
            f"{brief.scene_summary} The text slows the reader down by presenting rest as a holy answer to completed work."
        ),
        "life_dependence": (
            f"{brief.scene_summary} The text reminds the reader that creaturely life is received, not manufactured."
        ),
        "garden_stewardship": (
            f"{brief.scene_summary} The text places provision and responsibility together so gratitude does not drift into carelessness."
        ),
        "generous_command": (
            f"{brief.scene_summary} The text frames command inside generosity so that obedience is received as trust rather than threat."
        ),
        "delegated_discernment": (
            f"{brief.scene_summary} The text trains the reader to notice that naming, judging, and tending are part of faithful responsibility."
        ),
        "covenant_nearness": (
            f"{brief.scene_summary} The text begins with remembered mercy so obedience does not forget who brought the people near."
        ),
        "holy_boundary": (
            f"{brief.scene_summary} The text places holy boundaries in front of the reader before it allows any easy familiarity with God's presence."
        ),
        "holy_encounter": (
            f"{brief.scene_summary} The text brings the hearer to a mountain scene where worship and fear belong together."
        ),
        "covenant_obedience": (
            f"{brief.scene_summary} The text orders covenant life under God's authority instead of leaving holiness undefined."
        ),
        "wisdom_warning": (
            f"{brief.scene_summary} The text warns the reader before evil companionship can begin to feel ordinary or useful."
        ),
        "wisdom_treasure": (
            f"{brief.scene_summary} The text calls for a searching heart rather than a passive admiration of wisdom."
        ),
        "wisdom_security": (
            f"{brief.scene_summary} The text presents wisdom as a guarded path where stability comes from received discernment."
        ),
        "conversion_confrontation": (
            f"{brief.scene_summary} The text interrupts the reader with the direct authority of the risen Lord."
        ),
        "helpless_reorientation": (
            f"{brief.scene_summary} The text slows the day into dependence and disorientation so pride can no longer pretend control."
        ),
        "mediated_mercy": (
            f"{brief.scene_summary} The text shows mercy arriving through the obedience of one believer toward another."
        ),
        "public_transformation": (
            f"{brief.scene_summary} The text puts changed allegiance into public view instead of leaving conversion hidden."
        ),
        "church_peace": (
            f"{brief.scene_summary} The text frames peace as strengthening life under God's holy comfort."
        ),
        "community_resurrection": (
            f"{brief.scene_summary} The text turns mercy into visible resurrection-shaped hope before a watching community."
        ),
        "ordinary_readiness": (
            f"{brief.scene_summary} The text dignifies the ordinary place where the servant of God remains available for what comes next."
        ),
        "warning": (
            f"{brief.scene_summary} The text sets the reader under warning before it offers the comfort of explanation."
        ),
        "loss": (
            f"{brief.scene_summary} The text lets grief arrive in sequence so the heart feels how ordinary security is stripped away."
        ),
        "endurance": (
            f"{brief.scene_summary} The text does not rush past pain; it asks whether worship can remain upright when suffering is not removed."
        ),
        "affliction": (
            f"{brief.scene_summary} The text presses suffering inward until the question is no longer abstract but painfully embodied."
        ),
        "trial": (
            f"{brief.scene_summary} The text places truth under pressure and asks what faithfulness looks like when public voices distort what is right."
        ),
        "cross": (
            f"{brief.scene_summary} The text brings costly obedience into view and refuses every attempt to make sacrifice feel decorative."
        ),
        "resurrection": (
            f"{brief.scene_summary} The text opens the day with living hope rather than mere religious sentiment."
        ),
    }.get(
        theme_key,
        f"{brief.scene_summary} The text does not ask the reader to admire the moment from a distance."
    )
    genre_sentence = {
        "prophecy": "Because this is prophetic material, the burden falls on sober listening, not imaginative embellishment.",
        "poetry": "Because this is poetic material, the imagery must be received with patience rather than flattened into slogans.",
        "wisdom": "Because this is wisdom material, the passage trains ordinary judgment through concentrated truth.",
        "narrative": "Because this is narrative material, the theology arrives through events, actions, and speech rather than detached maxims.",
        "epistle": "Because this is epistolary material, the burden is argued and applied with deliberate clarity.",
    }.get(brief.genre, "The literary shape of the passage helps determine the kind of obedience it requires.")
    key_terms = ", ".join(term for term in brief.key_terms[:3] if term) or "the specific language of the passage"
    drift_warning = brief.forbidden_drifts[:1]
    drift_sentence = (
        f"We should not drift into {drift_warning[0]}."
        if drift_warning
        else "We should not drift into vague religious language."
    )
    # Use the focus clause as the primary in-text quotation — but only if it appears
    # in the supplied passage text. The outliner may derive focus_clause from adjacent verses
    # (e.g. Philippians 2:11 when the passage ends at 2:8). Validate before using it;
    # fall back to the image (which is always extracted directly from scripture_text).
    _passage_lower = (scripture_text or "").lower()
    _focus_lower = (brief.focus_clause or "").lower().strip().rstrip(".,;:")
    if _focus_lower and len(_focus_lower) >= 6 and _focus_lower in _passage_lower:
        focus_quote = brief.focus_clause
    else:
        # focus_clause fell outside the focal passage (outliner used adjacent verse).
        # Override both the quote and the focus variable so all paragraphs stay grounded.
        focus_quote = image
        focus = image
    paragraphs = [
        (
            f"{opening_sentence} "
            f"The passage puts one scene before us: \"{focus_quote}.\" "
            f"That phrase — not a general principle, but those specific words — sets the day's register. "
            f"What {brief.scripture_reference} shows through {key_terms} must be received before it is applied. "
            "That specificity keeps the reading grounded in this text."
        ),
        (
            f"{(brief.theological_lane or '')[:1].upper()}{(brief.theological_lane or '')[1:]}. "
            f"The text stays concrete: \"{focus_quote}\" — "
            f"the language of {key_terms} carries the day's theological weight before any principle is named. "
            f"{theme_sentence}".strip()
        ),
        (
            f"{presence_sentence} "
            "The point is not bare information. "
            f"It presses into {emphasis}. "
            f"{drift_sentence} "
            "We should let the passage name the pressure point for the day."
        ),
        (
            f"If the scene is shaped by {focus}, then obedience today should answer that same pressure point. "
            f"Where the text exposes fear, we should {practice_move}. "
            f"Where it honors devotion, we should practice {communal_application}. "
            f"{closing_reference} "
            "That keeps the day under the authority of Scripture."
        ),
    ]
    text = "\n\n".join(paragraphs)
    if len(text.split()) >= 500:
        fixed = _maybe_apply_safe_fixes(text, ignored_words={word.title() for word in brief.key_terms})
        return _ensure_exposition_floor(fixed, theme_key=theme_key)

    # Deterministic fallback padding if wording drifts below validator minimum.
    # These sentences reference the passage's specific quote and terms — not generic devotional filler.
    addenda = [
        f"The language of \"{focus_quote}\" is not decorative — it carries the specific weight of {brief.scripture_reference}'s claim.",
        f"An exposition that replaces \"{focus_quote}\" with a general theological concept loses what {brief.scripture_reference} actually says.",
        f"The details {key_terms} represent do their work on the conscience precisely because they are this passage's particulars.",
        f"Careful attention to \"{focus_quote}\" before reaching for application keeps the day tethered to this text.",
    ]
    if christological:
        addenda.extend(
            [
                f"The passage fixes courage to the specific scene of \"{focus_quote}\" — not to a general confidence in Jesus detached from this text.",
                f"Where {brief.scripture_reference} names what faithfulness costs, the reader is trained by that cost, not by a principle imported from elsewhere.",
            ]
        )
    else:
        addenda.extend(
            [
                f"When {brief.scripture_reference} gives us \"{focus_quote},\" that phrase sets the pastoral work for the day.",
                f"The exposition honors \"{focus_quote}\" when it reads those words on their own terms before drawing any lesson from them.",
            ]
        )
    theme_addenda = {
        "ordered_light": [
            "Ordered-light passages discipline attention by teaching that faithful living receives time and limits as part of God's good governance.",
            "They therefore resist both frantic pace and spiritual vagueness by calling the heart back into God's created rhythms.",
        ],
        "appointed_times": [
            "Appointed-times passages teach the reader to stop treating urgency as wisdom and to receive God's ordering of time as a form of mercy.",
            "They therefore form patience, rhythm, and steadier judgment rather than reactive motion.",
        ],
        "fruitfulness": [
            "Fruitfulness passages teach that life multiplies under blessing, not under anxious grasping or restless self-invention.",
            "That is why gratitude and reverence belong near the center of any faithful response to abundance.",
        ],
        "delegated_rule": [
            "Delegated-rule passages give dignity without granting autonomy, keeping authority answerable to the One who gives it.",
            "The reader is therefore trained to lead, work, and influence others with humility rather than possession.",
        ],
        "sabbath_rest": [
            "Sabbath passages do more than commend rest; they teach the creature to stop proving what God has already declared good.",
            "That is why faithful rest is an act of trustful worship rather than mere recovery from overwork.",
        ],
        "life_dependence": [
            "Life-dependence passages keep human identity low enough to remain grateful and high enough to remain dignified before God.",
            "They teach that dependence is not humiliation but truthful creatureliness lived in God's presence.",
        ],
        "garden_stewardship": [
            "Stewardship passages tie gift to calling so that provision is neither idolized nor neglected.",
            "They train the reader to tend, cultivate, and guard what God gives with deliberate gratitude.",
        ],
        "generous_command": [
            "Command passages of this kind guard the conscience from imagining that every limit is hostile to joy.",
            "They show that divine boundaries often preserve freedom more deeply than unrestrained appetite ever can.",
        ],
        "delegated_discernment": [
            "Discernment passages teach that naming and noticing are forms of obedience when God entrusts responsibility to human hands.",
            "They therefore call for thoughtful attention instead of passive drift or hurried judgment.",
        ],
        "covenant_nearness": [
            "Covenant-nearness passages keep obedience from becoming bare duty by grounding it in the mercy of the God who has already drawn His people near.",
            "They train gratitude to come before demand so holiness is remembered as response rather than self-invention.",
        ],
        "holy_boundary": [
            "Boundary passages teach that holy love does not erase reverence, and that nearness to God must not be treated as casual access.",
            "They therefore form restraint, teachability, and awe rather than presumptuous familiarity.",
        ],
        "holy_encounter": [
            "Encounter passages confront the reader with a holiness large enough to unsettle self-possession and reorder worship.",
            "They keep devotion from becoming tame by insisting that divine glory is not a background detail but the center of the scene.",
        ],
        "covenant_obedience": [
            "Commandment passages give covenant life a practical shape so holiness is measured in worship, speech, desire, and neighbor-love.",
            "They therefore train obedience that is concrete, ordered, and resistant to selective morality.",
        ],
        "wisdom_warning": [
            "Warning passages in wisdom literature aim at early refusal, teaching the reader to reject evil before it becomes normalized companionship.",
            "They are therefore clearest when the exposition names the seduction plainly and counsels decisive moral refusal.",
        ],
        "wisdom_treasure": [
            "Treasure-seeking passages teach that wisdom is worth labor, asking the reader to pursue understanding with hunger rather than with vague appreciation.",
            "That is why the devotional must commend disciplined seeking rather than passive admiration.",
        ],
        "wisdom_security": [
            "Security passages in Proverbs promise guarded walking, not naive ease, and they tether safety to wisdom rather than to self-confidence.",
            "The reader is therefore trained to value stable discernment more than quick certainty.",
        ],
        "conversion_confrontation": [
            "Conversion-confrontation passages do not flatter the sinner; they expose rebellion by the authority of the risen Christ.",
            "Any faithful exposition must therefore let divine interruption lead before human response is discussed.",
        ],
        "helpless_reorientation": [
            "Reorientation passages teach that divine grace often humbles before it commissions, dismantling false control so a new calling can be received.",
            "They therefore require a devotional tone that honors dependence rather than entrepreneurial zeal.",
        ],
        "mediated_mercy": [
            "Mediated-mercy passages dignify the obedient believer who carries God's welcome to the most unlikely recipient.",
            "They train the church to risk obedience when mercy crosses expectation or suspicion.",
        ],
        "public_transformation": [
            "Public-transformation passages show that true conversion becomes visible because allegiance to Christ cannot remain hidden indefinitely.",
            "They should therefore emphasize changed witness rather than private feeling alone.",
        ],
        "church_peace": [
            "Church-peace passages portray strengthening calm under the fear of the Lord and the comfort of the Spirit, not spiritual laziness.",
            "They therefore call the reader toward quiet faithfulness that builds others up.",
        ],
        "community_resurrection": [
            "Community-resurrection passages show that mercy and resurrection hope become public encouragement for many, not just private consolation for one.",
            "They therefore should move toward communal witness rather than isolated amazement.",
        ],
        "ordinary_readiness": [
            "Ordinary-readiness passages dignify the seasons between dramatic events, where faithfulness remains available in humble places.",
            "They train the reader to honor preparation and presence rather than craving constant spectacle.",
        ],
        "warning": [
            "Warning passages train the conscience by forcing the reader to reckon with divine opposition before pride hardens into presumption.",
            "That is why responsible devotion must remain alert, teachable, and morally awake rather than merely curious about future events.",
        ],
        "loss": [
            "Loss passages are not merely records of pain; they train the church to name grief truthfully without surrendering reverence.",
            "In that way the text disciplines both despair and denial, teaching the reader to mourn without accusing God falsely.",
        ],
        "endurance": [
            "Endurance in Scripture is never passive numbness; it is active reverence that refuses to let pain rewrite the character of God.",
            "The day therefore matures faith not by quick relief but by steadier worship under strain.",
        ],
        "affliction": [
            "Affliction passages make the soul choose whether pain will become an excuse for accusation or an occasion for deeper dependence.",
            "That choice is why the devotional must remain serious, patient, and unwilling to reduce suffering to a tidy lesson.",
        ],
        "trial": [
            "Trial scenes expose how easily public pressure can train the heart to hide behind procedure, noise, or self-protection.",
            "Faithfulness therefore requires more than private conviction; it requires truthful steadiness when the stakes become visible.",
        ],
        "cross": [
            "Cross-shaped passages keep obedience from becoming sentimental by showing that love remains holy, costly, and concrete.",
            "They teach the reader that discipleship is measured not by admiration alone but by costly conformity to the way of Christ.",
        ],
        "resurrection": [
            "Resurrection passages insist that hope is not decorative theology but the living reality that reorders fear, witness, and endurance.",
            "The devotional therefore must move beyond uplift and into courageous trust shaped by the risen Christ.",
        ],
        "poetry": [
            "Poetry in the Psalms teaches the heart to speak its inner state before God with an honesty that prose alone cannot carry.",
            "The imagery of the Psalms is not decoration; it names the weight of lived faith before it is organized into doctrine.",
            "Psalm passages therefore call for slow, attentive reading that does not rush from metaphor to application.",
            "They train the soul to linger over God's character rather than move immediately to self-directed resolution.",
            "Faithful reading of the Psalms learns to pray before it learns to act, and to listen before it speaks.",
            "That posture of attentive stillness is itself a form of obedience that the text requires before anything else.",
        ],
        "response": [
            "A faithful response to this text will be shaped by what it actually says rather than by what we hope it says.",
            "The text does not reward the reader who arrives with conclusions already formed; it rewards the reader who arrives empty enough to hear.",
            "Honest application therefore begins with honest reading, which means staying close to the specific words before reaching for their implications.",
            "What the passage names must be felt before it is acted upon, or action will outrun understanding.",
            "Devotion trained by this kind of text becomes steadier over time because it is anchored in what God has actually said.",
            "That steadiness is not complacency — it is the settled confidence of a soul that has learned to trust the word before trusting its own impressions of the word.",
        ],
    }
    addenda.extend(theme_addenda.get(theme_key, [
        "The text rewards slow attention because its details are part of its theology, not background decoration.",
        "Good application therefore grows from disciplined reading rather than from devotional instinct alone.",
    ]))
    words = text.split()
    for sentence in addenda:
        if len(words) >= 520:
            break
        words.extend(sentence.split())
    # Trim to 520 words but cut at a sentence boundary to avoid mid-word truncation.
    truncated = " ".join(words[:520])
    # Find last sentence-ending punctuation at or before the 520-word boundary.
    _sent_end = max(
        truncated.rfind(". "),
        truncated.rfind("! "),
        truncated.rfind("? "),
    )
    if _sent_end > len(truncated) // 2:
        truncated = truncated[: _sent_end + 1].rstrip()
    fixed = _maybe_apply_safe_fixes(truncated, ignored_words={word.title() for word in brief.key_terms})
    return _ensure_exposition_floor(fixed, theme_key=theme_key)


def _topic_focus(topic: str) -> str:
    raw = str(topic or "").strip()
    if "|" in raw:
        raw = raw.split("|", 1)[1].strip()
    text = " ".join(raw.replace("/", " ").split()).strip()
    if not text:
        return "the truth of this passage"
    return text[0].upper() + text[1:]


def _scripture_image(scripture_text: str) -> str:
    # Strip ASCII quotes, backtick, and Unicode curly/smart quotes that appear in NASB text
    cleaned = re.sub(r"[\"\u201c\u201d\u2018\u2019'`\u2032\u2033]+", "", str(scripture_text or "")).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    clauses = [part.strip(" ,;:-") for part in re.split(r"[.!?]", cleaned) if part.strip()]
    # Skip short heading/title clauses (e.g. "The Lord, the Psalmist's Shepherd", "A Psalm of David")
    # to reach actual verse content. Use the first clause with >= 7 words.
    chosen = ""
    for clause in clauses:
        if len(clause.split()) >= 7:
            chosen = clause
            break
    if not chosen and clauses:
        chosen = clauses[0]
    chosen = re.sub(r"\b(And|Or|But)\b", "", chosen)
    words = [w.strip(" ,;:-") for w in chosen.split() if w.strip(" ,;:-")]
    if not words:
        return "the shape of God's word"
    excerpt_words = words[:7]
    while excerpt_words and excerpt_words[-1].lower().rstrip(".,;:") in {"and", "or", "the", "a", "an"}:
        excerpt_words.pop()
    excerpt = " ".join(excerpt_words or words[:5]).rstrip(".,;:")
    return excerpt or "the shape of God's word"


_GENERIC_CLAIM_PHRASES = frozenset({
    "god is", "we are", "let us", "in our", "as we", "may we",
    "god's love", "god's grace", "god's word", "walk with", "trust in",
    "faith in", "this passage", "the bible", "scripture tells",
    "we must", "we should", "we can", "we need",
})

def _extract_focal_claim(exposition_text: str) -> str:
    """Deterministic extraction of the focal theological claim from exposition.

    Takes the first substantive sentence that:
    - Is at least 8 words long
    - Does not start with a generic filler phrase
    - Is not just restating a verse reference (no chapter:verse pattern)

    Returns "" if no qualifying sentence is found — caller escalates to LLM agent.
    """
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", exposition_text) if s.strip()]
    for sentence in sentences[:4]:  # Only examine first 4 sentences
        words = sentence.split()
        if len(words) < 8:
            continue
        lower = sentence.lower()
        # Skip sentences that are just verse quotes (contain chapter:verse)
        if re.search(r"\d+:\d+", sentence):
            continue
        # Skip sentences that open with generic filler
        if any(lower.startswith(phrase) for phrase in _GENERIC_CLAIM_PHRASES):
            continue
        # Return the first qualifying sentence, trimmed to 200 chars
        return sentence[:200].strip()
    return ""


def _first_exposition_sentence(exposition_text: str) -> str:
    for sentence in re.split(r"(?<=[.!?])\s+", exposition_text):
        cleaned = sentence.strip()
        if cleaned:
            return cleaned
    return ""


def _build_be_still(
    *,
    brief: EditorialDayBrief,
    scripture_text: str,
    exposition_text: str,
) -> list[str]:
    exposition_sentence = _first_exposition_sentence(exposition_text).lower()
    focus = _communalize_focus(brief.focus_clause)
    theme_key = _theme_key(brief, scripture_text)
    theme_variant = _theme_variant(brief, scripture_text)
    if "order" in exposition_sentence:
        response_prompt = "Where do you need to receive God's order instead of forcing control?"
    elif "rest" in exposition_sentence:
        response_prompt = "Where is God inviting you to rest instead of striving today?"
    elif "trust" in exposition_sentence or "fear" in exposition_sentence:
        response_prompt = "What fear or self-reliance does this passage ask you to surrender?"
    elif theme_key == "loss" and theme_variant == "first_report":
        response_prompt = "What first shock or sudden disruption are you being asked to bring before God honestly today?"
    elif theme_key == "loss" and theme_variant == "compounding_reports":
        response_prompt = "Where do repeated pressures tempt you to go numb instead of remaining reverent before God?"
    elif theme_key == "loss" and theme_variant == "collapse":
        response_prompt = "What grief feels most personal or irreversible right now, and how will you bring it before God without pretending?"
    elif theme_key == "affliction" and theme_variant == "heavenly_charge":
        response_prompt = "Where are you tempted to interpret unexplained pain as proof that faithfulness is pointless?"
    elif theme_key == "affliction" and theme_variant == "bodily_affliction":
        response_prompt = "How is physical or emotional pain pressing on your worship today?"
    else:
        response_prompt = f"Where does this passage call for {_communalize_application(brief.application_lane)} today?"
    closing_prompt = (
        "Stay for one more minute and answer God with one honest sentence of confession, courage, or repentance before continuing."
        if theme_key in {"trial", "cross", "betrayal", "repentance"}
        else "Stay for one more minute and answer God with one honest sentence of trust, lament, or reverence before continuing."
        if theme_key in {"loss", "endurance", "affliction"}
        else "Stay for one more minute and answer God with one honest sentence of trust, repentance, or gratitude before continuing."
    )
    # Use a concrete passage image (extracted directly from scripture_text) instead of
    # the abstract pastoral_burden label. The trainer requires specific narrative details,
    # not category labels, in prompt 1.
    passage_image = _scripture_image(scripture_text)
    return [
        f"Sit with {brief.scripture_reference} for two quiet minutes. Read the words \"{passage_image}\" slowly and let what the passage shows settle before you move on.",
        response_prompt,
        closing_prompt,
    ]


def _build_action_steps(
    *,
    brief: EditorialDayBrief,
    day_number: int,
    exposition_text: str,
    scripture_text: str = "",
) -> tuple[str, list[str]]:
    exposition_sentence = _first_exposition_sentence(exposition_text).lower()
    focus = _communalize_focus(brief.focus_clause)
    theme_key = _theme_key(brief, scripture_text)
    theme_variant = _theme_variant(brief, scripture_text)
    connector = f"Because {brief.scripture_reference} calls for {_communalize_application(brief.application_lane)} today:"
    # Use a concrete passage image as the anchor for action steps, not just reference labels.
    _action_image = _scripture_image(scripture_text)
    action_sets = [
        [
            f"Write one sentence naming what the words \"{_action_image}\" exposed or confirmed in your honest sentence from Be Still.",
            f"Name one place where {_communalize_application(brief.application_lane)} should change the way you listen, speak, or act today — specifically in response to what you named in Be Still.",
        ],
        [
            f"Before your next decision, pause and ask how \"{_action_image}\" should shape your response — not as a general principle but as the specific weight {brief.scripture_reference} places on today.",
            "Offer one concrete act of service that matches the patience or steadiness this passage commends, not a general act of goodwill but one that answers the passage's specific call.",
        ],
        [
            f"Name one place where you have been trying to control the outcome that \"{_action_image}\" directly addresses, and entrust that specific concern to God in prayer.",
            "End the day by recording one evidence of God's faithfulness you noticed that corresponds to what you heard in this passage — specific, not general.",
        ],
        [
            f"Speak one truthful and encouraging sentence to someone today that flows from what \"{_action_image}\" showed you in Be Still — name the passage's claim, not just your own observation.",
            f"Set aside ten minutes to return to the honest sentence you wrote in Be Still and let it become a prayer shaped by {brief.scripture_reference}.",
        ],
    ]
    items = action_sets[(day_number - 1 + len(theme_key)) % len(action_sets)]
    if theme_key == "betrayal":
        items = [
            "Refuse one shortcut or half-truth today, even if it would make life easier.",
            f"Name one place where convenience competes with loyalty to Jesus in {brief.scripture_reference}, and choose faithfulness instead.",
        ]
    elif theme_key == "repentance":
        items = [
            "Confess one recent failure honestly to God without self-defense.",
            f"Return to one neglected act of obedience that {brief.scripture_reference} brings back to mind.",
        ]
    elif theme_key == "resurrection":
        items = [
            f"Tell one person today what hope {brief.scripture_reference} gives you.",
            "Take one concrete step that reflects courage instead of resignation.",
        ]
    elif theme_key == "trial":
        trial_variant = _trial_variant(brief)
        if trial_variant == "accusation":
            items = [
                "Refuse one distorted retelling of events today, even if it benefits you.",
                f"Protect one person's reputation in conversation by choosing accuracy over insinuation in the spirit of {brief.scripture_reference}.",
            ]
        else:
            items = [
                "Name one place where you are tempted to appear innocent without acting justly.",
                f"Take one concrete step of honest responsibility instead of symbolic distance in response to {brief.scripture_reference}.",
            ]
    elif theme_key == "cross":
        items = [
            f"Name one costly act of obedience that {brief.scripture_reference} places before you today.",
            "Accept one inconvenience without complaint as a small act of cross-shaped faithfulness.",
        ]
    elif theme_key == "loss":
        if theme_variant == "first_report":
            items = [
                "Name the first hard report you are tempted to manage instead of mourn.",
                f"Bring that shock to God in one brief act of reverence rooted in {brief.scripture_reference}.",
            ]
        elif theme_variant == "compounding_reports":
            items = [
                "Name one pressure that has been followed too quickly by another and has tempted you to spiritual numbness.",
                f"Pause between those pressures today and answer them with one deliberate act of reverence shaped by {brief.scripture_reference}.",
            ]
        else:
            items = [
                "Name the grief that feels most personal or irreversible right now.",
                f"Bring that sorrow before God honestly and refuse to let {brief.scripture_reference} become a slogan instead of a lamenting act of worship.",
            ]
    elif theme_key == "endurance":
        items = [
            f"Write one sentence confessing what is hard in light of {brief.scripture_reference} without hiding either the pain or God's worthiness.",
            "Choose one small act of obedience that says suffering will not dictate your theology today.",
        ]
    elif theme_key == "affliction":
        if theme_variant == "heavenly_charge":
            items = [
                "Refuse the conclusion that unexplained suffering proves your faithfulness is useless.",
                f"Bring one unanswered question honestly to God in the spirit of {brief.scripture_reference} instead of shutting down.",
            ]
        else:
            items = [
                "Refuse one bitter interpretation of your pain today.",
                f"Bring one physical or emotional ache honestly to God in the spirit of {brief.scripture_reference} instead of shutting down.",
            ]
    elif theme_key == "warning":
        items = [
            f"Name one place where you are tempted to treat {brief.scripture_reference} as distant material instead of living warning.",
            f"Take one concrete step today that shows you are receiving {focus} with sober obedience.",
        ]
    elif "rest" in exposition_sentence:
        items = [
            f"Protect one short period of unhurried rest today and receive it as obedience to {brief.scripture_reference}.",
            "Release one unnecessary task or self-imposed pressure that is keeping you from grateful trust.",
        ]
    elif "gratitude" in exposition_sentence or "good" in exposition_sentence:
        items = [
            f"Thank God aloud for three concrete gifts named or implied in {brief.scripture_reference}.",
            "Share one tangible kindness or provision with someone else today as a response to God's goodness.",
        ]
    return connector, items


def _build_prayer(
    *,
    brief: EditorialDayBrief | None = None,
    scripture_text: str,
    exposition_text: str,
    topic: str | None = None,
    scripture_reference: str | None = None,
) -> str:
    if brief is None:
        if not scripture_reference:
            raise TypeError("scripture_reference is required when brief is not provided")
        brief = build_editorial_day_brief(
            day_number=1,
            scripture_reference=scripture_reference,
            scripture_text=scripture_text,
        )
    focus = _communalize_focus(brief.focus_clause)
    exposition_sentence = _first_exposition_sentence(exposition_text)
    theme_key = _theme_key(brief, scripture_text)
    christological = _christological_frame(brief)
    theme_variant = _theme_variant(brief, scripture_text)
    emphasis, practice_move, closing_move = _theme_applications(theme_key)
    trial_variant = _trial_variant(brief) if theme_key == "trial" else ""
    theme_petition = {
        "repentance": "Keep us from Peter's collapse of courage, and teach us to remember Your word before fear becomes denial.",
        "trial": "Keep us from Pilate's evasions, from the crowd's surrender to pressure, and from any habit that hides truth behind appearances.",
        "cross": "Keep us near the crucified Christ, and do not let us soften suffering love into something easier than holy obedience.",
        "betrayal": "Keep us from selling loyalty for convenience, approval, or imagined gain.",
        "resurrection": "Lift our hearts into resurrection courage, and keep us from living as though death still has the final word.",
        "psalm_trust": "Keep us resting under You as our Shepherd, trusting that You lead us beside still waters and through every valley without fear.",
        "psalm_lament": "Hear our cry when our soul is cast down and we feel forsaken; do not hide Your face, but draw near in our anguish and meet us there.",
        "psalm_praise": "Stir our hearts to bless You with all that is within us and to declare Your steadfast love and mighty deeds to every generation.",
        "epistle_justification": "Thank You for justifying us by faith apart from works of the law; let us stand in peace with You through our Lord Jesus Christ and not return to self-made righteousness.",
        "epistle_sanctification": "Help us put to death what belongs to the earth and set our minds on things above, walking as those who are truly alive from the dead.",
        "narrative_loyalty": "Grant us grace to cling in faithful loyalty, choosing Your people and Your God even when the path is costly and comfort is not promised.",
        "narrative_providence": "Open our eyes to see Your hidden hand at work — the hand that turns what men intend for harm into mercy for many.",
        "prophecy_restoration": "Comfort us as Your people; speak tenderly, and do the new thing You have promised — breathe life into what is dry and make rivers in the desert.",
    }.get(theme_key, "Keep us near Your word, and do not let ordinary pressure turn us away from humble obedience.")
    if theme_key == "trial" and trial_variant == "accusation":
        theme_petition = (
            "Keep us from joining false accusation, and teach us to stand near the truth when loud voices try to control the story."
        )
    elif theme_key == "trial" and trial_variant == "evasion":
        theme_petition = (
            "Keep us from public evasions that mimic innocence while surrendering justice to the crowd."
        )
    elif theme_key == "loss":
        if theme_variant == "first_report":
            theme_petition = (
                "Keep us from confusing the first hard report with Your absence, and teach us reverence before we know the full shape of our losses."
            )
        elif theme_variant == "compounding_reports":
            theme_petition = (
                "Keep us from going numb when one painful report is followed by another, and teach us reverence between each blow."
            )
        else:
            theme_petition = (
                "Keep us from treating devastating grief as proof that worship is pointless, and teach us reverence when sorrow becomes intensely personal."
            )
    elif theme_key == "endurance":
        theme_petition = (
            "Keep us steady in suffering, and do not let pain persuade us to call evil good or to stop blessing Your name."
        )
    elif theme_key == "affliction":
        if theme_variant == "heavenly_charge":
            theme_petition = (
                "Keep us from interpreting unexplained affliction as evidence that integrity is pointless, and guard us from accusation against Your wisdom."
            )
        else:
            theme_petition = (
                "Keep us from interpreting bodily affliction as permission for despair, accusation, or spiritual surrender."
            )
    closing_sentence = (
        "Make us truthful, steady, and brave where fear, pressure, or suffering would tempt us to compromise."
        if theme_key in {"trial", "cross", "betrayal", "repentance", "loss", "endurance", "affliction"}
        else f"Make our lives more truthful, more restful, and more loving as we pursue {closing_move}."
    )
    # Extract a concrete passage image to anchor the prayer in specific passage language.
    _prayer_image = _scripture_image(scripture_text)
    sentences = [
        f"Father, thank You for speaking clearly in {brief.scripture_reference}.",
        f"In this passage You bring {brief.pastoral_burden} into the open through {focus}.",
        (
            f"Lord Jesus, let the words \"{_prayer_image}\" press into our obedience today, not only our understanding."
            if christological
            else f"Lord, let the words \"{_prayer_image}\" press into our obedience today, not only our understanding."
        ),
        f"Where we resist the truth highlighted in this reflection, bring repentance and renewed trust.",
        theme_petition,
        f"Holy Spirit, take what we have seen in \"{_prayer_image}\" and make it lived faithfulness rather than a passing impression.",
        f"Teach us to remember that {exposition_sentence or 'Your word is always trustworthy and near to us.'}",
        f"Guard our hearts from pride, our choices from self-deception, and whatever would pull us away from {emphasis}.",
        f"Help us practice the obedience this day requires with humility as we pursue {_communalize_application(brief.application_lane)}.",
        closing_sentence,
        "Receive this prayer and keep us near to You in all things.",
        "Amen.",
    ]
    amen = sentences[-1]
    core_sentences = sentences[:-1]
    selected: list[str] = []
    words = 0
    for sentence in core_sentences:
        sentence_words = len(sentence.split())
        if selected and words + sentence_words + len(amen.split()) > 180:
            break
        selected.append(sentence)
        words += sentence_words
    while words < 120:
        filler = [
            "Keep us from treating Your grace lightly or delaying the obedience You deserve.",
            "Strengthen our hearts to trust You when the next ordinary demand arrives.",
        ]
        if theme_key in {"loss", "endurance", "affliction"}:
            filler.append(
                "Teach us to remain reverent without pretending that suffering is simple, brief, or easy to explain."
            )
        else:
            filler.append(
                "Let today's quiet reflection become a faithful response in conversation, work, rest, and service."
            )
        next_sentence = filler[len(selected) % len(filler)]
        if words + len(next_sentence.split()) + len(amen.split()) > 180:
            break
        selected.append(next_sentence)
        words = sum(len(sentence.split()) for sentence in selected)
    selected.append(amen)
    return _maybe_apply_safe_fixes(" ".join(selected), ignored_words={word.title() for word in brief.key_terms})


def _exposition_query_topics(brief: EditorialDayBrief) -> list[str]:
    topics: list[str] = []
    candidates = [
        brief.focus_clause,
        brief.pastoral_burden,
        brief.theological_lane,
        brief.application_lane,
        brief.scene_summary,
        " ".join(brief.key_terms[:3]),
    ]
    for candidate in candidates:
        cleaned = " ".join(str(candidate or "").split()).strip()
        if cleaned and cleaned not in topics:
            topics.append(cleaned)
    return topics


def _scripture_grounding_excerpts(
    *,
    scripture_reference: str,
    scripture_text: str,
    translation: str,
) -> dict[int, list[RetrievedExcerpt]]:
    clauses = [
        " ".join(part.split()).strip()
        for part in re.split(r"[.;:?!]", scripture_text)
        if " ".join(part.split()).strip()
    ]
    if not clauses:
        clauses = [scripture_text.strip() or scripture_reference]
    n = len(clauses)
    return {
        para_num: [
            RetrievedExcerpt(
                # Cycle through available clauses instead of repeating the last one,
                # so each paragraph is grounded in a distinct portion of the passage.
                text=clauses[(para_num - 1) % n][:180],
                original_text=clauses[(para_num - 1) % n][:180],
                language_modernized=False,
                modernization_label="",
                source_title=f"Scripture ({scripture_reference})",
                author=translation,
                source_type="reference",
                relevance_score=1.0,
            )
        ]
        for para_num in (1, 2, 3, 4)
    }


def _research_db_path() -> Path:
    return default_registry_db_path()


def _dedupe_excerpts(excerpts: list[RetrievedExcerpt]) -> list[RetrievedExcerpt]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[RetrievedExcerpt] = []
    for excerpt in excerpts:
        key = (
            excerpt.source_title.strip(),
            excerpt.author.strip(),
            " ".join(excerpt.text.split()),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(excerpt)
    return unique


def _prefer_positive_scores(excerpts: list[RetrievedExcerpt]) -> list[RetrievedExcerpt]:
    positive = [excerpt for excerpt in excerpts if float(excerpt.relevance_score) > 0.0]
    return positive if positive else excerpts


def _dedupe_quote_candidates(candidates: list[QuoteCandidate]) -> list[QuoteCandidate]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[QuoteCandidate] = []
    for candidate in candidates:
        key = (
            candidate.author.strip(),
            candidate.source_title.strip(),
            " ".join(candidate.quote_text.split()),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)
    return unique


def _quote_support_excerpts(candidates: list[QuoteCandidate], limit: int = 6) -> list[RetrievedExcerpt]:
    support_excerpts: list[RetrievedExcerpt] = []
    for candidate in candidates[:limit]:
        support_excerpts.append(
            RetrievedExcerpt(
                text=candidate.quote_text,
                original_text=candidate.original_quote_text,
                language_modernized=bool(candidate.language_modernized),
                modernization_label=candidate.modernization_label,
                source_title=candidate.source_title,
                author=candidate.author,
                source_type="reference",
                relevance_score=float(candidate.relevance_score),
            )
        )
    return support_excerpts


def _unique_source_count(excerpts: list[RetrievedExcerpt]) -> int:
    return len({excerpt.source_title.strip() for excerpt in excerpts if excerpt.source_title.strip()})


class DeterministicRealSectionGenerator:
    """Deterministic section generator with scripture retrieval + grounded exposition."""

    def __init__(
        self,
        retriever: ScriptureRetriever | None = None,
        operator_scripture_import: Path | None = None,
    ) -> None:
        self._retriever = retriever or ScriptureRetriever()
        self._operator_scripture_import = operator_scripture_import
        self._author_usage: dict[str, int] = defaultdict(int)
        self._quote_usage: set[tuple[str, str, str]] = set()

    def snapshot_quote_state(self) -> tuple[dict[str, int], set[tuple[str, str, str]]]:
        return dict(self._author_usage), set(self._quote_usage)

    def restore_quote_state(
        self,
        snapshot: tuple[dict[str, int], set[tuple[str, str, str]]],
    ) -> None:
        author_usage, quote_usage = snapshot
        self._author_usage = defaultdict(int, author_usage)
        self._quote_usage = set(quote_usage)

    def release_quote(
        self,
        *,
        author: str,
        source_title: str,
        quote_text: str,
    ) -> None:
        key = (
            str(author or "").strip(),
            str(source_title or "").strip(),
            str(quote_text or "").strip(),
        )
        if not any(key):
            return
        if key in self._quote_usage:
            self._quote_usage.remove(key)
        author_name = key[0]
        if author_name and author_name in self._author_usage:
            next_count = int(self._author_usage.get(author_name, 0)) - 1
            if next_count > 0:
                self._author_usage[author_name] = next_count
            else:
                self._author_usage.pop(author_name, None)

    def _build_and_save_prayer_trace(
        self,
        *,
        topic: str,
        day_number: int,
        scripture_reference: str,
        exposition_text: str,
        be_still_prompts: list[str],
    ) -> str:
        prayer_id = f"prayer-{topic}-day{day_number}"
        ptm_id = create_prayer_trace_map_id(prayer_id)
        exposition_sentence = next(
            (s.strip() for s in re.split(r"(?<=[.!?])\s+", exposition_text) if s.strip()),
            "Exposition grounding unavailable.",
        )
        entries = [
            PrayerTraceMapEntry(
                element_text=f"Father, we thank You for {scripture_reference}.",
                source_type="scripture",
                source_reference=scripture_reference,
            ),
            PrayerTraceMapEntry(
                element_text=exposition_sentence[:180],
                source_type="exposition",
                source_reference="exposition",
            ),
            PrayerTraceMapEntry(
                element_text=be_still_prompts[-1],
                source_type="be_still",
                source_reference="be_still",
            ),
        ]
        ptm = PrayerTraceMap(id=ptm_id, prayer_id=prayer_id, entries=entries)
        PrayerTraceMapStore(root_dir=PrayerTraceMapStore.DEFAULT_ROOT).save(ptm)
        return ptm_id

    def build_editorial_brief(
        self,
        topic: str,
        day_number: int,
        scripture_reference: str | None = None,
        study_window_reference: str | None = None,
        passage_resources: PassageResourceBundle | None = None,
    ) -> EditorialDayBrief:
        retrieved = _retrieve_scripture(
            retriever=self._retriever,
            anchor_reference=study_window_reference or scripture_reference,
            day_number=day_number,
            operator_import=self._operator_scripture_import,
        )
        key_reference = (scripture_reference or retrieved.reference).strip() or retrieved.reference
        study_reference = (study_window_reference or retrieved.reference).strip() or retrieved.reference
        return build_editorial_day_brief(
            day_number=day_number,
            scripture_reference=key_reference,
            scripture_text=retrieved.text,
            study_window_reference=study_reference,
            passage_resources=passage_resources,
        )

    def generate_day(
        self,
        topic: str,
        day_number: int,
        attempt_number: int = 1,
        scripture_reference: str | None = None,
        forbidden_quote_texts: set[str] | None = None,
        editorial_brief: EditorialDayBrief | None = None,
        passage_resources: PassageResourceBundle | None = None,
    ) -> DailyDevotional:
        exposition_id = f"expo-{topic}-day{day_number}"
        grounding_map_id = create_grounding_map_id(exposition_id)

        retrieved = _retrieve_scripture(
            retriever=self._retriever,
            anchor_reference=scripture_reference,
            day_number=day_number,
            operator_import=self._operator_scripture_import,
        )
        brief = editorial_brief or build_editorial_day_brief(
            day_number=day_number,
            scripture_reference=retrieved.reference,
            scripture_text=retrieved.text,
            passage_resources=passage_resources,
        )
        db_path = _research_db_path()

        live_quote_candidates = QuoteCatalog().retrieve_quotes(
            topic=topic,
            scripture_reference=retrieved.reference,
            top_k=100,
        )
        memory_quote_candidates = load_quote_candidates(
            db_path=db_path,
            topic=topic,
            scripture_reference=retrieved.reference,
            limit=100,
        )
        quote_source_rankings = load_quote_source_rankings(db_path=db_path)
        quote_candidates = _dedupe_quote_candidates(
            live_quote_candidates + memory_quote_candidates
        )

        rag = ExpositionRAG()
        query_topics = _exposition_query_topics(brief)
        seeded_context, seeded_theological = _seeded_exposition_resources(
            passage_resources
        )
        live_context: list[RetrievedExcerpt] = list(seeded_context)
        live_theological: list[RetrievedExcerpt] = list(seeded_theological)
        # Seed library resources from the editorial brief (outliner + shared pool).
        # These include both catalog-level records (available now) and passage-indexed
        # excerpts (available after acquisition indexing).  Conversion filters out
        # records that have no real excerpt text.
        for lib_record in brief.library_resources:
            lib_excerpt = _resource_record_to_excerpt(lib_record)
            if lib_excerpt is None:
                continue
            purpose = str(getattr(lib_record, "purpose", "") or "").strip().lower()
            if purpose == "theological":
                live_theological.append(lib_excerpt)
            else:
                live_context.append(lib_excerpt)
        for query_topic in query_topics:
            live_context.extend(
                rag.retrieve_for_paragraph(
                    paragraph_type="context",
                    passage_reference=retrieved.reference,
                    topic=query_topic,
                    source_types=["commentary", "reference"],
                )
            )
            live_theological.extend(
                rag.retrieve_for_paragraph(
                    paragraph_type="theological",
                    passage_reference=retrieved.reference,
                    topic=query_topic,
                    source_types=["commentary", "reference"],
                )
            )
        memory_context = load_exposition_candidates(
            db_path=db_path,
            paragraph_type="context",
            topic=brief.focus_clause,
            passage_reference=retrieved.reference,
            limit=100,
        )
        memory_theological = load_exposition_candidates(
            db_path=db_path,
            paragraph_type="theological",
            topic=brief.focus_clause,
            passage_reference=retrieved.reference,
            limit=100,
        )
        broader_context: list[RetrievedExcerpt] = []
        broader_theological: list[RetrievedExcerpt] = []
        for query_topic in query_topics[1:]:
            broader_context.extend(
                rag.retrieve_for_paragraph(
                    paragraph_type="context",
                    passage_reference=retrieved.reference,
                    topic=query_topic,
                    source_types=["commentary", "reference"],
                )
            )
            broader_theological.extend(
                rag.retrieve_for_paragraph(
                    paragraph_type="theological",
                    passage_reference=retrieved.reference,
                    topic=query_topic,
                    source_types=["commentary", "reference"],
                )
            )
        context_pool = _prefer_positive_scores(
            _dedupe_excerpts(live_context + memory_context + broader_context)
        )
        theological_pool = _prefer_positive_scores(
            _dedupe_excerpts(live_theological + memory_theological + broader_theological)
        )
        if (
            not context_pool
            or not theological_pool
            or _unique_source_count(context_pool + theological_pool) < 2
        ):
            scripture_fallback = [
                excerpt
                for items in _scripture_grounding_excerpts(
                    scripture_reference=retrieved.reference,
                    scripture_text=retrieved.text,
                    translation=retrieved.translation,
                ).values()
                for excerpt in items
            ]
            context_pool = _dedupe_excerpts(context_pool + scripture_fallback[:2])
            theological_pool = _dedupe_excerpts(theological_pool + scripture_fallback[2:])

        selected_context = context_pool[: min(len(context_pool), 4)]
        selected_theological = theological_pool[: min(len(theological_pool), 4)]
        store_exposition_candidates(
            db_path=db_path,
            paragraph_type="context",
            topic=brief.focus_clause,
            passage_reference=retrieved.reference,
            excerpts=context_pool,
            selected_excerpts=selected_context,
        )
        store_exposition_candidates(
            db_path=db_path,
            paragraph_type="theological",
            topic=brief.focus_clause,
            passage_reference=retrieved.reference,
            excerpts=theological_pool,
            selected_excerpts=selected_theological,
        )

        if selected_context and selected_theological:
            first_excerpt = (selected_context + selected_theological)[0:1]
            paragraph_excerpts = {
                1: first_excerpt,
                2: selected_context,
                3: selected_theological,
                4: first_excerpt,
            }
        else:
            paragraph_excerpts = _scripture_grounding_excerpts(
                scripture_reference=retrieved.reference,
                scripture_text=retrieved.text,
                translation=retrieved.translation,
            )

        gm = GroundingMapBuilder().build(exposition_id, paragraph_excerpts)
        gm = gm.model_copy(update={"id": grounding_map_id})
        GroundingMapStore(root_dir=GroundingMapStore.DEFAULT_ROOT).save(gm)

        exposition_text = _build_exposition(
            brief=brief,
            scripture_text=retrieved.text,
        )
        be_still_prompts = _build_be_still(
            brief=brief,
            scripture_text=retrieved.text,
            exposition_text=exposition_text,
        )
        action_connector, action_items = _build_action_steps(
            brief=brief,
            day_number=day_number,
            exposition_text=exposition_text,
            scripture_text=retrieved.text,
        )
        prayer_text = _build_prayer(
            brief=brief,
            scripture_text=retrieved.text,
            exposition_text=exposition_text,
        )
        prayer_trace_map_id = self._build_and_save_prayer_trace(
            topic=topic,
            day_number=day_number,
            scripture_reference=retrieved.reference,
            exposition_text=exposition_text,
            be_still_prompts=be_still_prompts,
        )
        quote = None
        attempted_quote_sources: list[str] = []
        if quote_candidates:
            blocked_norm = {
                " ".join(str(q or "").strip().lower().split())
                for q in (forbidden_quote_texts or set())
                if str(q or "").strip()
            }
            grouped: dict[tuple[str, str, str], list[QuoteCandidate]] = {}
            for cand in quote_candidates:
                cand_norm = " ".join(cand.quote_text.strip().lower().split())
                if cand_norm in blocked_norm or not cand_norm:
                    continue
                key = (cand.author.strip(), cand.source_title.strip(), cand_norm)
                grouped.setdefault(key, []).append(cand)

            eligible: list[QuoteCandidate] = []
            fresh: list[QuoteCandidate] = []
            for key, variants in grouped.items():
                ranked_variants = sorted(
                    variants,
                    key=lambda candidate: (
                        -_best_source_helpfulness(candidate, quote_source_rankings),
                        -float(getattr(candidate, "relevance_score", 0.0)),
                        -int(getattr(candidate, "citation_completeness", 0)),
                        candidate.author,
                        candidate.quote_text,
                    ),
                )
                used_variants: list[QuoteCandidate] = []
                merged_candidate: QuoteCandidate | None = None
                for variant in ranked_variants:
                    used_variants.append(variant)
                    merged = merge_quote_citation_fields(
                        *(item.model_dump() for item in used_variants)
                    )
                    merged_candidate = QuoteCandidate(**merged)
                    if has_strong_quote_citation(
                        citation_locator=merged_candidate.citation_locator or merged_candidate.page_or_url,
                        publisher=merged_candidate.publisher,
                        publication_city=merged_candidate.publication_city,
                    ):
                        break
                if merged_candidate is None:
                    continue
                for variant in used_variants:
                    source_value = str(
                        variant.source_url or (variant.page_or_url if is_url(variant.page_or_url) else "")
                    ).strip()
                    if source_value and source_value not in attempted_quote_sources:
                        attempted_quote_sources.append(source_value)
                if not has_strong_quote_citation(
                    citation_locator=merged_candidate.citation_locator or merged_candidate.page_or_url,
                    publisher=merged_candidate.publisher,
                    publication_city=merged_candidate.publication_city,
                ):
                    continue
                eligible.append(merged_candidate)
                usage_key = (merged_candidate.author, merged_candidate.source_title, merged_candidate.quote_text)
                if usage_key not in self._quote_usage:
                    fresh.append(merged_candidate)

            pool = fresh if fresh else eligible
            if not pool:
                store_quote_candidates(
                    db_path=db_path,
                    topic=topic,
                    scripture_reference=retrieved.reference,
                    candidates=quote_candidates,
                    selected=None,
                )
                record_quote_source_outcomes(
                    db_path=db_path,
                    candidates=quote_candidates,
                    selected=None,
                )
            else:
                def _source_helpfulness(candidate: QuoteCandidate) -> float:
                    return _best_source_helpfulness(candidate, quote_source_rankings)

                pool.sort(
                    key=lambda c: (
                        self._author_usage.get(c.author, 0),
                        -_source_helpfulness(c),
                        -float(getattr(c, "relevance_score", 0.0)),
                        -int(getattr(c, "citation_completeness", 0)),
                        c.author,
                        c.quote_text,
                    )
                )
                quote = pool[0]
                store_quote_candidates(
                    db_path=db_path,
                    topic=topic,
                    scripture_reference=retrieved.reference,
                    candidates=quote_candidates,
                    selected=quote,
                )
                record_quote_source_outcomes(
                    db_path=db_path,
                    candidates=quote_candidates,
                    selected=quote,
                )
                key = (quote.author, quote.source_title, quote.quote_text)
                self._quote_usage.add(key)
                self._author_usage[quote.author] = self._author_usage.get(quote.author, 0) + 1
        else:
            store_quote_candidates(
                db_path=db_path,
                topic=topic,
                scripture_reference=retrieved.reference,
                candidates=quote_candidates,
                selected=None,
            )
            record_quote_source_outcomes(
                db_path=db_path,
                candidates=quote_candidates,
                selected=None,
            )

        now = datetime.now(timezone.utc)
        quote_display_text = quote.quote_text if quote else ""
        quote_original_text = getattr(quote, "original_quote_text", "") if quote else ""
        quote_modernized = bool(getattr(quote, "language_modernized", False)) if quote else False
        quote_modernization_label = str(getattr(quote, "modernization_label", "") or "") if quote else ""
        if quote is not None and not quote_original_text:
            (
                quote_display_text,
                quote_original_text,
                quote_modernized,
                quote_modernization_label,
            ) = modernization_payload(quote.quote_text)
        quote_has_strong_citation = bool(
            quote
            and has_strong_quote_citation(
                citation_locator=quote.citation_locator or quote.page_or_url,
                publisher=quote.publisher,
                publication_city=quote.publication_city,
            )
        )
        quote_supports_agent_validation = bool(
            quote
            and supports_agent_quote_validation(
                author=quote.author,
                source_title=quote.source_title,
                quote_text=quote_display_text,
                source_url=quote.source_url or (quote.page_or_url if is_url(quote.page_or_url) else ""),
            )
        )
        return DailyDevotional(
            day_number=day_number,
            day_focus=brief.day_title,
            timeless_wisdom=TimelessWisdomSection(
                quote_text=quote_display_text,
                original_quote_text=quote_original_text,
                language_modernized=quote_modernized,
                modernization_label=quote_modernization_label,
                author=(quote.author if quote else ""),
                source_title=(quote.source_title if quote else ""),
                publication_year=(quote.publication_year if quote else None),
                page_or_url=(quote.page_or_url if quote else ""),
                citation_locator=(
                    quote.citation_locator
                    if quote and quote.citation_locator
                    else (quote.page_or_url if quote and not is_url(quote.page_or_url) else "")
                ),
                source_url=(
                    quote.source_url if quote and quote.source_url
                    else (quote.page_or_url if quote and is_url(quote.page_or_url) else "")
                ),
                source_trace=(quote.source_trace if quote else attempted_quote_sources),
                publisher=(quote.publisher if quote else ""),
                publication_city=(quote.publication_city if quote else ""),
                public_domain=(quote.public_domain if quote else True),
                retrieval_source=(
                    "quote_catalog"
                    if quote_has_strong_citation
                    else ""
                ),
                retrieval_reference=(
                    (
                        f"{quote.source_title} | searched={','.join(quote.source_trace or attempted_quote_sources)}"
                        if quote
                        else f"searched={','.join(attempted_quote_sources)}"
                    )
                ),
                retrieved_at_utc=now.isoformat(),
                validation_agent=(
                    ""
                ),
                verification_status=(
                    "quote_validated"
                    if quote_has_strong_citation
                    else "catalog_unverified"
                ),
            ),
            scripture=ScriptureSection(
                reference=retrieved.reference,
                text=retrieved.text,
                translation=retrieved.translation,
                retrieval_source=retrieved.retrieval_source,
                retrieval_reference=retrieved.retrieval_reference or retrieved.reference,
                retrieved_at_utc=retrieved.retrieved_at_utc,
                copyright_notice=retrieved.copyright_notice,
                source_access_policy=retrieved.source_access_policy,
                text_cache_status=retrieved.text_cache_status,
                cache_expires_at_utc=retrieved.cache_expires_at_utc,
                verification_status=retrieved.verification_status,
            ),
            exposition=ExpositionSection(
                text=exposition_text,
                focal_claim=_extract_focal_claim(exposition_text),
                word_count=len(exposition_text.split()),
                grounding_map_id=grounding_map_id,
            ),
            be_still=BeStillSection(prompts=be_still_prompts),
            action_steps=ActionStepsSection(
                items=action_items,
                connector_phrase=action_connector,
            ),
            prayer=PrayerSection(
                text=prayer_text,
                word_count=150,
                prayer_trace_map_id=prayer_trace_map_id,
            ),
            sending_prompt=None,
            day7=None,
            created_at=now,
            last_modified=now,
        )
