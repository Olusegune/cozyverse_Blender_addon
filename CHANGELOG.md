# Changelog

## 0.17.0 Magic Flow

- **Turntable** (Shot tab): one click parents the current camera to a small rig that orbits the world once on a seamless, linear, editable keyframe loop. Rebuild never duplicates it, and Remove puts the camera back exactly where it was, with no leftover objects or actions. Length is set in frames (default 120).
- **Pie menu** on Alt+W in the 3D View: Golden Hour, Moonlit, Rainy Evening, Misty Dawn, Blue Hour, Remix Layout, Next Shot and a Turntable toggle. With no world yet it offers Conjure and Surprise Me instead. Keys can be changed in Preferences > Keymap.
- One-click **Conjure World**: describe, press the button, get an approved, built, framed, Material-Preview-lit world with an animated reveal. Every build is still a new version; "Review the plan first" restores the old gated flow.
- Dice (Surprise Me, Ctrl builds it), **Remix Layout** (re-roll the layout, keep the plan), and a Shift+Alt+W quick-conjure popup from the 3D View.
- A single tabbed panel (Create, Mood, Shot, Motion, Assets, Activity, Settings) with a "What next?" guide after each build, native collapsible sections, icon galleries for Style and Look, live "reads as" feedback, and an inline prompt field.
- Mood tab: time-of-day chips, a live clock, and a time-of-day sky gradient backdrop.
- Shot tab: Wide, Hero, and Detail (depth of field) cameras created as separate cameras (the original is never moved), plus Render Postcard.
- Real Principled shader materials so EEVEE and Cycles renders match the viewport; windows glow in step with the practical lights.
- Fixed: rain and snow previews were visible on every fresh build; their transforms were also mistaken for hand edits.
- Fixed: Select and Frame now frames the diorama instead of the distant camera and lights.
- Added tests/blender_flow_smoke.py.
- The sidebar prompt now holds only your own words. The style directive is added once when the plan is made, so templates, Surprise and the composer no longer paste a long "Style direction" suffix into the field.
- Every composition family now has glowing parts: windows on houses, barns, towers, turrets and sci-fi modules, lanterns on market stalls, and beacons on tech and magic props.
- A new build hides earlier versions (viewport and render only, never deleted) so versions no longer stack on the same stage. Unhide them from the Activity tab.

## 0.16.0

- Added the approved M8.1 Story Moments workspace with large supplied artwork and Story/Animate/Timeline icons.
- Added zero-mutation preview plans with exact target, skip, frame, and keyframe counts plus fingerprint invalidation.
- Added deterministic Quiet Morning, Busy Market, and Rainy Evening native Blender Actions for characters, foliage, precipitation, and practical lights.
- Added per-world Story state, save/reopen persistence, locked/manual-animation preservation, and targeted Clear Story restoration.
- Added pure-Python and Blender integration tests; camera sequencing and export remain out of scope.

## 0.15.3

- Added and registered the supplied individual dark/light Story, Animate, Timeline, Shot, and Export icons.
- Kept these icons dormant until their corresponding M8 slices are approved and implemented.

## 0.15.2

- Reworked Quick Start into large two-column visual cards with explicit actions.
- Increased header and Style Studio artwork to full-width presentation scale.
- Replaced stacked Atmosphere/Season thumbnails with one large contextual preview that reacts to weather, wetness, wind, and season controls.
- Preserved native Blender layouts and icon fallbacks for reliable scaling and accessibility.

## 0.15.1

- Added the second supplied visual set for fog, snow, wind, wetness, four seasons, three Story Moments, three cinematic shot types, and the no-story empty state.
- Atmosphere and season previews now react to current controls; future Story/Cinematic art is bundled but remains inactive until its separately gated milestone is approved.

## 0.15.0

