"""index_source_texts.py — Index library source.txt files into the excerpt_catalog SQLite table.

Acquisition lifecycle: locate → **index** → card → verify → shelved.
This script implements the index step.

For each resource with a source.txt:
  1. Read and clean the text
  2. Split into ~300-word chunks at paragraph boundaries
  3. Extract scripture references from each chunk
  4. Classify paragraph_type (context vs. theological)
  5. Insert into excerpt_catalog with passage_reference tagged

Special handling:
  - Metropolitan Tabernacle Pulpit: parses TOC to pre-tag each sermon by scripture reference
  - All texts: OCR quality filtering rejects garbage chunks
"""

from __future__ import annotations

import re
import sqlite3
import sys
from pathlib import Path
from typing import Iterator

from src.persistence.paths import default_registry_db_path

REPO_ROOT = Path(__file__).resolve().parents[2]
LIBRARY_DIR = REPO_ROOT / "data" / "library" / "resources"
DB_PATH = default_registry_db_path()

# ---------------------------------------------------------------------------
# Book name → max chapters (for reference validation)
# ---------------------------------------------------------------------------

BOOK_MAX_CHAPTERS: dict[str, int] = {
    "Genesis": 50, "Exodus": 40, "Leviticus": 27, "Numbers": 36,
    "Deuteronomy": 34, "Joshua": 24, "Judges": 21, "Ruth": 4,
    "1 Samuel": 31, "2 Samuel": 24, "1 Kings": 22, "2 Kings": 25,
    "1 Chronicles": 29, "2 Chronicles": 36, "Ezra": 10, "Nehemiah": 13,
    "Esther": 10, "Job": 42, "Psalms": 150, "Proverbs": 31,
    "Ecclesiastes": 12, "Song of Solomon": 8, "Isaiah": 66,
    "Jeremiah": 52, "Lamentations": 5, "Ezekiel": 48, "Daniel": 12,
    "Hosea": 14, "Joel": 3, "Amos": 9, "Obadiah": 1, "Jonah": 4,
    "Micah": 7, "Nahum": 3, "Habakkuk": 3, "Zephaniah": 3,
    "Haggai": 2, "Zechariah": 14, "Malachi": 4,
    "Matthew": 28, "Mark": 16, "Luke": 24, "John": 21, "Acts": 28,
    "Romans": 16, "1 Corinthians": 16, "2 Corinthians": 13,
    "Galatians": 6, "Ephesians": 6, "Philippians": 4, "Colossians": 4,
    "1 Thessalonians": 5, "2 Thessalonians": 3,
    "1 Timothy": 6, "2 Timothy": 4, "Titus": 3, "Philemon": 1,
    "Hebrews": 13, "James": 5, "1 Peter": 5, "2 Peter": 3,
    "1 John": 5, "2 John": 1, "3 John": 1, "Jude": 1,
    "Revelation": 22,
}

# Abbreviation → canonical book name
ABBREV: dict[str, str] = {
    "gen": "Genesis", "exod": "Exodus", "ex": "Exodus",
    "lev": "Leviticus", "num": "Numbers", "deut": "Deuteronomy",
    "josh": "Joshua", "judg": "Judges",
    "1 sam": "1 Samuel", "2 sam": "2 Samuel",
    "1 ki": "1 Kings", "2 ki": "2 Kings",
    "1 chr": "1 Chronicles", "2 chr": "2 Chronicles",
    "neh": "Nehemiah", "esth": "Esther",
    "ps": "Psalms", "psa": "Psalms", "psalm": "Psalms",
    "prov": "Proverbs", "eccl": "Ecclesiastes",
    "song": "Song of Solomon", "cant": "Song of Solomon",
    "isa": "Isaiah", "jer": "Jeremiah", "lam": "Lamentations",
    "ezek": "Ezekiel", "dan": "Daniel",
    "hos": "Hosea", "obad": "Obadiah", "jon": "Jonah",
    "mic": "Micah", "nah": "Nahum", "hab": "Habakkuk",
    "zeph": "Zephaniah", "hag": "Haggai", "zech": "Zechariah",
    "mal": "Malachi",
    "matt": "Matthew", "mat": "Matthew", "mk": "Mark",
    "lk": "Luke", "jn": "John",
    "rom": "Romans",
    "1 cor": "1 Corinthians", "2 cor": "2 Corinthians",
    "gal": "Galatians", "eph": "Ephesians",
    "phil": "Philippians", "col": "Colossians",
    "1 thess": "1 Thessalonians", "2 thess": "2 Thessalonians",
    "1 tim": "1 Timothy", "2 tim": "2 Timothy",
    "tit": "Titus", "philem": "Philemon", "phlm": "Philemon",
    "heb": "Hebrews", "jas": "James", "jas.": "James",
    "1 pet": "1 Peter", "2 pet": "2 Peter",
    "1 john": "1 John", "2 john": "2 John", "3 john": "3 John",
    "rev": "Revelation",
}


