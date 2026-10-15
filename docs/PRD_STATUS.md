# CozyVerse Builder: status against the Master PRD v3

Written 15 October 2026, following section 13 of `MASTER_PRD.md`. Everything below was run on **Blender 5.2.2 LTS, Windows 11**. The add-on declares support from Blender 4.5, but **4.5 has not been run**. Status words follow the PRD: **working** (built, tested, and seen in the real Blender window), **partial**, **missing**, **untested**.

## Evidence

- 10 Blender background suites (`tests/blender_*_smoke.py`) and 15 pure-Python suites (`tests/test_*.py`) pass. The Blender suites exercise real scene data, drivers, saving and reopening, not just registered buttons.
- The add-on validates and builds as an extension package with `blender --command extension validate / build` (`cozyverse_builder-0.17.0.zip`).
- The panel was driven and screenshotted in the real Blender GUI (Create, Review, Built, Mood, Shot, Motion, Assets tabs, the pie menu). These are my own captures, not a recorded human walkthrough.
- **Never run against a live service:** Tripo, Meshy, Anthropic and OpenAI-compatible calls. Their request building, response parsing, error handling and key redaction are tested against faked network functions only. Per PRD section 11, real provider tests need your explicit authorisation and a key.
- `blender_undo_smoke.py` cannot run headless (`ed.undo` needs a UI context), so native Undo is **untested** beyond operators carrying the undo flag.

## P0: restoration and foundation

| ID | Status | Notes |
|---|---|---|
| CV-001 Installable | working | Registers and unregisters cleanly; extension builds. 4.5 untested. |
| CV-002 Visible prompt | working | Inline field, composer popup, multiline text editor. |
| CV-003 Describe, Review, Build | working | One-click Conjure, or review-first. Offline build gives base, buildings, road, plants, lights, camera, named collections. |
| CV-004 Review quality | working | Review shows the Director's plan: assumptions, what comes from your library, what is built procedurally, what could be generated with an estimated cost, and what would leave the machine. |
| CV-005 Atmosphere essentials | working | Time, sun, warmth, ambient, practical lights, ten looks, weather, rain/snow/fog objects, clouds, stars. |
| CV-006 Safe edits | partial | Managed collections, working locks, archive instead of delete. Native Undo untested headless. |
| CV-007 Save and reopen | working | Tested for worlds, drivers, plans, library choices. |
| CV-008 Assets | working | Multiple folders, recursive scan, search, roles, licences, generated thumbnails. |
| CV-009 UX verification | partial | Screenshots from the real GUI; no screen recording or human walkthrough. |

## P1: intelligent director and creation

| ID | Status | Notes |
|---|---|---|
| CV-101 World DNA | partial | Twelve styles with palettes and architecture forms. No scale system or cultural references. |
| CV-102 Local asset intelligence | partial | `.blend` (asset-marked collections), `.glb`, `.gltf`, `.obj` import; FBX untested. Roles, licences, thumbnails. No dimension index. |
| CV-103 Scene composer | partial | Free-ground placement avoiding water, slopes, roads and other objects; hills, lakes, rivers, seas. No Geometry Nodes scattering. |
| CV-104 AI Director | working offline, untested live | Versioned Scene Blueprint with strict validation; allowlisted follow-up commands; plan diff and confirmation; locks respected; archive instead of delete; offline planner and reader. Anthropic and OpenAI-compatible adapters are only tested with a faked network. |
| CV-105 Atmosphere expansion | partial | Cloud, fog volume, snow, rain, wind sway, wetness, preview quality levels. No performance warnings. |
| CV-106 Seasons | partial | Four seasons change foliage and freeze water. No per-object overrides or climate-aware fallbacks. |
| CV-107 Asset Factory | partial | Tripo and Meshy adapters with cost estimate, explicit consent, quarantine import and promotion, tested with a mock. The Director hands items to it one at a time ("Prepare generation"); there is no batch generation. |
| CV-108 Reference-to-World | partial | Local palette and composition analysis. With your consent a reduced copy of the image can go to an AI model. No reconstruction, as the PRD intends. |

## P2: story, animation, cinema, export

| ID | Status | Notes |
|---|---|---|
| CV-201 Story Moments | partial | Three presets animate characters, foliage, rain and lamps. No staging of new characters or props. |
| CV-202 Living Worlds | partial | Plant sway, lamp flicker, moving water, drifting clouds, cars, a train, build-up animation. No smoke. No bake option. |
| CV-203 Cinematic Studio | partial | Wide, hero and detail cameras with depth of field, turntable, clip rendering. No saved shot list or transitions. |
| CV-204 Export | partial | Postcard stills and MP4 clips. No 3D export and no export validation. |
| CV-205 Project versions | partial | Every build is a new version; older ones hide and can be restored; recovery checkpoints. No named snapshots. |

## Known limitations and risks

- Tripo and Meshy request schemas and model names came from earlier work and have **not** been checked against the providers' current documentation or a live call.
- The offline planner reads keywords. It is deterministic and safe, but it is not intelligent; the AI path is what adds understanding.
- Image understanding is only as good as the model you choose; nothing here reconstructs geometry from a picture.
- The sidebar is narrow; a few labels shorten in the Blender UI.

## Live provider testing

`tools/live_provider_check.py` (see `docs/LIVE_TEST.md`) runs one real planning call, one real follow-up call, and one capped real 3D generation. It reads keys only from environment variables, shows exactly what would be sent, and needs a typed YES. Its own logic is tested offline (`tests/test_live_provider_check.py`); **it has not yet been run against a live service**, because no key was available on this machine.

## Proposed next single milestone

Run a **real provider test with your authorisation** (one Anthropic or OpenAI-compatible plan call, then one Tripo or Meshy generation within a small credit cap), and fix whatever the live services reveal. After that: batch generation from the Director's plan.