- Added offline reference composition analysis (aspect, brightness, contrast, warmth, focal point, and horizon cues) with explicit approximation disclosure.
- Added Blockout, Balanced, and Detailed reference interpretation levels.
- Added editable native world-volume fog, rain and snow meshes, a visible wind guide, wet material response, four seasonal foliage looks, and precipitation preview quality controls.
- Migrated atmosphere presets to schema 3.0 while retaining version 1 and 2 loading.
- Added pure-Python and Blender smoke coverage for the new controls.
- Integrated the supplied CozyVerse visual asset pack: branded header, visual Quick Start choices, live style/atmosphere previews, and image empty-state artwork with native icon fallbacks.
- Added supplied fog, snow, wind, wetness, Spring, Summer, Autumn, Winter, Story Moment, and cinematic reference artwork; weather and season previews now react to the current controls.

## 0.14.0

- Implemented Milestone 6 optional Tripo/Meshy generation and Asset Factory workflow.
- Corrected Tripo to its documented v2 API task endpoint and pinned v3.1 model contract.
- Updated Meshy to its current Text-to-3D v2 preview contract and documented PENDING-only cancellation behavior.
- Added exact-request fingerprints, estimated-credit display, user-set credit ceilings, paid-request consent and a final confirmation dialog.
- Added non-blocking provider submission, polling, cancellation where supported, and validated downloads without calling `bpy` from worker threads.
- Restricted model downloads to approved HTTPS hosts, GLB/GLTF paths, 100 MB, and valid binary GLB content.
- Added a complete zero-cost asynchronous mock lifecycle.
- Added isolated quarantine import, driver removal, inspection summaries, provider provenance and separately approved Asset Factory promotion.
- Added contract, budget, transport, download and Blender integration tests; no paid provider request was executed.

## 0.13.0

- Completed Milestone 5 safe revisions and beta hardening.
- Added fingerprinted previews of changed plan fields plus created, deleted, preserved, protected, and manually edited content.
- Invalidated approval whenever a reviewed plan changes.
- Kept revisions non-destructive by creating lineage-linked world versions with zero source deletions.
- Added explicit revision cancellation with no scene mutation.
- Added timestamped `.blend` recovery checkpoints that preserve the active file path.
- Added a bounded scene activity log with credential-pattern and session-secret redaction.
- Added pure-Python, Blender background, and real foreground Blender Undo coverage.

## 0.12.0

- Completed Milestone 4 Atmosphere Lab and Cozy Engine controls without rebuilding geometry.
- Added Bright Day and Blue Hour for six curated atmosphere looks.
- Added scene exposure plus practical-light enable, intensity, and 1,800–6,500 K color-temperature controls.
- Stored versioned atmosphere data independently on every CozyVerse world.
- Added saved-look loading when selecting a world and an explicit Load Saved action.
- Added safe migration from atmosphere preset schema 1 to schema 2.
- Kept rain as the existing demonstration and left fog, wind, wetness, and animated weather out of this milestone.
- Added pure-Python and Blender integration coverage for color temperature, exposure, practical lights, per-world looks, persistence, and migration.

## 0.11.0

- Added eight distinct procedural composition families: village, city, cafe, nature, space outpost, market, farm, and fantasy.
- Added deterministic prompt-seeded layouts so different prompts change placement while the same prompt remains reproducible.
- Added family-specific hero architecture, secondary structures, props, vegetation, paths, and landing pads.
- Added editable procedural characters and a dedicated `CV_CHARACTERS` collection.
- Added style-specific architectural treatment for Retro Sci-Fi, Gothic, Art Deco, and Cozy Fantasy.
- Added composition-aware orthographic or perspective camera positioning and lens choices.
- Gave every world version independent materials so later style changes cannot recolor earlier worlds.
- Added unit and Blender integration coverage for layout determinism, family diversity, characters, camera metadata, and material isolation.

## 0.10.0

- Added a searchable Asset Match & Placement workspace.
- Added deterministic filename categorization and tag extraction for local models.
- Added prompt-, scene-plan-, category-, and style-aware asset ranking.
- Added lightweight placement proxies with location, rotation, and scale controls.
- Added explicit per-asset import approval and a dedicated `CV_IMPORTED_ASSETS` collection.
- Added reviewed `.blend`, GLB/GLTF, OBJ, and available FBX import paths with provenance metadata.
- Removed imported object animation drivers and kept paid generation as an unused fallback.
- Added unit and Blender integration coverage for matching, approval gates, proxy placement, and `.blend` import.

