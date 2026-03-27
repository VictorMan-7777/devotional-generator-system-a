**Diagnosis Prayer Template Fix**

**Code:** prayer_writer_training_agent.py fresh _build_prayer brief scripture exposition focal_scripture_text line 116 pass focal.

llm_prayer_writer_core review prayer_text focal_text.

**Problem:** _build_prayer line 2183 _prayer_image = _prayer_image_override or _scripture_image(scripture_text) full context.

**Evidence:** trainer passage_anchored fail template quote outside focal.

**Location:** src/generation/real_section_generator.py _build_prayer ~2183 same pattern.

**Fix:** replace _scripture_image(scripture_text) with _scripture_image(focal_scripture_text or scripture_text)

**Why:** anchor prayer image focal no bleed.

**Success:** trainer anchored pass.

**Target:** src/generation/real_section_generator.py _build_prayer image