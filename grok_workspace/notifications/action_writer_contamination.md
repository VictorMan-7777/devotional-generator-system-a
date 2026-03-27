**Diagnosis Action Writer Contamination**

**Code:** action_writer_training_agent.py run_fresh_action_steps_benchmark _FRESH_BENCHMARK_PASSAGES luke proverbs col habakkuk psalm.

_build_be_still _build_exposition _build_action_steps real_section_generator.

llm_action_steps_core build_llm_action_steps_trainer_review action_items connector be_still_prompts passage_text.

**Problem:** _build_action_steps line 1932 _action_image = _scripture_image(scripture_text) full context bleed outside focal.

items f"Name ... \"{_action_image}\" surfaced in your Be Still reflection" quote full not focal.

**Evidence:** trainer flows_from_be_still fail contamination outside passage.

**Location:** src/generation/real_section_generator.py _build_action_steps ~1932 same as be_still.

**Fix:** replace _scripture_image(scripture_text) with _scripture_image(focal_scripture_text or scripture_text) add param or compute focal.

Next proposal generator action focal image.