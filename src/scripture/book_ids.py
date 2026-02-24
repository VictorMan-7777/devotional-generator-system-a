"""
Bolls.life book ID mapping table.

Maps book names and common abbreviations (case-insensitive) to the integer
book IDs used by the Bolls.life API. IDs follow canonical order:
Genesis = 1 through Revelation = 66.

Source: PRD Appendix A.11 / Bolls.life API documentation.
"""

from __future__ import annotations

# Keys are lowercase. Values are canonical integer book IDs.
BOOK_IDS: dict[str, int] = {
    # ── Old Testament ─────────────────────────────────────────────────────────
    "genesis": 1,       "gen": 1,   "gn": 1,
    "exodus": 2,        "exo": 2,   "ex": 2,    "exod": 2,
    "leviticus": 3,     "lev": 3,   "lv": 3,
    "numbers": 4,       "num": 4,   "nm": 4,    "nb": 4,
    "deuteronomy": 5,   "deut": 5,  "dt": 5,    "deu": 5,
    "joshua": 6,        "josh": 6,  "jos": 6,   "jsh": 6,
    "judges": 7,        "judg": 7,  "jdg": 7,   "jg": 7,
    "ruth": 8,          "rut": 8,   "ru": 8,
    "1 samuel": 9,      "1sam": 9,  "1sa": 9,   "i samuel": 9,   "1s": 9,
    "2 samuel": 10,     "2sam": 10, "2sa": 10,  "ii samuel": 10, "2s": 10,
    "1 kings": 11,      "1kgs": 11, "1ki": 11,  "i kings": 11,
    "2 kings": 12,      "2kgs": 12, "2ki": 12,  "ii kings": 12,
    "1 chronicles": 13, "1chr": 13, "1ch": 13,  "i chronicles": 13,
    "2 chronicles": 14, "2chr": 14, "2ch": 14,  "ii chronicles": 14,
    "ezra": 15,         "ezr": 15,
    "nehemiah": 16,     "neh": 16,
    "esther": 17,       "est": 17,  "esth": 17,
    "job": 18,          "jb": 18,
    "psalms": 19,       "psalm": 19, "ps": 19,  "psa": 19, "pss": 19,
    "proverbs": 20,     "prov": 20, "prv": 20,  "pr": 20,
    "ecclesiastes": 21, "eccl": 21, "eccles": 21, "ec": 21, "qoh": 21,
    "song of solomon": 22, "song of songs": 22, "sos": 22, "ss": 22,
    "song": 22,         "cant": 22, "sng": 22,
    "isaiah": 23,       "isa": 23,  "is": 23,
    "jeremiah": 24,     "jer": 24,  "je": 24,
    "lamentations": 25, "lam": 25,  "la": 25,
    "ezekiel": 26,      "ezek": 26, "eze": 26,  "ezk": 26,
    "daniel": 27,       "dan": 27,  "da": 27,   "dn": 27,
    "hosea": 28,        "hos": 28,  "ho": 28,
    "joel": 29,         "joe": 29,  "jl": 29,
    "amos": 30,         "amo": 30,  "am": 30,
    "obadiah": 31,      "obad": 31, "ob": 31,
    "jonah": 32,        "jon": 32,  "jnh": 32,
    "micah": 33,        "mic": 33,  "mi": 33,
    "nahum": 34,        "nah": 34,  "na": 34,
    "habakkuk": 35,     "hab": 35,
    "zephaniah": 36,    "zeph": 36, "zep": 36,
    "haggai": 37,       "hag": 37,
    "zechariah": 38,    "zech": 38, "zec": 38,
    "malachi": 39,      "mal": 39,
    # ── New Testament ─────────────────────────────────────────────────────────
    "matthew": 40,      "matt": 40, "mat": 40,  "mt": 40,
    "mark": 41,         "mrk": 41,  "mk": 41,   "mar": 41,
    "luke": 42,         "luk": 42,  "lk": 42,
    "john": 43,         "jhn": 43,  "jn": 43,
    "acts": 44,         "act": 44,  "ac": 44,
    "romans": 45,       "rom": 45,  "ro": 45,   "rm": 45,
    "1 corinthians": 46, "1cor": 46, "1co": 46, "i corinthians": 46,
    "2 corinthians": 47, "2cor": 47, "2co": 47, "ii corinthians": 47,
    "galatians": 48,    "gal": 48,  "ga": 48,
    "ephesians": 49,    "eph": 49,
    "philippians": 50,  "phil": 50, "php": 50,
    "colossians": 51,   "col": 51,
    "1 thessalonians": 52, "1thess": 52, "1th": 52, "i thessalonians": 52,
    "2 thessalonians": 53, "2thess": 53, "2th": 53, "ii thessalonians": 53,
    "1 timothy": 54,    "1tim": 54, "1ti": 54,  "i timothy": 54,
    "2 timothy": 55,    "2tim": 55, "2ti": 55,  "ii timothy": 55,
    "titus": 56,        "tit": 56,
    "philemon": 57,     "phlm": 57, "phm": 57,
    "hebrews": 58,      "heb": 58,
    "james": 59,        "jas": 59,  "jm": 59,
    "1 peter": 60,      "1pet": 60, "1pe": 60,  "i peter": 60,
    "2 peter": 61,      "2pet": 61, "2pe": 61,  "ii peter": 61,
    "1 john": 62,       "1jhn": 62, "1jn": 62,  "i john": 62,
    "2 john": 63,       "2jhn": 63, "2jn": 63,  "ii john": 63,
    "3 john": 64,       "3jhn": 64, "3jn": 64,  "iii john": 64,
    "jude": 65,         "jud": 65,
    "revelation": 66,   "rev": 66,  "re": 66,   "rv": 66,
}


def get_book_id(book_name: str) -> int | None:
    """
    Resolve a book name or abbreviation to its Bolls.life integer book ID.

    Returns None if the name is not recognised.
    Lookup is case-insensitive and strips surrounding whitespace.
    """
    return BOOK_IDS.get(book_name.lower().strip())
