# Biblical Cinematic — Build Error Log

Running log of bugs hit during development. Kept here so we don't fix the same issue twice.
Archive this file when the app reaches full production.

---

## [2026-06-15] "Generate ALL Sections" → `Unexpected token '<', "<!DOCTYPE"` — single giant Claude call overflowed both the token cap and the proxy timeout

**Symptom:** Generating scenes for a large chapter ("Generate ALL Sections", ~2,252 words) failed in the browser with `Unexpected token '<', "<!DOCTYPE "... is not valid JSON`. The frontend got an HTML page where it expected JSON.

**Root cause (two compounding bugs, same design flaw):** `generate_image_prompts()` made **one** Claude call for *all* scenes (intro + N scripture + outro). For a full chapter that's 75+ scenes in a single request, which broke two ways:
1. **Token overflow → truncation.** `max_tokens: 8000` couldn't hold the JSON for 36+ scenes. Claude's output was cut off mid-string, so the server's `json.loads()` raised `Unterminated string starting at: line 210 column 22` → HTTPException 500. Confirmed by hitting the **Modal upstream directly** (bypassing Cloudflare) with ~1,081 words: `500 {"detail":"Unterminated string ..."}` after 153s.
2. **Latency → proxy 524.** The same call ran >100s. Through anointed.app the **Cloudflare Worker proxy** (free tier, ~100s origin-response limit) returns its **524 HTML error page**, which the frontend's `res.json()` choked on → the `<!DOCTYPE` error. (Direct-to-Modal showed the 500; through the proxy you only ever see the HTML 524.)

**Fix (two parts):**
1. **Batch the Claude calls.** `generate_image_prompts()` now splits scenes into `PROMPT_BATCH_SIZE = 12` per call via `_request_prompt_batch()` (intro on the first batch, outro on the last). Each call's output stays well under 8000 tokens — no truncation. Narration is merged **per batch** so a miscount in one batch can't shift alignment in the next.
2. **Run generation in the background + poll.** `/v9/api/generate-scenes` now spawns a daemon thread (`_run_scene_generation`), sets `phase="generating_scenes"`, and returns `{"status":"started"}` immediately — the HTTP response no longer blocks for minutes, so it never trips the proxy's 100s limit. The browser polls `/v9/api/status` (new `pollForScenes()` in app.py, 2s interval, 6-min ceiling, tolerant of transient non-JSON and Modal sibling-container idle-without-scenes windows). Mirrors the existing video-pipeline pattern.

**Verified live via anointed.app:** 1,081-word input → `{"status":"started"}` instantly, polled through 202s (well past the 100s CF limit), finished `phase=idle, scenes=38 (intro=1, scripture=36, outro=1)`. The input that previously 500'd/524'd now succeeds.

**Lesson:** Any synchronous endpoint behind the Cloudflare proxy has a hard **~100s wall** — long LLM work must be backgrounded + polled, not awaited in the request. And one-shot "generate N items in a single call" patterns silently break once N grows enough to exceed `max_tokens` — batch them.

---

## [2026-06-15] Render 404s — hardcoded dated Claude model snapshot hit its retirement date

**Symptom:** Starting a video render failed at scene generation with `⚠ 404 Client Error: Not Found for url: https://api.anthropic.com/v1/messages`. The endpoint URL was correct, so it read like an endpoint/network problem.

**Root cause:** The scene-gen calls hardcoded the model ID `claude-sonnet-4-20250514` — a **dated snapshot** of Claude Sonnet 4. That snapshot was deprecated with a retirement date of **2026-06-15** (the day this hit). The Anthropic API returns **404 `not_found_error`** for a model ID it no longer serves — not a 400, not an auth error — which is why it masqueraded as a bad-endpoint problem. Auth issues would be 401; a typo'd-but-live model would also be 404, but here the ID was valid and simply retired.

