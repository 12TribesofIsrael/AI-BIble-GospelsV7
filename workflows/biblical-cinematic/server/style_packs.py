"""
Style Packs — audience-specific visual/narration direction for the video engine.

One pipeline, three looks. A pack is a bundle of everything that changes when
you swap audience: the Claude system-prompt language, the FLUX image suffix,
the FLUX negative prompt, the Kling motion guidance, the subtitle styling, and
the suggested ElevenLabs voice.

    cinematic  — the original AI Bible Gospels look. DEFAULT. Unchanged.
    epic       — High Cinematic. Adults. Anamorphic, feature-film grade.
    kids       — Animated. Children. Stylized 3D family-film look.

Imported by:
    workflows/biblical-cinematic/server/biblical_pipeline.py   (Scripture Mode)
    workflows/custom-script/router.py                          (Custom Script Mode)

NON-NEGOTIABLE: the character ethnicity rules are shared by every pack and are
NOT pack-overridable. Animation changes the rendering style, never the skin
tone, hair texture, or features. See brand depiction standard.
"""

DEFAULT_STYLE = "cinematic"

# Kling reinterprets small, ambiguous background shapes when it animates them.
# A distant scatter of sheep on a hillside path turned into a convoy of pickup
# trucks in a kids render on 2026-07-25 — the blobs were too small to read, so the
# video model "resolved" them into the most common thing that shape does on a road.
# Every pack sends this as the Kling negative prompt; anachronisms are a defect in
# any biblical style, not a stylistic choice.
ANACHRONISM_GUARD = (
    "cars, trucks, pickup trucks, vehicles, convoy, traffic, roads with vehicles, "
    "modern machinery, tractors, power lines, telephone poles, modern buildings, "
    "modern clothing, wristwatches, glasses, guns, plastic, signage, text, letters, "
    "morphing objects, shape-shifting background, warping geometry, flickering, "
    "duplicated limbs, extra fingers, distorted faces, low quality, blurry"
)

# Shared across every pack — never overridden by a pack.
ETHNICITY_RULES = """CHARACTER ETHNICITY RULES (CRITICAL):
- ISRAELITES / HEBREWS: Black Hebrew Israelites with rich, deeply melanated dark skin. Natural Afro-textured hair: locs, braids, twists, afros, or traditional head wraps. Traditional Hebrew robes, garments with tzitzit fringes, priestly vestments.
- ROMANS: Caucasian with light skin. Roman armor, togas, military regalia.
- GREEKS / MACEDONIANS: Mediterranean olive skin. Hellenistic armor, robes, classical styling.
- EGYPTIANS: Brown skin. Traditional Egyptian garments and headdress.
- PERSIANS / MEDES: Olive-brown skin. Ornate Persian robes.
- PHILISTINES / CANAANITES: Mediterranean/Levantine appearance. Bronze armor, distinctive garments.
- For scenes with MULTIPLE nations, depict EACH character according to their own nation's ethnicity.
- CRITICAL: Israelites = Black Hebrew Israelites. All other nations = their own historical ethnicity.
- SAY IT EXPLICITLY, EVERY TIME. Naming the group is NOT enough — image models drift pale when
  skin tone is left implied. Any prompt containing an Israelite/Hebrew figure (including Christ,
  the disciples, a shepherd, a crowd, a child) MUST literally spell out the skin tone and the
  hair, e.g. "deeply melanated dark brown skin" plus "natural Afro-textured hair" (locs, coils,
  braids, twists, or a head wrap). This applies to figures seen from behind, in silhouette, at a
  distance, or in a wide shot. Never write "a man in robes" and assume the ethnicity carries.
- WATCH THE BACKLIGHT. The drift clusters on heavily backlit "divine glow" hero shots — arms
  raised, sun behind the head, golden light blowing out the face. When a scene is lit that way,
  state that the divine light must NOT wash out or lighten the skin: keep the face in warm
  frontal fill, rich dark brown skin clearly readable, glow behind rather than across the face."""