def normalize_book(raw: str) -> str:
    key = raw.strip().lower().rstrip(".")
    return ABBREV.get(key, raw.strip())


# ---------------------------------------------------------------------------
# Scripture reference regex
# Handles: "John 3:16", "Phil. 2:1", "1 Cor. 13:4", "Ps. 23:1"
# ---------------------------------------------------------------------------

_NUMBERED = r"(?:1|2|3)\s*"
_BOOKS = (
    rf"{_NUMBERED}(?:Samuel|Kings|Chronicles|Corinthians|Thessalonians|Timothy|Peter|John)"
    r"|Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth"
    r"|Nehemiah|Esther|Job|Psalms?|Proverbs|Ecclesiastes"
    r"|(?:Song\s+of\s+(?:Solomon|Songs))"
    r"|Isaiah|Jeremiah|Lamentations|Ezekiel|Daniel"
    r"|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|Habakkuk"
    r"|Zephaniah|Haggai|Zechariah|Malachi"
    r"|Matthew|Mark|Luke|John|Acts|Romans"
    r"|Galatians|Ephesians|Philippians|Colossians"
    r"|Titus|Philemon|Hebrews|James|Jude|Revelation"
    # abbreviations
    r"|(?:1|2)\s*(?:Cor|Thess|Tim|Pet|Jn)\."
    r"|(?:1|2)\s*Cor(?:inthians)?"
    r"|Phil(?:ippians)?\.?"
    r"|Col(?:ossians)?\.?"
    r"|Rom(?:ans)?\.?"
    r"|Matt?\.?"
    r"|Mk\.?"
    r"|Lk\.?"
    r"|Jn\.?"
    r"|Acts?"
    r"|Heb(?:rews)?\.?"
    r"|Gal(?:atians)?\.?"
    r"|Eph(?:esians)?\.?"
    r"|Jas\.?"
    r"|Rev(?:elation)?\.?"
    r"|Pss?\.?"
    r"|Prov\.?"
    r"|Gen\.?"
    r"|Exod?\.?"
    r"|Deut\.?"
    r"|Lev\.?"
    r"|Num\.?"
    r"|Isa\.?"
    r"|Jer\.?"
    r"|Ezek?\.?"
    r"|Dan\.?"
    r"|Zech\.?"
    r"|Mal\.?"
)

SCRIPTURE_RE = re.compile(
    rf"\b({_BOOKS})\.?\s+(\d{{1,3}})(?:[:.]\s*(\d{{1,3}})(?:\s*[-–]\s*(\d{{1,3}}))?)?",
    re.IGNORECASE,
)


def _validate_ref(book_raw: str, chapter: int, verse: int | None = None) -> str | None:
    """Return normalized 'Book chapter:verse' if valid, else None."""
    book = normalize_book(book_raw)
    # Try to look up exact or title-cased book
    max_ch = BOOK_MAX_CHAPTERS.get(book) or BOOK_MAX_CHAPTERS.get(book.title())
    if max_ch is None:
        # Try stripping trailing dot and re-normalizing
        for key, val in BOOK_MAX_CHAPTERS.items():
            if key.lower() == book.lower():
                book = key
                max_ch = val
                break
    if max_ch is None:
        return None
    if chapter < 1 or chapter > max_ch:
        return None
    if verse is not None:
        if verse < 1 or verse > 200:  # no chapter has >200 verses
            return None
        return f"{book} {chapter}:{verse}"
    return f"{book} {chapter}"


