# Shot-Generation Prompt (individual shots) — v2

> Third step in the pipeline (Step 3). Input is the **scene list** from the scene step (Step 2). Break each scene into individual shots and write **one complete, self-contained image prompt per shot**. No grids — every shot is generated on its own.

## Inputs (per scene, from the scene step)
`scene_id / section` · `vo_span` · `location` · `subject` (persona name → use that persona's reference image; or `general` / `product`) · `tonal_register` (problem | momentum | payoff | invitation) · `scene_description` · `duration` · `{{TARGET_SHOT_SECONDS}}` (default 4s, range 3–5s).

## How many shots per scene
- **Single** — one shot prompt. Use for establishing shots, general/brand moments, product-only inserts, or any short beat.
- **Threaded** — several shot prompts that read as consecutive beats of one moment. Use when the scene has observable action with a beginning-middle-end, a two-person interaction, or a visible emotional shift. Size the thread to the scene: roughly `ceil(duration / {{TARGET_SHOT_SECONDS}})` shots.

The scene may arrive with a `thread_hint`; treat it as a starting suggestion the producer can override.

## Output rules
- Emit an **ordered, flat list of shots**. There is no fixed shot count — it scales to the scenes.
- Each shot is **one complete, self-contained image prompt** (no "as above," no references to other shots).
- Every shot prompt must include: 1) Setting + art direction, 2) Subject description (**matches the reference exactly**; for `general`/`product` shots, describe the environment or device instead), 3) Lighting plan (from `tonal_register`, within the natural-light house style), 4) Camera + lens + aperture + distance/angle + DOF, 5) the single shot's action/framing, 6) Finishing notes.
- **Within a threaded scene, every sibling shot restates the same setting, subject, wardrobe, and lighting** (same reference image) and changes only its framing/action — this is what holds the thread together with no grid.
- **Each scene includes at least one wide shot** usable as an additional reference plate later (the single shot itself, or one shot in the thread). Flag it `wide_reference`.

## Creative constraints
- Consistent subject, wardrobe, location, lighting mood, and aesthetic across all shots of a scene.
- **No gender references** in text — identity is fixed by the reference image. Use "the subject," "the person," or omit pronouns. Diversity lives across personas/reference images, not in prompt wording.
- Cinematic + technical detail on every shot: focal length, aperture, distance/angle, depth of field, lighting.
- Framing mostly tight (close-ups, partial crops, hands/face) with wider shots for rhythm; vary angles subtly (high/low tilt, over-shoulder, profile, foreground obstructions).
- Tactile props / environmental elements that support the beat (fabric, glass, rain, reflections, paper, steam) without changing location.
- Finishing: "Capture RAW," "muted professional grade," "smooth tonal rolloff," "subtle cinematic grain," "controlled contrast."

## Style & tone
Authentic documentary realism · natural expressions and real gestures (mid-conversation, mid-task, mid-thought) · lived-in imperfections · professional yet approachable · real-world color (warm neutrals, soft highlights, no artificial gloss).

## Camera & technical feel
Natural light only (window, office daylight, practical lamps, soft outdoor) · shallow DOF with a clear focal point · clean exposure, no blown highlights · soft contrast, realistic color (no HDR, no over-sharp edges) · subtle film-inspired grain if it supports realism.

## Environment & composition
People in believable everyday moments · confident, efficient individuals, **not** product-first · modern, diverse, relatable work and industry settings · clear context via subtle cues · single clear focal point, uncluttered backgrounds · depth via blur, reflections, or foreground. Avoid clichés (staged handshakes, pointing at screens, contrived poses).

## Overall mood
Confident, approachable, human · calm, clear, aspirational without gloss · feels like a real moment you walked into. Communicates authenticity, trust, competence, clarity, human connection.

## Per-shot prompt format (must match)
```
[Setting + art direction, one location]. Subject (matches reference exactly): [neutral description, or environment/device for general/product].
Lighting: [plan derived from tonal_register].
Shot: [action / framing beat] — [lens], [aperture], [distance/angle], [DOF note].
Props/environment: [tactile elements supporting the beat].
Post: Capture RAW, muted professional grade, smooth tonal rolloff, subtle cinematic grain, controlled contrast.
Mood: [mood].
```

## Shot object (output)
- `shot_id` · `scene_id` (parent) · `order`
- `single | threaded` and position in thread
- `wide_reference` — boolean (which shot becomes the next reference plate)
- `beat` — the editable action/framing (what the producer edits in beat mode)
- `compiled_prompt` — the full text sent to the generator (read-only preview; editable in advanced mode)
