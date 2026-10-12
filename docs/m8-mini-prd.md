# Milestone 8 mini-PRDs — Story Moments, Living Worlds and Cinematic Studio

Status: proposed; implementation requires explicit approval for each slice.

## M8.1 — Story Moments and Living Worlds

Goal: add optional, deterministic staging and looping environmental animation without changing static worlds by default.

Scope:

- A new Story workspace with three local presets: Quiet Morning, Busy Market, and Rainy Evening.
- Preview before apply, including affected objects, frame range, and keyframe count.
- Stage only CozyVerse-managed characters and props; never reposition user objects or protected objects.
- Create a dedicated `CV_STORY` collection and named Blender Actions for character idle motion, foliage sway, precipitation travel, and optional practical-light pulse.
- Use ordinary keyframes, Actions, and timeline markers. Do not use generated Python, drivers, simulation baking, or external services.
- Apply creates a new animation layer/state and supports Blender Undo. Clear Story removes only data tagged with the matching CozyVerse story identifier.
- Default frame range: 1–120 at 24 fps. Loop endpoints are deterministic.

Acceptance criteria:

- A static world remains byte-for-byte unchanged in its object transforms and animation data until the user explicitly applies a reviewed Story plan.
- Preview creates no objects, keyframes, Actions, markers, or timeline changes.
- Apply produces deterministic keyframes for the same world and preset.
- Protected objects and manually animated objects are skipped and reported.
- Clear Story removes only the selected story's tagged animation data.
- Background Blender tests verify preview purity, deterministic keyframes, skip rules, Undo-compatible operator flags, save/reopen persistence, and no effect on an unrelated static scene.

## M8.2 — Cinematic Studio

Goal: create an editable shot sequence after M8.1 is accepted.

Proposed scope: Wide Establishing, Hero Medium, and Detail Close-up cameras; timeline markers; editable shot durations; camera preview; no rendering farm or cloud service. This slice needs separate approval because it changes scene camera sequencing.

## M8.3 — Reviewed Export

Goal: export an explicitly reviewed world or shot range after M8.2 is accepted.

Proposed scope: `.blend` package copy plus optional glTF/GLB export to a user-selected path, with an export manifest and overwrite confirmation. No upload, publishing, or provider request. This slice needs separate approval because it writes external files and requires an agreed format contract.

## Explicit exclusions from M8.1

- No automatic lip sync, skeletal retargeting, crowds, physics simulation, audio generation, render queue, or external AI.
- No semantic interpretation of reference images.
- No mutation of prior static world versions.
- No export implementation before M8.3 approval.