def extract_refs(text: str) -> list[str]:
    """Return validated normalised scripture references from text, most prominent first."""
    refs: list[str] = []
    seen: set[str] = set()
    for m in SCRIPTURE_RE.finditer(text):
        book_raw = m.group(1)
        try:
            chapter = int(m.group(2))
            verse = int(m.group(3)) if m.group(3) else None
        except (TypeError, ValueError):
            continue
        ref = _validate_ref(book_raw, chapter, verse)
        if ref and ref not in seen:
            seen.add(ref)
            refs.append(ref)
    return refs


# ---------------------------------------------------------------------------
# Text quality filter
# ---------------------------------------------------------------------------

def _non_ascii_ratio(text: str) -> float:
    if not text:
        return 1.0
    return sum(1 for c in text if ord(c) > 127) / len(text)


def _has_ocr_artifacts(text: str) -> bool:
    """Detect common OCR garbage patterns."""
    # Many isolated single/double chars separated by spaces
    isolated = re.findall(r"(?<!\w)[A-Za-z]{1,2}(?!\w)", text)
    if len(isolated) > len(text.split()) * 0.5:
        return True
    # Long runs of dashes or special chars
    if re.search(r"[-—–]{5,}", text):
        return True
    # Ratio of non-space punctuation
    punct = sum(1 for c in text if c in "—–ͤꝓͥ›‹")
    if punct > len(text) * 0.02:
        return True
    return False