STYLE_PACKS = {
    # ------------------------------------------------------------------ #
    # DEFAULT — byte-for-byte the language the engine shipped with.       #
    # Do not "improve" this pack; it is the regression baseline.          #
    # ------------------------------------------------------------------ #
    "cinematic": {
        "id": "cinematic",
        "name": "Cinematic",
        "audience": "General / Adults",
        "blurb": "The original AI Bible Gospels look — photoreal, reverent, gold divine light.",
        "director_role": "cinematic visual director",
        "brand_style": (
            "- Dark, dramatic backgrounds with golden divine light\n"
            "- Cinematic, reverent, powerful tone\n"
            "- Photorealistic ancient biblical settings"
        ),
        "ethnicity_extra": "",
        "image_suffix": (
            "photorealistic, cinematic lighting, 8K, shot on RED V-Raptor, "
            "hyper-detailed skin texture and fabric weave, natural film grain"
        ),
        # Custom Script mode historically used a shorter tail.
        "image_suffix_custom": "photorealistic, cinematic, 8K detail",
        "forbidden_line": (
            'NEVER use words like "painting", "illustration", "stylized", "artistic", '
            '"cartoon", "anime", "rendered", "digital art", or "concept art".'
        ),
        "motion_note": (
            "Camera movement description for video animation (zoom, pan, tilt, pull back, "
            "tracking shot, etc.). Vary angles — never repeat the same motion twice in a row."
        ),
        "lighting_note": (
            "Specific dramatic lighting for the scene (golden hour, divine shaft of light, "
            "torch-lit darkness, moonlit, etc.)."
        ),
        "lighting_examples": (
            "golden divine light, torch-lit darkness, moonlit night, storm clouds, sunrise"
        ),
        "extra_guidelines": "",
        # Custom Script mode only — one GUIDELINES bullet about narration voice.
        "script_tone_line": "- Make narration powerful and revelatory — this is awakening content",
        "narration_note": "",
        "negative_prompt": (
            "cartoon, anime, illustration, painting, drawing, digital art, concept art, "
            "stylized, 3D render, CGI, plastic skin, smooth skin, airbrushed, watercolor, "
            "sketch, unrealistic, low quality, blurry"
        ),
        "cfg_scale": 0.5,
        "kling_negative": ANACHRONISM_GUARD,
        "subtitles": {},  # no overrides — engine defaults
        "suggested_voice": "NgBYGKDDq2Z8Hnhatgma",   # Pro Narrator
        "suggested_model": "v3.0",
    },

    # ------------------------------------------------------------------ #
    # HIGH CINEMATIC — adults. Feature-film grade, heavier atmosphere.    #
    # ------------------------------------------------------------------ #
    "epic": {
        "id": "epic",
        "name": "High Cinematic",
        "audience": "Adults",
        "blurb": "Feature-film grade — anamorphic, volumetric light, shallow depth of field.",
        "director_role": "feature-film cinematographer and visual director",
        "brand_style": (
            "- Epic, theatrical scale — this must feel like a $200M biblical feature film\n"
            "- Deep shadow and controlled contrast (chiaroscuro), golden divine light as the key source\n"
            "- Volumetric god rays through atmospheric haze, drifting dust motes, practical firelight\n"
            "- Anamorphic widescreen framing, shallow depth of field, subject isolated from background\n"
            "- Photorealistic ancient biblical settings with weathered, lived-in production design\n"
            "- Reverent and restrained — gravity over spectacle, never gaudy or over-saturated"
        ),
        "ethnicity_extra": "",
        "image_suffix": (
            "photorealistic, anamorphic widescreen, shot on ARRI Alexa 65 with vintage 40mm "
            "anamorphic lens, shallow depth of field, volumetric atmospheric haze, practical "
            "firelight and god rays, high dynamic range, hyper-detailed melanated skin texture "
            "with visible pores and sweat, hand-woven fabric weave, fine natural 35mm film grain, "
            "subtle halation on highlights, color-graded warm gold and deep teal shadow, 8K"
        ),
        "image_suffix_custom": (
            "photorealistic, anamorphic widescreen, shot on ARRI Alexa 65, shallow depth of field, "
            "volumetric haze and god rays, warm gold and deep teal grade, 35mm film grain, 8K"
        ),
        "forbidden_line": (
            'NEVER use words like "painting", "illustration", "stylized", "artistic", '
            '"cartoon", "anime", "rendered", "digital art", or "concept art".'
        ),
        "motion_note": (
            "Camera movement for video animation. Favor SLOW, deliberate, motivated moves — "
            "a creeping push-in, a slow crane down, a locked-off shot with only atmosphere moving, "
            "a patient tracking shot alongside the subject. No whip pans, no frantic handheld. "
            "Vary the move every scene — never repeat the same motion twice in a row."
        ),
        "lighting_note": (
            "Specific dramatic lighting, described like a gaffer would: key source, direction, "
            "quality, and falloff (e.g. 'single hard shaft of divine light from high camera-left, "
            "deep falloff into black', 'low warm firelight from below frame, smoke catching the beam')."
        ),
        "lighting_examples": (
            "hard divine shaft through cloud break, single-source torchlight with deep falloff, "
            "blue moonlight through a doorway, storm-diffused overcast, low-sun rim light through dust"
        ),
        "extra_guidelines": (
            "- Compose like a film frame: leading lines, negative space, foreground occlusion for depth\n"
            "- Alternate scale deliberately — an epic wide should be followed by an intimate close-up\n"
            "- Let atmosphere do the work: haze, smoke, dust, embers, rain, wind-moved fabric"
        ),
        "script_tone_line": (
            "- Make narration weighty and restrained — trust gravity and silence over hype"
        ),
        "narration_note": (
            "Narration tone: measured, weighty, adult. Do NOT simplify or soften. "
            "Speak to a grown listener who came for depth."
        ),
        "negative_prompt": (
            "cartoon, anime, illustration, painting, drawing, digital art, concept art, "
            "stylized, 3D render, CGI, video game, plastic skin, smooth skin, airbrushed, "
            "waxy, watercolor, sketch, flat lighting, blown highlights, oversaturated, "
            "HDR halo, unrealistic, low quality, blurry, deformed hands, extra fingers, "
            "text, watermark, logo"
        ),
        # Raised above the 0.5 default: slow, deliberate epic moves give Kling more
        # frames to drift over, so it needs to hold the source image harder.
        "cfg_scale": 0.6,
        "kling_negative": ANACHRONISM_GUARD + ", cartoon, animation, stylized",
        "subtitles": {
            # Restrained + on-brand gold instead of the loud default yellow.
            "font-family": "Oswald Bold",
            "word-color": "#E8B44A",
            "line-color": "#EDEDED",
            "outline-width": 8,
        },
        # Daniel Steady Broadcaster — verified against JSON2Video on 2026-07-25.
        "suggested_voice": "onwK4e9ZLuTAKqWW03F9",
        "suggested_model": "o3",
    },

    # ------------------------------------------------------------------ #
    # KIDS — animated. Ethnicity rules still fully apply.                 #
    # ------------------------------------------------------------------ #
    "kids": {
        "id": "kids",
        "name": "Kids Animation",
        "audience": "Children (ages 4–11)",
        "blurb": "Warm stylized 3D family-film animation — bright, safe, never scary.",
        "director_role": "children's animated feature director",
        "brand_style": (
            "- Stylized 3D animated family film — the look of a modern animated feature, NOT photorealism\n"
            "- Warm, bright, saturated color palette; golden divine light stays, but as a friendly glow\n"
            "- Soft rounded character design, large expressive eyes, gentle exaggerated proportions\n"
            "- Clean rim lighting, soft ambient bounce, subsurface-scattered skin, no harsh shadows\n"
            "- Storybook-simple backgrounds with clear silhouettes a child can read instantly\n"
            "- Joyful and reverent — awe without fear"
        ),
        "ethnicity_extra": (
            "\n- ANIMATION DOES NOT CHANGE ETHNICITY. Stylization applies to shape and rendering only. "
            "Israelite characters remain deeply melanated with rich dark brown skin and natural "
            "Afro-textured hair (locs, braids, twists, afros, head wraps) in every animated frame. "
            "Never lighten skin, never straighten hair, never make features Eurocentric for the sake "
            "of a 'cartoon' look."
        ),
        "image_suffix": (
            "stylized 3D animated family feature film still, soft rounded character design, large "
            "expressive eyes, warm saturated storybook color palette, soft rim lighting and ambient "
            "bounce, subsurface scattering on deeply melanated skin, clean readable silhouettes, "
            "gentle depth of field, high-end animation studio render, wholesome and child-friendly"
        ),
        "image_suffix_custom": (
            "stylized 3D animated family feature film still, soft rounded character design, warm "
            "saturated storybook palette, soft rim lighting, deeply melanated skin, child-friendly"
        ),
        "forbidden_line": (
            'The image MUST be animated. NEVER use the words "photorealistic", "photograph", '
            '"photo", "live action", "hyper-realistic", or "documentary". Also NEVER depict blood, '
            'gore, wounds, corpses, weapons striking a person, terror on a face, or anything a young '
            'child would find frightening — imply conflict through posture, distance, and shadow instead.'
        ),
        "motion_note": (
            "Camera movement for video animation. Keep it gentle, smooth, and easy to follow — "
            "slow push-in, soft arc around the subject, gentle pan across a landscape, light float-up. "
            "No jarring or fast moves. Vary the move every scene — never repeat the same motion twice "
            "in a row."
        ),
        "lighting_note": (
            "Bright, warm, friendly lighting (sunny morning, soft golden glow from above, cozy "
            "campfire warmth, gentle starlight). Keep scenes well lit — avoid darkness that reads "
            "as scary to a child."
        ),
        "lighting_examples": (
            "sunny morning light, warm golden glow from above, cozy firelight, soft blue evening light, "
            "cheerful sunrise with pastel sky"
        ),
        "extra_guidelines": (
            "- Every frame must be SAFE for a 4-year-old: no blood, no gore, no horror, no menacing faces\n"
            "- Show emotion through big, clear, readable expressions — kids read faces before words\n"
            "- Include friendly animals, plants, and small visual delights where the text allows\n"
            "- Keep compositions simple and uncluttered — one clear subject per frame"
        ),
        "script_tone_line": (
            "- Make narration warm, simple, and exciting — short sentences a child can follow"
        ),
        "narration_note": (
            "Narration tone for any narration you write yourself (intro/outro/branding): warm, "
            "excited, and simple — like a favorite storyteller talking to a child. Short sentences. "
            "Everyday words. Never condescending, never scary. "
            "IMPORTANT: scripture text itself is NEVER paraphrased, simplified, or reworded — "
            "the verses stay exactly as given."
        ),
        # The skin-tone guard is deliberate and pack-specific. Stylized animation
        # drifts pale harder than photoreal does — a kids render produced a
        # light-skinned Christ on 2026-07-26 despite the prompt rules. The kids cast
        # is Israelite essentially always, so a blanket guard is safe here in a way
        # it would NOT be for the cinematic/epic packs, which legitimately depict
        # Caucasian Romans and Mediterranean Greeks. If a kids story ever needs a
        # Roman, drop this clause for that render rather than weakening the rule.
        "negative_prompt": (
            "light skin, pale skin, white skin, fair complexion, caucasian, european features, "
            "blonde hair, straight hair, red hair, blue eyes, whitewashed, "
            "photorealistic, photograph, live action, realistic skin pores, hyper-realistic, "
            "gore, blood, wounds, corpse, weapon, violence, horror, scary, menacing, creepy, "
            "uncanny valley, dark grim, harsh shadows, desaturated, deformed hands, extra fingers, "
            "extra limbs, distorted face, low quality, blurry, text, watermark, logo"
        ),
        # Was 0.45, which was backwards — a LOW cfg_scale gives Kling more freedom to
        # reinvent the frame, and that is exactly how a hillside of distant sheep
        # became a line of pickup trucks. Kids scenes are the most vulnerable because
        # storybook backgrounds are simple and full of small repeated shapes, so this
        # pack holds the source image hardest of the three.
        "cfg_scale": 0.75,
        "kling_negative": ANACHRONISM_GUARD + ", photorealistic, live action, gore, scary",
        "subtitles": {
            # Bigger, rounder, higher contrast — built for early readers.
            "font-family": "Baloo 2",
            "word-color": "#FFD84D",
            "line-color": "#FFFFFF",
            "outline-color": "#1B2A4A",
            "outline-width": 10,
            "font_size_bump": 8,      # added to the aspect-ratio default
            "max_words_delta": -1,    # fewer words per line for early readers
        },
        # Young Jamal — warm, young-sounding, and VERIFIED against JSON2Video's
        # supported-voice list on 2026-07-25. Do not suggest a voice here without
        # test-rendering it first: JSON2Video rejects ids it doesn't carry, and the
        # render fails only AFTER all the FLUX + Kling money is spent.
        # Alicia Calm Storyteller — the right voice for children's narration. She is
        # valid on ElevenLabs (verified 2026-07-25) but NOT on JSON2Video's curated
        # list, so she only works through the local FFmpeg assembler, which is now
        # the default path. If you route a kids render back through JSON2Video,
        # switch to Young Jamal (6OzrBCQf8cjERkYgzSg8).
        "suggested_voice": "OOk3INdXVLRmSaQoAX9D",
        "suggested_model": "v3.0",
    },
}