**Fix:** Swapped every call site to the bare alias **`claude-sonnet-4-6`** (same tier/pricing as Sonnet 4, $3/$15 per 1M — no cost change; this step only generates structured scene prompts so Opus isn't worth the 1.7×). Six occurrences:
- `workflows/biblical-cinematic/server/biblical_pipeline.py` (production scene-gen)
- `workflows/custom-script/router.py`, `generate.py`, `server.py`, `recover.py`
- `scripts/heaven/generate_heaven.py`

**Lesson:** **Never hardcode dated Claude model snapshots** (`claude-*-YYYYMMDD`) — they retire on a published schedule and 404 with no code change on your side. Use the bare alias (`claude-sonnet-4-6`, `claude-opus-4-8`), which doesn't carry a hard retirement date. Requires a **redeploy** to take effect on Modal (model ID read at request time, but warm containers run old code).

**Follow-on (same day): read timeout after the model swap.** Once the 404 was fixed, the next render failed with `HTTPSConnectionPool(...): Read timed out. (read timeout=120)`. **Root cause:** Sonnet 4.6 supports adaptive thinking and **defaults to `effort: high`** — unlike the old dated Sonnet 4, which sent no thinking config and answered fast. The model now "thought" before generating scenes, pushing the call past the 120s `requests` timeout. **Fix:** added `"thinking": {"type": "disabled"}` + `"output_config": {"effort": "low"}` to every scene-gen payload (these are raw-HTTP `requests.post` calls, so the fields go straight into the JSON body — `effort` is GA on Sonnet 4.6, no beta header) and bumped the production call's timeout 120→300s. Scene-gen is structured prompt generation, not reasoning, so disabling thinking matches the old Sonnet-4 behavior with no quality loss. Verified live: `/v9/api/generate-scenes` went from >120s timeout to **33s**. **Lesson:** when migrating to a 4.6+ model, explicitly set thinking/effort for latency-sensitive structured-output calls — the new default-`high` effort can silently blow past existing timeouts.

---

## [2026-06-06] Public launch: auth fell OPEN, not closed — and enabling it would have locked out the public

**Symptom:** Production `/admin/waitlist` returned **200** to anyone — exposing signup emails, IPs, invite tokens, and paid-credit counts. The Basic Auth middleware existed but was never installed in prod.

**Root cause (two coupled problems):**
1. **Fail-open install guard.** The middleware was wrapped in `if _AUTH_USER and _AUTH_PASS:`. `APP_USERNAME`/`APP_PASSWORD` weren't in the Modal secret, so the entire middleware was skipped and the whole app — including `/admin/*` — was public. Missing config silently disabled security instead of denying.
2. **Wrong gating model for a public app.** Even if enabled as written, the middleware gated the *entire* app behind one password with only `/`, `/landing/*`, `/billing/*` allowlisted. That's correct for a personal tool but for the public marketing launch it would have 401'd every visitor the instant they hit `/v9/api/*`, `/custom/api/*`, or `/api/clean` — i.e. enabling auth would have broken the product. Non-obvious: the "fix" (add the two env vars) would have made the app unusable.

**Fix:** Inverted the model in [server/app.py](server/app.py) — "public app with a private `/admin/` zone" instead of "private app with a public allowlist":
- Middleware is **always installed** (no env guard).
- Requests outside `/admin/*` pass straight through (public).
- `/admin/*` requires valid Basic Auth, and **fails closed**: if `APP_USERNAME`/`APP_PASSWORD` are unset, it returns 401 rather than opening.
- Still requires a **redeploy** to take effect after setting the secret — the middleware reads env at import time, so warm containers keep old behavior (`modal app stop` then `modal deploy`).

Verified the gating logic with a pure-Starlette TestClient harness (creds unset → `/admin/*` 401, public routes 200; creds set → admin needs correct Basic Auth) since the full FastAPI app can't boot on this machine (see next entry).

**Files changed:** `workflows/biblical-cinematic/server/app.py`.

---

## [2026-06-06] Local server won't boot on this desktop — Python 3.14 env is broken (not a code bug)

**Symptom:** `python app.py` crashes at `app = FastAPI(title="Anointed")` with `TypeError: Router.__init__() got an unexpected keyword argument 'on_startup'`. Happens before any app code runs.

**Root cause:** The machine's system Python 3.14 has **starlette 1.2.1** installed alongside **fastapi 0.115.0**. That starlette dropped the `on_startup`/`on_shutdown` Router kwargs that fastapi 0.115 still passes. There's no project venv, so the server runs against this mismatched global env. Worse, **pip is also broken** on this Python 3.14 (`RecursionError: maximum recursion depth exceeded` in `ssl.py verify_mode`), so you can't `pip install` a compatible starlette to fix it — even with the sandbox disabled.

**Workaround / TODO:** Local full-server smoke testing is blocked until the Python env is repaired (create a clean venv with a working pip, or pin `starlette<0.39`). For now, static checks (`python -m py_compile app.py`, grep for dangling refs) + isolated logic harnesses cover what they can; final runtime verification happens on Modal (which builds its own correctly-pinned image from requirements.txt). Modal deploys are unaffected by this local breakage.

---

## [2026-04-19] Stop button does nothing on Modal + pipeline freezes silently

**Symptom:** User clicks **Stop Rendering** mid-render on the deployed Modal app. API responds `{"status": "stop_requested"}` but the pipeline keeps running. Later the render pauses/errors on its own. After the container scales down, `/api/status` returns `phase=idle, scenes=null, processed=[]` — all in-memory pipeline state is gone even though 3 of 6 Kling clips were already paid for.

**Root cause (two layers):**

1. **Stop flag was process-local.** Both `biblical_pipeline.py` and `custom-script/router.py` declared `stop_requested = threading.Event()` at module level. On Modal, the web app can run in multiple containers under concurrent load. When `/api/stop` load-balances to a container that isn't the one running the worker thread, setting the Event in container A has zero effect on the worker in container B. Same failure mode as the multi-container `pipeline_state` issue — in-memory state doesn't cross Modal container boundaries.
2. **Custom-script pipeline doesn't persist state.** Biblical pipeline persists `pipeline_state` to `/data/pipeline_state.json` and survives restarts. Custom-script only keeps state in RAM. When the container scaled down after 5 min idle, everything — the 6 scenes, the 3 completed Kling URLs, the fix panel state — was lost. Recovery required pulling video URLs from fal.ai's history API.

**Fix:**
- Added disk-backed stop flags on the shared `/data` volume: `biblical_stop.flag` and `custom_stop.flag`.
- Added `is_stop_requested()` / `request_stop()` / `clear_stop()` helpers in both files. `is_stop_requested()` returns `stop_requested.is_set() or STOP_FILE.exists()` — the Event stays for fast-path single-container checks, the file covers multi-container.
- `/api/stop` now calls `request_stop()` which writes to `/data/<kind>_stop.flag`. The flag is visible to every container because the Volume is mounted everywhere.
- All in-pipeline stop checks (`stop_requested.is_set()` call sites inside FLUX/Kling poll loops and between scenes) now call `is_stop_requested()`.
- `clear_stop()` at module init purges stale flags left by crashed/killed containers.

**What this does NOT fix (deliberate, out of scope):**
- Concurrency: two users rendering simultaneously still collide on the global `pipeline_state` dict. That's the multi-tenant refactor deferred to the SaaS roadmap.
- Already-submitted fal.ai / JSON2Video jobs continue on the vendor side even after local stop — those credits are spent. Cancellation would require hitting each vendor's cancel API per pending request.
- Custom-script pipeline still doesn't persist to `/data` between container restarts. Added a one-shot recovery script instead: `workflows/custom-script/recover_run.py` reads a scenes JSON (exported from the browser's `currentScenes` JS variable), pulls the most-recent N successful Kling clips from fal.ai history, regenerates the rest, and submits to JSON2Video.