def is_quality(text: str) -> bool:
    if len(text.split()) < 50:
        return False
    if _non_ascii_ratio(text) > 0.03:
        return False
    if _has_ocr_artifacts(text):
        return False
    return True


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def chunks(text: str, target_words: int = 300) -> Iterator[str]:
    """Yield paragraph-boundary chunks of ~target_words words."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    bucket: list[str] = []
    bucket_words = 0
    for para in paras:
        wc = len(para.split())
        if bucket_words + wc > target_words and bucket:
            yield " ".join(bucket)
            bucket = [para]
            bucket_words = wc
        else:
            bucket.append(para)
            bucket_words += wc
    if bucket:
        yield " ".join(bucket)


# ---------------------------------------------------------------------------
# Paragraph type classifier
# ---------------------------------------------------------------------------

_THEOLOGICAL_WORDS = {
    "grace", "justification", "sanctification", "atonement", "covenant",
    "election", "sovereignty", "predestination", "regeneration", "imputation",
    "propitiation", "reconciliation", "righteousness", "holiness", "repentance",
    "faith", "salvation", "redemption", "forgiveness", "wrath", "mercy",
    "adoption", "perseverance", "glorification", "substitution", "intercession",
    "sin", "sinner", "condemned", "judgment", "resurrection", "atone",
}


def paragraph_type(text: str) -> str:
    lower = text.lower()
    hits = sum(1 for w in _THEOLOGICAL_WORDS if w in lower)
    return "theological" if hits >= 2 else "context"


# ---------------------------------------------------------------------------
# Metropolitan Tabernacle Pulpit: TOC-based sermon tagging
# ---------------------------------------------------------------------------

# TOC line: "348 Consolation in Christ — Phil. 2:1  1"
# or:       "354 A Sermon ... — Col. 4:2  114"
_MET_TAB_TOC_RE = re.compile(
    r"^\s*(\d{3,4})\s+[^—–\-]{3,80}[-–—]\s*(.+?)\s+\d{1,4}\s*$",
    re.MULTILINE,
)


def _parse_met_tab_toc(text: str) -> dict[str, str]:
    """Build {sermon_number: normalised_ref} from TOC lines."""
    mapping: dict[str, str] = {}
    # TOC is in the first ~300 lines
    toc_text = "\n".join(text.splitlines()[:400])
    for m in _MET_TAB_TOC_RE.finditer(toc_text):
        num = m.group(1)
        raw_ref = m.group(2).strip()
        refs = extract_refs(raw_ref)
        if refs:
            mapping[num] = refs[0]
    return mapping


# Find a sermon header like "348 Title\n" or "SERMON NO. 348"
_SERMON_NUM_RE = re.compile(r"\b(\d{3,4})\b")


def _chunk_sermon_ref(toc_map: dict[str, str], chunk_text: str) -> str:
    """Find sermon number in chunk and return its TOC-mapped ref."""
    for m in _SERMON_NUM_RE.finditer(chunk_text):
        ref = toc_map.get(m.group(1))
        if ref:
            return ref
    return ""


# ---------------------------------------------------------------------------
# Resource config
# ---------------------------------------------------------------------------

RESOURCES: list[dict] = [
    {
        "slug": "the-sovereignty-of-god",
        "source_title": "The Sovereignty of God",
        "author": "Arthur W. Pink",
        "source_type": "commentary",
        "skip_header_lines": 50,
    },
    {
        "slug": "metropolitan-tabernacle-pulpit",
        "source_title": "Metropolitan Tabernacle Pulpit",
        "author": "Charles Spurgeon",
        "source_type": "commentary",
        "skip_header_lines": 40,
        "is_met_tab": True,
    },
    {
        "slug": "institutes-of-the-christian-religion",
        "source_title": "Institutes of the Christian Religion",
        "author": "John Calvin",
        "source_type": "commentary",
        "skip_header_lines": 80,
    },
    {
        "slug": "works-of-jonathan-edwards",
        "source_title": "The Works of Jonathan Edwards",
        "author": "Jonathan Edwards",
        "source_type": "commentary",
        "skip_header_lines": 100,
    },
    {
        "slug": "the-bruised-reed",
        "source_title": "The Bruised Reed",
        "author": "Richard Sibbes",
        "source_type": "commentary",
        "skip_header_lines": 120,
    },
    {
        "slug": "letters-of-samuel-rutherford",
        "source_title": "Letters of Samuel Rutherford",
        "author": "Samuel Rutherford",
        "source_type": "commentary",
        "skip_header_lines": 60,
    },
    {
        "slug": "sermons-and-letters",
        "source_title": "Sermons and Letters",
        "author": "George Whitefield",
        "source_type": "commentary",
        "skip_header_lines": 60,
    },
    {
        "slug": "the-doctrine-of-repentance",
        "source_title": "The Doctrine of Repentance",
        "author": "Thomas Watson",
        "source_type": "commentary",
        "skip_header_lines": 50,
    },
    {
        "slug": "table-talk",
        "source_title": "Table Talk",
        "author": "Martin Luther",
        "source_type": "commentary",
        "skip_header_lines": 50,
    },
    {
        "slug": "sermons-and-tracts",
        "source_title": "Sermons and Tracts",
        "author": "Thomas Chalmers",
        "source_type": "commentary",
        "skip_header_lines": 50,
    },
    {
        "slug": "journals-of-george-whitefield",
        "source_title": "Journals of George Whitefield",
        "author": "George Whitefield",
        "source_type": "commentary",
        "skip_header_lines": 60,
    },
    {
        "slug": "the-pulpit-commentary",
        "source_title": "The Pulpit Commentary",
        "author": "H.D.M. Spence and Joseph Exell",
        "source_type": "commentary",
        "skip_header_lines": 80,
    },
    {
        "slug": "matthew-henry-s-commentary-on-the-whole-bible",
        "source_title": "Matthew Henry's Commentary on the Whole Bible",
        "author": "Matthew Henry",
        "source_type": "commentary",
        "skip_header_lines": 60,
    },
    {
        "slug": "keil-delitzsch-ruth",
        "source_title": "Keil and Delitzsch Commentary: Joshua, Judges, Ruth",
        "author": "C.F. Keil and F. Delitzsch",
        "source_type": "commentary",
        "skip_header_lines": 80,
    },
    {
        "slug": "pulpit-commentary-ruth",
        "source_title": "The Pulpit Commentary: Judges and Ruth",
        "author": "H.D.M. Spence and Joseph Exell",
        "source_type": "commentary",
        "skip_header_lines": 80,
    },
]

# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS excerpt_catalog (
          text TEXT NOT NULL,
          source_title TEXT NOT NULL,
          author TEXT NOT NULL,
          source_type TEXT NOT NULL,
          paragraph_type TEXT NOT NULL,
          passage_reference TEXT NOT NULL DEFAULT ''
        )
        """
    )
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(excerpt_catalog)").fetchall()}
    if "passage_reference" not in cols:
        conn.execute(
            "ALTER TABLE excerpt_catalog ADD COLUMN passage_reference TEXT NOT NULL DEFAULT ''"
        )
    conn.commit()


def _already_indexed(conn: sqlite3.Connection, source_title: str) -> bool:
    # Require at least 10 rows to consider a resource indexed.  A single seed
    # excerpt in the catalog should not prevent full indexing from source.txt.
    count = conn.execute(
        "SELECT COUNT(*) FROM excerpt_catalog WHERE source_title = ?", (source_title,)
    ).fetchone()[0]
    return int(count) >= 10