def resolve_style(style_id):
    """Return a style pack dict. Unknown/blank ids fall back to the default —
    this endpoint is public, so never raise on user input."""
    if isinstance(style_id, str):
        key = style_id.strip().lower()
        if key in STYLE_PACKS:
            return STYLE_PACKS[key]
    return STYLE_PACKS[DEFAULT_STYLE]


def style_list():
    """Catalog for the UI picker (GET /v9/api/styles, GET /custom/api/styles)."""
    return [
        {
            "id": p["id"],
            "name": p["name"],
            "audience": p["audience"],
            "blurb": p["blurb"],
            "suggested_voice": p["suggested_voice"],
            "suggested_model": p["suggested_model"],
        }
        for p in STYLE_PACKS.values()
    ]


def apply_subtitle_style(settings, pack):
    """Overlay a pack's subtitle overrides onto the engine's computed settings.

    `font_size_bump` and `max_words_delta` adjust the aspect-ratio-derived values
    rather than replacing them, so 9:16 stays readable on a phone.
    """
    overrides = dict(pack.get("subtitles") or {})
    bump = overrides.pop("font_size_bump", 0)
    delta = overrides.pop("max_words_delta", 0)
    out = dict(settings)
    out.update(overrides)
    if bump:
        out["font-size"] = int(out.get("font-size", 70)) + bump
    if delta:
        out["max-words-per-line"] = max(2, int(out.get("max-words-per-line", 3)) + delta)
    return out
