# Exposition — Two Structural Bugs Still Active (cycle 2026-03-23__110944)

The trainer identified two structural issues in `real_section_generator.py` that are not training-quality problems. Both will recur deterministically. Both need code fixes.

## Bug 1: Generic closing paragraph via theme_addenda (lines ~1484–1704)

The `_ensure_exposition_floor()` fix (our last change) cleared the `supplementals` list — that path is clean. But there is a second, separate word-padding mechanism: the `addenda` / `theme_addenda` dict that runs from line 1484 through ~1704. This path appends theme-specific sentences when exposition is under 520 words. The "response" theme includes:

> "Devotion trained by this kind of text becomes steadier over time because it is anchored in what God has actually said."

and five other sentences in the same block. The trainer described this as:
> "semantically identical to closing paragraphs that would be generated for any devotional passage... it is a structural template suffix, not a quality-of-attention problem."

**Target:** `real_section_generator.py`, the `theme_addenda["response"]` block and the `addenda.extend()` / `for sentence in addenda:` loop. Either remove the generic sentences or require each sentence to reference a lexical token from the supplied passage text before it can be emitted.

## Bug 2: Heading fragment concatenated into prose

The trainer saw the phrase "worship and wisdom under the word of god" appearing mid-paragraph with no surrounding punctuation and no grammatical connection to adjacent sentences. `_strip_stray_headings()` exists (line 68) but is not catching this pattern because it appears to be lowercase and doesn't match the heading-detection heuristics in `_looks_like_heading()`.

**Target:** `real_section_generator.py`, `_looks_like_heading()` (line 194) and `_strip_stray_headings()` (line 68). The filter needs to catch bare lowercase phrase fragments that are not grammatically connected to surrounding prose — or trace where the phrase is being injected and prevent it at the source.

---

## Bug 3: Section label injected mid-paragraph (cycle 2026-03-23__124138)

The trainer identified a third deterministic artifact: a section-label string (e.g. "worship and wisdom under the word of god") appearing mid-paragraph with no surrounding punctuation, in a syntactically impossible position. The trainer's diagnosis:

> "This is a deterministic artifact of a leaking template or prompt-construction bug, not a training quality issue. The string appears in a syntactically impossible position (mid-paragraph, lowercase, no punctuation connection to surrounding sentences), which cannot be produced by a language model that is simply undertrained — it must be injected by the generation harness."

**Target:** `real_section_generator.py`. Either (a) add a post-processing filter that strips lines matching the known set of section-label strings before the exposition is returned, or (b) fix the prompt construction so scaffold labels are marked with a non-output delimiter and stripped at render time.

Note: `_strip_stray_headings()` (Bug 2 above) may catch some of these, but the trainer implies the injection point is in prompt construction, not just in post-processing.

---

## Bug 4: Missing passage-coverage validation (cycle 2026-03-23__165456)

The exposition for Psalm 23:1-2 omitted "He leads me beside quiet waters" (23:2b) entirely. The trainer's diagnosis:

> "The omission suggests the generation loop either truncates coverage of multi-clause verses or weights the first clause so heavily that subsequent clauses are dropped. A post-generation coverage check is a structural safeguard that training alone cannot provide if the loop architecture systematically deprioritizes later verse clauses."

**Target:** `src/generation/real_section_generator.py`. After generation, parse the output to check whether key lexical items from the focal reference verses each appear at least once with surrounding contextual engagement. If any focal-reference element is absent, trigger regeneration or flag for revision rather than accepting the output. For Psalm 23:1-2 the required elements include: 'shepherd', 'want'/'lack', 'green pastures', 'quiet waters'/'still waters', 'leads'.

---

All four bugs are code changes, not training changes. Submit a combined proposal if they are in the same code region. Include a specific `old_string` / `new_string` diff showing what changes.