**Files changed:** `workflows/biblical-cinematic/server/biblical_pipeline.py`, `workflows/custom-script/router.py`, `workflows/custom-script/recover_run.py` (new).

---

## [2026-03-11] JSON2Video error: "Voice generation failed: No text provided" on Scene 20

**Symptom:** JSON2Video render fails with error: `Scene #20, element #2: Voice generation failed: No text provided`. Video consumed 130 credits but produced no output.

**Root cause:** Perplexity generated only 19 scenes instead of 20. The Build Template Vars code pads to 20 scenes but fills scene 20 with empty strings (`voiceOverText: ""`, `overlaidText: ""`). The JSON2Video template is hardcoded to 20 scenes, each with an ElevenLabs voice element. ElevenLabs rejects empty text.

**Also noticed:** `scene19_videoUrl` and `scene20_videoUrl` were identical (padding reused last scene's URL), confirming scene 20 was a hollow pad.

**Fix:** Added **Step 4b** to Build Template Vars — after text balancing, scans all 20 scenes for empty `voiceOverText`. If found, splits text from the nearest previous scene (at sentence boundary, 50/50 split) to fill the empty scene. Also auto-generates `overlaidText` from first 5 words of the overflow. This ensures every scene sent to JSON2Video has valid voice text.

**File changed:** `n8n/v8.0-kling.json` → Build Template Vars Code node

---

## [2026-03-10] Last scene loops endlessly — uneven Perplexity text distribution

**Symptom:** Final rendered video gets stuck on the last scene. The 5-second Kling clip loops 10-13x while a massive narration plays. Earlier scenes have 6-20 words while scene 20 has 90-156 words.

**Root cause:** Perplexity sonar-pro ignores the "20+ words minimum" voiceOverText constraint and distributes text unevenly — stuffing the last few scenes with all remaining verses. A 5-second Kling clip looping for 68 seconds of narration looks broken.

**Fix:** Added text-balancing logic to the **Build Template Vars** code node (all 4 workflow files):
1. Forward pass (scenes 1-19): any scene over 55 words splits at the nearest sentence boundary (period + space), overflow pushed to the next scene
2. Scene 20 special: overflow pushed **backward** into scene 19 (since there's no scene 21)
3. Fallback: if no sentence boundary found after 55 words, tries after 25 words, then hard-splits at word boundary
4. Debug output includes `wordCounts` per scene for verification

**Also added** (but insufficient alone): Perplexity prompt now says "20-60 words per scene, NEVER exceed 60 words" and "distribute EVENLY" — but Perplexity doesn't reliably follow these constraints, so the code-level fix is the real solution.

**Files changed:** `n8n/v8.0-kling.json`, `n8n/models/v1.6-standard/*.json`, `n8n/models/v2.1-standard/*.json`, `n8n/models/v3-standard/*.json`

---

## [2026-03-08] "Not all elements have metadata" — 8 consecutive render failures

**Symptom:** Eight render failures after modifying template. Error after 671 seconds: "Not all elements have metadata". Last successful render was March 7 at 18:42 using the baseline `h5.json`.

**Root cause:** Multiple template bugs introduced during v7.2 modifications:
1. **Missing `"duration": "auto"`** on all 20 image elements (JSON2Video requires this metadata)
2. **Title card with unsupported elements**: `rectangle` type and text `animation` sub-objects (not valid schemas)
3. **Stripped variables block** (removed `animation`, `motionType`, `animationDuration`, `easing`)
4. **Variable name mismatches**: referenced `scene1_zoomStart`/`zoomEnd`/`panStart`/`panEnd` but n8n sends `scene1_zoom`/`scene1_pan`/`scene1_panDistance`
5. **`pan: ""` empty strings** for zoom-only scenes (invalid JSON2Video pan value)

**Fix:** **Reverted to the proven working baseline `h5.json`** (the exact template structure that rendered successfully at 18:42). Copied it to `JSON2Video-Template-v7-Phase1_no_card.json` with only the template ID and comment updated. This is 100% structurally identical to the template that worked.

**Prevention:**
- **Never modify a working template.** The baseline is sacred.
- **Test new features in isolation first** (e.g., test title card in a separate template before merging)
- **Always verify template structure matches n8n variable names** before uploading
- **Validate empty pan/zoom values** — all must be valid enum values or scalars

**Files:**
- **Source baseline:** `Checkworking/h5.json` (reference only)
- **Current production:** `templates/JSON2Video-Template-v7-Phase1_no_card.json` (copy of h5.json, template ID `h5yD4ZbxhCPNFQ2WoVUs`)
- **Broken/archived:** `archive/releases/RELEASES/v7.2-broken-templates/JSON2Video-Template-v7-Phase1.json` (DO NOT USE)

---

## [2026-03-07] JSON2Video rejects rectangle elements in scenes

**Symptom:** Title card fails with `Object [movie/scenes[0]/elements[1]] does not match any of possible schemas: rectangle`

**Root cause:** JSON2Video does not support `type: "rectangle"` inside scene elements. The title_overlay and title_divider elements caused the entire scene to be rejected.

**Fix:** Removed both rectangle elements. Text readability maintained via heavy `shadow-offset` on text elements + enforcing a dark background in the FLUX image prompt.

**Prevention:** Do not use `type: "rectangle"` in JSON2Video scene elements. For overlays/dividers, rely on image prompt darkness and text shadows instead.

---

## [2026-03-07] Template zoom/pan variables mismatched with n8n output

**Symptom:** All Ken Burns motion on scenes 1–20 was silently ignored — images rendered static.

**Root cause:** Template referenced `scene1_zoomStart`, `scene1_zoomEnd`, `scene1_panStart`, `scene1_panEnd` but n8n sets `scene1_zoom` (integer) and `scene1_pan` (string). Variables never resolved so zoom/pan defaulted to no motion.

**Fix:** Updated template to use `{{scene1_zoom}}`, `{{scene1_pan}}`, `{{scene1_panDistance}}` matching what n8n actually outputs.

**Prevention:** When changing n8n variable names, always cross-check against the JSON2Video template variable block.

---

## [2026-03-02] Ghost server blocking port 8000

**Symptom:** New server wouldn't bind to port 8000. `taskkill /F /PID <pid>` returned "process not found" but port was still occupied and serving old content.

**Root cause:** The server process was orphaned — its parent shell exited (context window ended) but the process kept running. Windows `taskkill` can't kill processes that have been orphaned from their original session in some cases.

**Fix:**
```powershell
# Kill specific PID via PowerShell (more reliable than taskkill):
Stop-Process -Id <pid> -Force

# Nuclear option — kill all Python:
Get-Process python | Stop-Process -Force
```

**Prevention:** Always use PowerShell `Stop-Process` when `taskkill` fails.

---

## [2026-03-02] Server serving stale HTML after code update

**Symptom:** After rewriting `app.py`, the server kept returning the old HTML even after restarting with a fresh `__pycache__`.

**Root cause:** `uvicorn.run("app:app", reload=True)` uses `multiprocessing.spawn` on Windows to create worker processes. The spawned worker imported a cached/old version of the module instead of reading the updated file.

**Fix:** Changed to `uvicorn.run(app, reload=False)` — no multiprocessing spawn, single process, always reads what's on disk at startup.

**Prevention:** Never use `reload=True` on Windows for this project. Restart manually after editing `app.py`.

---

## [2026-03-02] JSON2Video API key not loading — `realtime: false`

**Symptom:** `/api/status` kept returning `realtime: false`. Direct API calls to JSON2Video returned auth errors.

**Root cause:** `.env` had two entries for `JSON2VIDEO_API_KEY` — the placeholder on line 22 and the real key on line 28. `python-dotenv` uses the **first** occurrence, so the placeholder won (`your-json2video-api-key`). The server printed "✓ configured" anyway because a non-empty string is truthy.

**Fix:** Removed the duplicate placeholder line. `.env` now has one clean entry:
```
JSON2VIDEO_API_KEY=2CcHHheoC8loYYgL6TuAnpmgDJAhPfG9C7fwpdpY
```

**Prevention:** Only one entry per key in `.env`. If you need to update a key, edit the existing line — don't append a new one.

---

## [2026-02-XX] n8n generating "undefined" chapter content

**Symptom:** Perplexity received a prompt with "undefined" instead of the scripture text. Output scenes described "undefined chapter" content.

**Root cause:** The `Bible Chapter Text Input` Set node in n8n had `{{ $json.body.text }}` typed into the **field NAME** box instead of the **field VALUE** box. This created a weirdly-named field, and the downstream JS expression `$('Bible Chapter Text Input').item.json.inputText` returned `undefined`.

**Fix:** In the Set node:
- Field NAME = `inputText` (literal text, not an expression)
- Field VALUE = `{{ $json.body.text }}` (expression mode ON)

**Prevention:** In n8n Set nodes, always double-check which box (name vs value) you're typing expressions into. The expression toggle must be ON for the VALUE, not the NAME.

---

## [2026-03-07] Perplexity JSON parse failure — unescaped quotes in string values

**Symptom:** "Enhanced Format for 16:9 Template" node throws `Expected ',' or ']' after array element in JSON at position 20371`. Fails ~30-50% of runs, especially on chapters with dialogue (Matthew 12, etc.).

**Root cause:** Perplexity sonar-pro returns JSON with unescaped double quotes inside string values — e.g. `"the so-called "Pharisees" confronted him"`. The `"` around `Pharisees` breaks `JSON.parse()` because JSON requires `\"` for quotes inside strings.

**Why 7 previous fixes failed:** Heuristic quote repair cannot reliably distinguish structural quotes (`"key": "value"`) from embedded quotes (`"text with "quotes" inside"`). The patterns are identical without schema awareness.

**What was tried and failed (v7.1):** Added `response_format: { type: "json_schema" }` to the Perplexity request + rewrote `repairJson()` with charCode-based state machine. Still failed — Perplexity's `json_schema` requires Tier-3 access ($500+ spend) and is **silently ignored** on lower tiers. The state machine repair accumulates errors across 20 scenes and can't reliably distinguish structural from embedded quotes.

**Definitive fix (v7.2 — CONFIRMED WORKING):**
Field-name-anchored extraction — skips `JSON.parse()` for the fallback path entirely. The 4 field names (`overlaidText`, `voiceOverText`, `imagePrompt`, `motionDescription`) are guaranteed to never appear inside biblical text or image prompt values. Using `indexOf('"fieldName"')` as structural boundaries is therefore 100% reliable. Walks backwards from the next field name occurrence to find the closing quote of each value.

Two-pass flow:
1. Try `JSON.parse()` first (fast path, works ~50% of runs)
2. On failure → `extractScenes()` field-name-anchored extraction (immune to unescaped quotes)

**Prevention:** For any LLM that may return unescaped quotes inside JSON string values, use field-name `indexOf` anchoring rather than quote-state-machine repair. Heuristic repair of quote context is fundamentally unreliable.

---

## Archive note

When the app is fully in production (YouTube auto-upload working, stable for 30+ days), move this file to:
`workflows/biblical-cinematic/archive/ERRORS-build-phase.md`
