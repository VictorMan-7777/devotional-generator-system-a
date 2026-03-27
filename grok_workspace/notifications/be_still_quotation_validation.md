**Diagnosis Be Still Quotation Validation**

**Code:** be_still_training_agent.py run_fresh_be_still_benchmark _FRESH_BENCHMARK_PASSAGES focal context scripture focal_text.

_build_be_still brief scripture_text exposition focal_scripture_text prompts.

llm_be_still_core build_llm_be_still_trainer_review prompts passage_reference passage_text exposition_text.

**Problem:** prompts quote outside focal passage use full context scripture_text.

**Evidence:** cycle fresh score low quote proverb psalm outside assigned habakkuk psalm etc.

**Location:** src/generation/real_section_generator.py _build_be_still quote search scripture_text not focal.

Trainer rubric "passage-specific" fail but weak.

**Fix:** generator _build_be_still quote search focal_scripture_text only.

Or trainer prompt explicit "quotes must be from focal key verses no outside".

Prefer generator enforce assigned scope.

Next proposal generator fix quote focal only.