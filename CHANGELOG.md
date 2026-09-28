# Changelog

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
