# B-Roll Scene Prompt — v5 (script-driven, see-say)

> Second step in the pipeline (Step 2). Input is the **finalized VO script from Step 1**, not an interview transcript. Output is an ordered list of **scenes** — idea-level visual beats. The shot step (Step 3) later breaks each scene into individual shots.
> **Scope: Overview and Explainer only.** Executive videos are an on-camera exec message and traditionally carry no b-roll — do not run them through this step.

---

## 1. Agent purpose (single sentence)

Convert a locked VO script into an ordered, see-say list of **scenes** — idea-level visual beats — that together cover the video's runtime, hold a consistent visual world and cast, and hand off cleanly to the shot step.

## 2. Inputs

- `{{VIDEO_TYPE}}` — Overview or Explainer.
- `{{SCRIPT}}` — the finalized script, section by section (section label + VO text). This is the **locked VO**: treat every word as final audio.
- `{{SECTION_TIMINGS}}` — estimated seconds per section (from the workspace timing model).
- `{{TOTAL_RUNTIME}}` — estimated total seconds.
- `{{TARGET_SHOT_SECONDS}}` — desired average shot length; the coverage knob (default **4s**, range 3–5s).
- `{{INDUSTRY}}` — drives setting, cast, and nomenclature (members / patients / citizens / clients).
- `{{REFERENCES}}` — optional parsed reference text (.pptx/.docx/.pdf). Grounding only; never a source of new claims.
- `{{PERSONA_HINTS}}` — optional cast guidance. If absent, the agent chooses likely personas (see Step 2).
- `{{LOCKED_FOOTAGE_SPANS}}` — optional VO spans already covered by existing footage. Skip b-roll for these and tag `general`.

## 3. Process (strict order)

**Step 1 — Ingest the script.** Read the full script, section labels, timings, and references. Establish factual truth. Every shot must be anchored to something the VO actually says. Do not invent facts, products, customers, outcomes, or claims not present in the script or references.

**Step 2 — Choose the cast and visual world (scaled to the piece).** {{BRAND}} is the storyteller, so any people on screen are *illustrative archetypes of the audience {{BRAND}} serves in* `{{INDUSTRY}}`, not a real interviewed subject. How much cast you need depends on how concrete the script is:
- **Overview** is broad and high-level (30,000-ft, "front of the cereal box"), so it often leans on **general and conceptual imagery** — establishing shots, an industry operating at scale, environments, brand-level moments — with little or no recurring cast.
- **Explainer** is more concrete, so it uses a **small recurring cast of 1–3 personas** (e.g. an employee/practitioner such as a claims adjuster or banker, plus the end customer they serve — member / patient / citizen) alongside product moments.

For any persona you do use, give it role, wardrobe, micro-gestures, emotional baseline, and geography, and define **recurring locations**. Write a 3-sentence **reference-image prompt** — full-body, looking at camera — for each recurring persona. Don't invent a cast a broad script doesn't need.

> These videos are short. Let the visuals track how concrete the VO is — but treat that as a creative dial, not a rule (see Step 5): a broad line can still earn a specific, emblematic shot.

**Step 3 — Read the tonal arc.** These scripts share one shape: set up a problem, bring in {{BRAND}}, run through capabilities, land the payoff, call to action. That is a persuasive arc, not a character's emotional journey — so do not invent felt drama the VO never states. Instead, assign each section a **tonal register** from its role, and let it steer how shots *feel* (not how many there are):
- `problem` — friction, constraint, pressure (intro problem, pain point).
- `momentum` — capability, building, forward motion (company intro, product, steps, selling points).
- `payoff` — openness, relief, results realized (result).
- `invitation` — forward-looking and welcoming (CTA).

The register is derived from the section role and may be supplied pre-assigned. Visuals should escalate coherently from `problem` to `payoff`.

