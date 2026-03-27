from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerBenchmark:
    name: str
    reference: str
    reason: str


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    owned_surface: str
    objective_metrics: tuple[str, ...]
    learning_inputs: tuple[str, ...]
    benchmark_passages: tuple[WorkerBenchmark, ...]
    debate_role: str
    idle_duties: tuple[str, ...] = ()


WORKER_SPECS: tuple[WorkerSpec, ...] = (
    WorkerSpec(
        name="training_manager",
        owned_surface="Training-mode orchestration across workers, benchmark passage selection, scripture-range coverage, and escalation when worker learning stalls.",
        objective_metrics=(
            "training_cycle_completion_rate",
            "benchmark_coverage_rate",
            "worker_improvement_rate",
            "idle_training_utilization",
        ),
        learning_inputs=(
            "worker experiment ledger",
            "harness passage outcomes",
            "review acceptance trends",
            "range-length performance from 6-day/1-week through 30-day/5-week runs",
            "live generation requests that interrupt training mode",
        ),
        benchmark_passages=(
            WorkerBenchmark("short-cycle", "Luke 15", "Train the system on a 6-day / 1-week passage cycle."),
            WorkerBenchmark("medium-cycle", "Exodus 19-20", "Train the system on a 12-day / 2-week outline-sensitive cycle."),
            WorkerBenchmark("long-cycle", "Psalms 23-25", "Train the system on longer multi-week coordination."),
        ),
        debate_role="Challenge whether the current training queue is improving the right worker, with the right scripture range, at the right time.",
        idle_duties=(
            "Schedule training-mode passage runs whenever the generator has no live request.",
            "Move the system through 6-day/1-week to 30-day/5-week training ranges instead of repeating one fixed shape.",
            "Shift attention toward the worker that is currently limiting generation quality.",
        ),
    ),
    WorkerSpec(
        name="output_training_manager",
        owned_surface="Training-mode orchestration for output workers, especially PDF product quality, proof/final state separation, and publication-facing polish.",
        objective_metrics=(
            "output_cycle_completion_rate",
            "pdf_worker_improvement_rate",
            "proof_quality_progress",
            "output_benchmark_coverage_rate",
        ),
        learning_inputs=(
            "pdf worker experiment ledger",
            "reviewed-proof findings",
            "PDF engine/compliance test outcomes",
            "operator PDF quality findings",
        ),
        benchmark_passages=(
            WorkerBenchmark("proof-design", "Habakkuk 1-3", "Train the output workers on title page, introduction, and day hierarchy."),
            WorkerBenchmark("proof-layout", "Exodus 19-20", "Train the output workers on overflow, margin safety, and proof handling."),
            WorkerBenchmark("premium-rhythm", "Psalms 23-25", "Train the output workers on longer-form page rhythm and polish."),
        ),
        debate_role="Challenge whether the output workers are improving actual publication quality rather than merely passing technical engine tests.",
        idle_duties=(
            "Run PDF/output worker cycles when no higher-priority output review is active.",
            "Keep proof-state and final-state output concerns clearly separated.",
            "Prioritize visible product weaknesses that would reduce buyer confidence.",
        ),
    ),
    WorkerSpec(
        name="acquisition_librarian",
        owned_surface="Library acquisition, cataloging readiness, metadata normalization, and shelving resources for worker use.",
        objective_metrics=(
            "catalog_ready_rate",
            "acquisition_fulfillment_rate",
            "resource_metadata_completeness_rate",
        ),
        learning_inputs=(
            "research librarian acquisition requests",
            "resource source yield history",
            "cataloging corrections",
            "validator-safe source policies",
        ),
        benchmark_passages=(
            WorkerBenchmark("prophetic-gap-fill", "Habakkuk 1-3", "Acquire and catalog resources for a difficult prophetic passage."),
            WorkerBenchmark("parable-gap-fill", "Luke 15", "Acquire book-fit resources for clustered parables."),
            WorkerBenchmark("epistle-gap-fill", "Colossians 3-4", "Acquire and catalog epistle resources for household and union themes."),
        ),
        debate_role="Challenge whether newly acquired resources are truly catalog-ready and safe for downstream workers.",
        idle_duties=(
            "Prioritize open worker-driven acquisition requests ahead of speculative library growth.",
            "Inspect newly acquired resources beyond the TOC and create shelf-ready card catalog entries.",
            "Normalize metadata and mark resources as ready for research-librarian use.",
        ),
    ),
    WorkerSpec(
        name="research_librarian",
        owned_surface="Passage-specific research answering, shared bundle preparation, and acquisition handoff when the library is thin.",
        objective_metrics=(
            "shared_bundle_helpfulness_rate",
            "followup_request_rate",
            "thin_library_escalation_accuracy",
        ),
        learning_inputs=(
            "worker resource requests",
            "writer-selected supports",
            "outliner resource usage",
            "general librarian fulfillment outcomes",
        ),
        benchmark_passages=(
            WorkerBenchmark("law-service", "Exodus 19-20", "Serve doctrinal and structural resources without weak fallback."),
            WorkerBenchmark("parable-service", "Luke 15", "Serve scene-fit resources across clustered narratives."),
            WorkerBenchmark("epistle-service", "Colossians 3-4", "Serve shared resources for outliner and writer from the same passage pool."),
        ),
        debate_role="Challenge whether the shared bundle really answers the worker's research need before asking for acquisition or returning it as sufficient.",
        idle_duties=(
            "Review outstanding worker requests and identify which passage families remain thin.",
            "Turn live worker needs into targeted acquisition requests for the general librarian.",
            "Prebuild likely shared bundles only when near-future passages are already probable.",
        ),
    ),
    WorkerSpec(
        name="outliner",
        owned_surface="Passage structure, day boundaries, week turns, burden assignment, and genre-aware segmentation.",
        objective_metrics=(
            "BOOK_DAY_PROGRESS",
            "BOOK_WEEK_TRANSITION",
            "BOOK_THEOLOGICAL_BOUNDARY",
            "harness_pass_rate",
        ),
        learning_inputs=(
            "passage text",
            "book-specific commentary outlines",
            "genre-sensitive structural cues",
            "remedy outcomes",
            "second-eyes critique",
        ),
        benchmark_passages=(
            WorkerBenchmark("sinai-boundary", "Exodus 19-20", "Law, covenant, and week-turn pressure test."),
            WorkerBenchmark("wisdom-progression", "Proverbs 1-2", "Adjacent-day sameness pressure test."),
            WorkerBenchmark("conversion-arc", "Acts 9", "Narrative turn and burden differentiation test."),
            WorkerBenchmark("prophetic-lament", "Habakkuk 1-3", "Difficult prophetic movement test."),
        ),
        debate_role="Challenge the proposed outline for weak boundaries, repeated burdens, and genre mistakes before generation proceeds.",
    ),
    WorkerSpec(
        name="exposition_writer",
        owned_surface="Exposition research, paragraph construction, readability, and passage-faithful devotional prose.",
        objective_metrics=(
            "EXPOSITION_VOICE",
            "EXPOSITION_WORD_COUNT",
            "readability_grade_le_8",
            "review_acceptance_rate",
        ),
        learning_inputs=(
            "passage text",
            "selected commentary support",
            "approved reviewer edits",
            "approved final exposition",
        ),
        benchmark_passages=(
            WorkerBenchmark("habakkuk-lament", "Habakkuk 1-3", "Prophetic complaint and faith-under-loss test."),
            WorkerBenchmark("colossians-union", "Colossians 3-4", "Epistle exhortation and household-flow test."),
            WorkerBenchmark("psalm-devotional", "Psalms 23-25", "Poetry, prayer, and devotional tone test."),
        ),
        debate_role="Challenge weak abstractions, repeated sentence frames, and paragraph movement before the exposition is accepted.",
    ),
    WorkerSpec(
        name="quote_selector",
        owned_surface="Quote suitability, source search order, duplicate avoidance, and complete Turabian readiness.",
        objective_metrics=(
            "complete_turabian_rate",
            "duplicate_quote_failure_rate",
            "validator_quote_pass_rate",
        ),
        learning_inputs=(
            "approved source domains",
            "domain-level citation yield history",
            "selector-touched source traces",
            "quote rejection reasons",
        ),
        benchmark_passages=(
            WorkerBenchmark("pastoral-devotional", "Psalms 23-25", "High-fit quote suitability test."),
            WorkerBenchmark("law-doctrine", "Exodus 19-20", "Citation completeness under doctrinal pressure."),
            WorkerBenchmark("church-partnership", "Colossians 3-4", "Distinct quote distribution across an epistle."),
        ),
        debate_role="Challenge whether a quote is truly day-specific and fully citable before it is accepted into the devotional.",
    ),
    WorkerSpec(
        name="theological_reviewer",
        owned_surface="Expert review of theological writing, doctrinal boundaries, and quote appropriateness before content is treated as trustworthy.",
        objective_metrics=(
            "theological_boundary_review_pass_rate",
            "quote_appropriateness_pass_rate",
            "manual_review_flag_reduction",
        ),
        learning_inputs=(
            "book-level validator findings",
            "agent validation reports",
            "quote validation results",
            "approved theological edits",
        ),
        benchmark_passages=(
            WorkerBenchmark("law-holiness-review", "Exodus 19-20", "Review severe holiness passages for flattening and quote fit."),
            WorkerBenchmark("parable-mercy-review", "Luke 15", "Review mercy passages for sentimental drift and quote fit."),
            WorkerBenchmark("epistle-identity-review", "Colossians 3-4", "Review exhortation passages for doctrinal clarity and quote fit."),
        ),
        debate_role="Challenge every theological claim and quote choice for passage fit, doctrinal safety, and competition-grade seriousness before approval.",
    ),
    WorkerSpec(
        name="policy_guardian",
        owned_surface="Expert oversight of worker and trainer behavior against global rules-laws authority, repo-local laws, anti-crutch guardrails, and role-boundary discipline.",
        objective_metrics=(
            "guardrail_violation_reduction",
            "role_boundary_violation_rate",
            "crutch_detection_rate",
        ),
        learning_inputs=(
            "rules-laws constitution and hierarchy",
            "repo-local laws",
            "latest trainer outputs",
            "monitor-visible system debt",
        ),
        benchmark_passages=(
            WorkerBenchmark("outliner-guardrail", "Luke 15", "Detect repeated failed-method reuse and role-boundary drift."),
            WorkerBenchmark("library-guardrail", "James 1", "Detect premature acquisition escalation and weak packet discipline."),
            WorkerBenchmark("output-guardrail", "Habakkuk 1-3", "Detect output shortcuts that look compliant without being premium."),
        ),
        debate_role="Challenge agent behavior that looks productive while violating DevG laws, role boundaries, or real-learning standards.",
    ),
    WorkerSpec(
        name="grammar_advisor",
        owned_surface="Expert review of grammar, paragraph clarity, sentence rhythm, and readable prose quality for devotional writing without overriding theological judgment.",
        objective_metrics=(
            "grammar_review_pass_rate",
            "awkward_sentence_reduction",
            "paragraph_clarity_rate",
        ),
        learning_inputs=(
            "approved exposition text",
            "editorial prose revisions",
            "sentence-length patterns",
            "readability and awkwardness findings",
        ),
        benchmark_passages=(
            WorkerBenchmark("epistle-prose-review", "Colossians 3-4", "Review exposition prose for clarity and rhythm in exhortation-heavy material."),
            WorkerBenchmark("wisdom-prose-review", "Proverbs 1-2", "Review concise explanatory prose in wisdom material."),
            WorkerBenchmark("prophetic-prose-review", "Habakkuk 1-3", "Review severity-preserving prose under difficult prophetic material."),
        ),
        debate_role="Challenge cluttered, repetitive, or grammatically weak prose without flattening the passage burden.",
    ),
    WorkerSpec(
        name="passage_researcher",
        owned_surface="Passage-relevant commentary/support retrieval and coordination for the exposition writer and other content workers.",
        objective_metrics=(
            "same_book_support_rate",
            "support_acceptance_rate",
            "wrong_book_helper_rate",
        ),
        learning_inputs=(
            "writer-selected supports",
            "writer-rejected supports",
            "book-specific commentary preference",
            "review trust findings",
        ),
        benchmark_passages=(
            WorkerBenchmark("prophetic-judgment", "Ezekiel 38-39", "Wrong-book helper and warning-lane test."),
            WorkerBenchmark("parable-cohesion", "Luke 15", "Scene-fit support test across short narratives."),
            WorkerBenchmark("sinai-theology", "Exodus 19-20", "Support-fit test for doctrinal and covenant framing."),
        ),
        debate_role="Challenge whether retrieved support really belongs to the passage before the writer sees it as trusted evidence.",
    ),
    WorkerSpec(
        name="be_still_writer",
        owned_surface="Meditative stillness prompts that remain anchored to the day passage without drifting into generic sentiment.",
        objective_metrics=(
            "section_day_unification",
            "passage_anchor_rate",
            "review_acceptance_rate",
        ),
        learning_inputs=(
            "day brief",
            "approved be still edits",
            "approved final be still sections",
        ),
        benchmark_passages=(
            WorkerBenchmark("lament-stillness", "Habakkuk 1-3", "Tests stillness under protest and trembling faith."),
            WorkerBenchmark("poetic-trust", "Psalms 23-25", "Tests prayerful stillness in poetic material."),
            WorkerBenchmark("sinai-awe", "Exodus 19-20", "Tests reverent stillness in law and holy encounter."),
        ),
        debate_role="Challenge generic calm-language and require stillness prompts to arise from the actual passage burden.",
    ),
    WorkerSpec(
        name="action_writer",
        owned_surface="Concrete action steps that obey the text without collapsing into vague productivity or moralism.",
        objective_metrics=(
            "section_day_unification",
            "application_specificity_rate",
            "review_acceptance_rate",
        ),
        learning_inputs=(
            "day brief",
            "approved action-step edits",
            "approved final action steps",
        ),
        benchmark_passages=(
            WorkerBenchmark("kingdom-obedience", "Luke 5-6", "Tests action under Christ's authority and mercy."),
            WorkerBenchmark("wisdom-walk", "Proverbs 1-2", "Tests practical action under wisdom literature."),
            WorkerBenchmark("colossians-obedience", "Colossians 3-4", "Tests action in epistle exhortation and household ethics."),
        ),
        debate_role="Challenge vague, generic, or over-broad action steps and require text-shaped obedience.",
    ),
    WorkerSpec(
        name="prayer_writer",
        owned_surface="Closing prayers that stay inside the passage horizon and reflect the right theological burden and tone.",
        objective_metrics=(
            "section_day_unification",
            "theological_boundary_pass_rate",
            "review_acceptance_rate",
        ),
        learning_inputs=(
            "day brief",
            "approved prayer edits",
            "approved final prayers",
        ),
        benchmark_passages=(
            WorkerBenchmark("prophetic-prayer", "Habakkuk 1-3", "Tests prayer under complaint, awe, and trembling joy."),
            WorkerBenchmark("warning-prayer", "Ezekiel 38-39", "Tests prayer under judgment and holy sovereignty."),
            WorkerBenchmark("worship-prayer", "Psalms 23-25", "Tests prayer in poetic trust and worship."),
        ),
        debate_role="Challenge prayers that outrun the text, import the wrong covenant horizon, or flatten severe passages into generic comfort.",
    ),
    WorkerSpec(
        name="pdf_art_director",
        owned_surface="Visual direction for devotional pages: title/opening pages, typography scale, day separators, page atmosphere, and overall premium presentation.",
        objective_metrics=(
            "title_page_quality",
            "day_boundary_visibility",
            "introduction_quality",
            "proof_readability_quality",
        ),
        learning_inputs=(
            "approved reviewed-proof PDFs",
            "operator PDF findings",
            "front matter rendering outputs",
            "page-design regression tests",
        ),
        benchmark_passages=(
            WorkerBenchmark("short-proof", "Luke 15", "Short parable set for day-boundary and typography checks."),
            WorkerBenchmark("mid-proof", "Habakkuk 1-3", "Difficult tone test for title page, introduction, and day separation."),
            WorkerBenchmark("long-proof", "Psalms 23-25", "Multi-week proof for premium page rhythm and atmosphere."),
        ),
        debate_role="Challenge bland layout, weak hierarchy, and cheap-looking presentation before proof PDFs are accepted.",
    ),
    WorkerSpec(
        name="pdf_layout_engineer",
        owned_surface="Pagination, overflow prevention, KDP-safe margins, reviewed-proof watermarking, and final PDF layout correctness.",
        objective_metrics=(
            "overflow_free_pages",
            "kdp_margin_compliance",
            "watermark_correctness",
            "proof_to_final_layout_stability",
        ),
        learning_inputs=(
            "PDF engine test results",
            "layout overflow findings",
            "KDP compliance checks",
            "review-to-proof export results",
        ),
        benchmark_passages=(
            WorkerBenchmark("overflow-pressure", "Exodus 19-20", "Boundary-heavy run for footer pressure and page overflow."),
            WorkerBenchmark("proof-watermark", "Colossians 3-4", "Reviewed-proof watermark and post-review rendering test."),
            WorkerBenchmark("premium-layout", "Psalms 23-25", "Long-form layout test for stable margins and page breaks."),
        ),
        debate_role="Challenge any PDF that clips content, loses margins, or looks like a draft printout instead of a premium devotional.",
    ),
)


def list_worker_specs() -> tuple[WorkerSpec, ...]:
    return WORKER_SPECS


def get_worker_spec(name: str) -> WorkerSpec:
    key = (name or "").strip().lower()
    if key == "exposition_retriever":
        key = "passage_researcher"
    for spec in WORKER_SPECS:
        if spec.name == key:
            return spec
    raise KeyError(f"Unknown autoresearch worker: {name}")