def _insert_excerpts(conn: sqlite3.Connection, rows: list[dict]) -> int:
    conn.executemany(
        """
        INSERT INTO excerpt_catalog
          (text, source_title, author, source_type, paragraph_type, passage_reference)
        VALUES (:text, :source_title, :author, :source_type, :paragraph_type, :passage_reference)
        """,
        rows,
    )
    conn.commit()
    return len(rows)


# ---------------------------------------------------------------------------
# Index one resource
# ---------------------------------------------------------------------------


def index_resource(resource: dict, conn: sqlite3.Connection, *, dry_run: bool = False) -> int:
    slug = resource["slug"]
    source_title = resource["source_title"]
    author = resource["author"]
    source_type = resource["source_type"]
    skip = resource.get("skip_header_lines", 50)
    is_met_tab = resource.get("is_met_tab", False)

    txt_path = LIBRARY_DIR / slug / "source.txt"
    if not txt_path.exists():
        print(f"  SKIP {slug}: no source.txt")
        return 0

    if not dry_run and _already_indexed(conn, source_title):
        count = conn.execute(
            "SELECT COUNT(*) FROM excerpt_catalog WHERE source_title = ?", (source_title,)
        ).fetchone()[0]
        print(f"  SKIP {slug}: already indexed ({count} rows)")
        return 0

    print(f"  Indexing {slug}...")
    raw = txt_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    body = "\n".join(lines[skip:])

    toc_map: dict[str, str] = {}
    if is_met_tab:
        toc_map = _parse_met_tab_toc(raw)
        print(f"    TOC entries parsed: {len(toc_map)}")

    rows: list[dict] = []
    rejected = 0
    for chunk in chunks(body):
        if not is_quality(chunk):
            rejected += 1
            continue

        if is_met_tab:
            passage_ref = _chunk_sermon_ref(toc_map, chunk)
            if not passage_ref:
                refs = extract_refs(chunk)
                passage_ref = refs[0] if refs else ""
        else:
            refs = extract_refs(chunk)
            passage_ref = refs[0] if refs else ""

        ptype = paragraph_type(chunk)
        rows.append(
            {
                "text": chunk[:2000],
                "source_title": source_title,
                "author": author,
                "source_type": source_type,
                "paragraph_type": ptype,
                "passage_reference": passage_ref,
            }
        )

    with_ref = sum(1 for r in rows if r["passage_reference"])
    print(f"    Chunks: {len(rows)} kept, {rejected} rejected (OCR/quality)")
    print(f"    passage_reference populated: {with_ref}/{len(rows)}")

    if dry_run:
        for r in rows[:3]:
            ref = r["passage_reference"] or "(no ref)"
            print(f"      [{ref}] {r['text'][:80].strip()}...")
        return 0

    inserted = _insert_excerpts(conn, rows)
    return inserted


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(dry_run: bool = False) -> None:
    conn = _connect(DB_PATH)
    _ensure_schema(conn)

    current = conn.execute("SELECT COUNT(*) FROM excerpt_catalog").fetchone()[0]
    print(f"excerpt_catalog: {current} rows before indexing")
    print()

    total_new = 0
    for resource in RESOURCES:
        n = index_resource(resource, conn, dry_run=dry_run)
        total_new += n

    final = conn.execute("SELECT COUNT(*) FROM excerpt_catalog").fetchone()[0]
    with_ref = conn.execute(
        "SELECT COUNT(*) FROM excerpt_catalog WHERE passage_reference != ''"
    ).fetchone()[0]
    print()
    print(f"Done. excerpt_catalog: {final} rows (+{final - current} new)")
    print(f"Rows with passage_reference: {with_ref}/{final}")

    if not dry_run:
        # Show coverage for key benchmark passages
        for ref in ["John 10", "Romans 5", "Matthew 26", "Philippians 2"]:
            count = conn.execute(
                "SELECT COUNT(*) FROM excerpt_catalog WHERE passage_reference LIKE ?",
                (f"{ref}%",),
            ).fetchone()[0]
            print(f"  {ref}: {count} indexed excerpts")

    conn.close()


if __name__ == "__main__":
    dry = "--dry-run" in sys.argv
    if dry:
        print("=== DRY RUN — no DB writes ===\n")
    main(dry_run=dry)