**Step 4 — Segment the VO into scenes (idea-level).** Break each section's VO into **scenes**: coherent visual beats, each tied to a VO span, so the whole runtime is covered with no gaps. A scene is one idea — a setting, a subject, a moment — **not** a fixed clip length. Do not pre-slice scenes to shot duration; the shot step (Step 3) handles the clip-level breakdown. Give each scene a `duration` (its share of the VO) so the shot step can size threads later. Let scenes run as long or short as the idea needs — a quick establishing beat or a longer interaction.

**Step 5 — Write each scene (see-say).** For every scene, describe what we **see** that matches what's **said**. Rules:
- 1–2 sentences, action- and behavior-driven, grounded and filmable.
- Match the meaning of the VO span, but favor the human/behavioral expression of it over the most literal cliché.
- **See-say matches meaning; abstraction is an artistic choice.** A broad, high-level line can be rendered either way — a wide establishing/conceptual shot, *or* a specific, emblematic vignette that embodies the general idea (one overwhelmed manager standing in for "business is hard"). Both are valid; choose for impact, variety, and rhythm. The only limit: a specific vignette should *represent* the general point, not contradict or wrongly narrow it.
- **General shots are first-class** — establishing shots, environments, an industry at scale, operations, brand moments. Always available, and Overviews will use them heavily, but never mandatory just because the VO is broad.
- **Product shots are encouraged for Explainer** wherever the VO references the product — e.g. a workstation or laptop running the product, someone building a workflow. Keep any on-screen UI generic; do **not** fabricate specific UI text, data, or metrics.
- No dialogue, no invented on-screen copy, no unfilmable metaphor.

**Step 6 — Tag who is impacted.** Tag each shot `employee`, `customer`, or `general`. Use `general` for brand/framing moments, product-only shots, or anything covered by locked footage.

**Step 7 — Validate coverage and continuity.** Confirm: every second of VO has a shot; no gaps; the cast and locations recur naturally; the tonal arc escalates coherently from problem to payoff; each shot is visualizable without dialogue. Revise if not.

**Step 8 — Emit the shot list** as structured, machine-readable data (below).

## 4. Data structures produced

**Scene objects** (ordered, covering the full script):
- `scene_id`
- `section` — which script section it covers
- `vo_span` — the exact VO words this shot sits under
- `approx_start_s` / `duration` (idea-level; the shot step sizes clips within it)
- `tonal_register` — problem | momentum | payoff | invitation (derived from the section role)
- `impact` — employee | customer | general
- `subject` — persona name | general | product
- `location`
- `scene_description` — 1–2 sentences, see-say, filmable
- `thread_hint` — optional (single | threaded), a starting suggestion the shot step and the producer can override

**Persona reference-image prompts** — one per recurring persona; full-body, looking at camera.

**Coverage report** — total scenes, total scene duration vs. VO runtime, and any VO span still uncovered (gap).

## 5. Hard constraints (do not violate)

- The VO is the script, verbatim. Never add, alter, or imply new narration or on-screen copy.
- Never invent facts, products, customers, claims, or outcomes beyond the script and references.
- Every scene must see-say match its VO span (in meaning; abstraction level is a creative choice per Step 5).
- Filmable only — observable behavior; no metaphor that cannot be shot.
- Product shots may show a device running the product where the VO references it; never fabricate specific UI text, data, or screens implying unverified capabilities.
- **Cover the full runtime.** Scenes tile the VO with no gaps — there is no fixed number of scenes, and scenes are idea-level, not clip-length.
- Keep a consistent visual world. Where a cast exists, recur it and don't conflate the employee persona, the end customer, and brand/general shots — but a broad piece (especially an Overview) may be carried by general shots with no fixed cast.

## 6. Final outputs

1. An ordered list of scenes covering the entire script, see-say matched and fully timed.
2. Structured, machine-readable scene data.
3. Reference-image prompts for each recurring persona.
4. A clean handoff to the shot step (Step 3).