## 0.9.0

- Replaced one-click creation with a guided Describe → Review Plan → Build workflow.
- Added a validated renderer-independent scene-plan schema and editable review controls.
- Added first-run guided example and local/no-cost onboarding messages.
- Added progress, actionable error, and recovery guidance surfaces.
- Added Select & Frame, reversible hide/show, and world-version management.
- Added generated-transform snapshots, manual-edit inspection, and explicit object protection.
- Made plan composition, counts, base shape, roads, vegetation, and camera affect local builds.
- Added unit and Blender integration tests for plan validation, approval gates, persistence, and edit protection.

## 0.8.0

- Added Style Studio with twelve validated visual-style presets.
- Added Retro Sci-Fi quick start and style-aware prompt generation.
- Made styles affect procedural material palettes and metallic treatment—not only prompt wording.
- Stored style labels and asset-search keywords on generated world collections.
- Added unit and Blender integration coverage for style prompts, palettes, metadata, and fallback behavior.

## 0.7.0

- Added an Image-to-World sidebar with local image selection and thumbnail preview.
- Added deterministic offline palette extraction and editable reference-based reconstruction.
- Added source provenance properties to reference-generated world collections.
- Added safe indexing for Blender Asset Library folders and an optional user-selected model folder.
- Added pure and Blender integration tests for the new local reference workflow.
- Kept image upload, AI vision analysis, automatic asset importing, and paid generation disabled.

## 0.6.0

- Replaced the tabbed sidebar with compact, collapsible workflow panels.
- Added a bounded structured Prompt Composer with clear Apply and Cancel actions.
- Added six quick-start world templates plus clipboard paste and prompt preview.
- Moved the full Blender Text Editor into a clearly labeled advanced workflow.
- Added an explicit return shortcut hint to the advanced editor.

## 0.5.0

- Added official-contract request builders for Tripo v3 and Meshy text-to-3D v2.
- Added normalized submit/status parsers and strict HTTPS GLB/GLTF download-host validation.
- Added a Generate workspace with request preview, cost warning, payload fingerprint, explicit approval, and zero-cost mock execution.
- Added provider contract tests; live billable submission remains disabled pending asynchronous job and import review.

## 0.4.0

- Added a full-area multiline prompt workflow using Blender's Text Editor and a guided return action.
- Added a wrapped prompt preview, numbered creation flow, stronger native iconography, and clearer action hierarchy.
- Added separate masked session-only Tripo and Meshy credential fields and local setup validation.
- Kept all 3D provider requests disabled until cost preview and per-job consent are implemented.

## 0.3.0

- Added a visible Build World workflow with optional multiline Blender Text prompt editing.
- Replaced the flat placeholder demo with an editable sari-sari-store diorama organized under named `CV_WORLD` collections.
- Added Atmosphere Lab presets and functional time, sunlight, warmth, ambient-light, and interior-light controls.
- Added a deterministic editable rain mesh with working Clear and Rain preview states.
- Preserved previous generated worlds, manually edited objects, and unrelated scene objects on subsequent builds.
- Expanded pure-Python, Blender background, save/reopen, secret-safety, and visual-render tests.

## 0.2.0

- Refined the sidebar into sleek Create, Activity, and Settings workspaces using theme-aware native controls.
- Added masked session-only API key entry and local configuration validation without provider calls.
- Added a user guide and credential-safety documentation.

## 0.1.0

- Added Blender extension manifest and native registration lifecycle.
- Added CozyVerse 3D View sidebar, prompt, preset, status, and settings.
- Added deterministic offline demo generation using editable Blender-native data.
- Added pure-Python tests, Blender background smoke test, installation instructions, and documentation audit.
- Added no network, provider, credential, or model-authored code execution capability.
