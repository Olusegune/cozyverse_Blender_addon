# CozyVerse Builder User Guide

The sidebar now includes bundled visual previews for the current style and supported atmosphere looks, illustrated Quick Start buttons, a branded header, and an image empty state. These are interface previews only, not 3D assets. Blender-native controls remain available when a preview cannot load.

## Start in under a minute

1. Install the CozyVerse ZIP through **Edit > Preferences > Get Extensions > Install from Disk**.
2. In the 3D View, press `N` and select the **CozyVerse** tab.
3. Expand **Create World**, choose a template or select **Compose Detailed Prompt**, and choose a style.
4. Select **Review World Plan**, edit the proposed contents, and confirm **I reviewed this plan**.
5. Select **Build New Version**.
5. Open `CV_WORLD` in the Outliner and edit its meshes, lights, materials, and camera normally.

The current foundation build is deterministic and offline. It creates a demonstration from Blender primitives so you can evaluate the interaction without an account, API key, or paid service.

## Sidebar sections

### Create World

Creation follows three visible steps: **Describe**, **Review**, and **Built**. Choose a quick-start template, paste a prompt, or select **Compose Detailed Prompt**. The composer is a bounded dialog with Setting, Subject, Mood, Details, Avoid, and Style fields plus clear **Apply Prompt** and **Cancel** actions.

Select **Review World Plan** before building. CozyVerse proposes an editable composition, base shape, camera type, number of buildings, props, plants and characters, and whether the scene needs a road or main path. This step creates no Blender objects. Review the proposal, enable **I reviewed this plan**, and select **Build New Version**.

#### Safe revision preview

The review step includes a fingerprinted safety summary before approval. It reports plan fields that changed, estimated new objects, objects that will be deleted, objects preserved in the source version, protected objects, and detected transform edits. CozyVerse revisions always report zero deletions because applying a revision creates a new `CV_WORLD` version.

If any reviewed plan field changes, the previous approval becomes invalid. Select **Refresh Preview**, review the new summary, and approve again. **Cancel** discards the pending preview without changing Blender objects. A completed world records its source version, approved preview, and plan fingerprint as collection metadata.

Every build creates a new numbered `CV_WORLD` collection. Existing versions and manual edits are never overwritten. The scene plan is saved as structured JSON on the collection; it is data, not executable Python.

#### Procedural composition families

The reviewed **Composition** field selects one of eight real construction families: Village, Urban Street, Cafe, Landscape, Space Outpost, Market, Farm, or Fantasy. These families change the generated architecture, hero object, roads or paths, props, vegetation, camera position, and set dressing—not only the labels or colors.

Object placement is deterministically seeded from the prompt and composition. Building the same approved plan produces the same layout; changing the description produces a new arrangement. The generated collection records `cv_composition_family`, `cv_composition_label`, `cv_layout_seed`, and `cv_architecture_treatment`.

Character count now produces simple editable miniature figures under `CV_CHARACTERS`. Characters are native Blender mesh parts and are intended as local placeholders until replaced with approved library assets.

Certain styles also change architectural construction. Retro Sci-Fi uses modular domed structures and antennas, Gothic and Cozy Fantasy use turret forms, and Art Deco uses stepped tower forms. Every world owns independent materials, so changing styles in a new version cannot recolor earlier versions.

After building, use **Select & Frame World** to locate the result. **Protect Selected** marks selected generated objects as explicitly locked. **Check Edits** reports objects whose transforms have changed since construction.

For unusually long free-form prompts, **Open Full Text Editor** creates a `CV_World_Prompt` Text datablock and switches the current area to Blender's Text Editor. Select **Use Prompt and Return**, or press **Shift+F5** to return to the 3D View. This is deliberately labeled as an advanced path.

#### Style Studio

Choose a visual style before building, or choose it directly inside **Compose Detailed Prompt**. Available styles are Cozy Village, Retro Sci-Fi, Cozy Fantasy, Solarpunk, Cyberpunk, Storybook, Low-Poly, Clay Miniature, Paper Craft, Art Deco, Gothic, and Tropical.

Styles affect the generated prompt, negative constraints, procedural material palette, metallic treatment, collection metadata, and asset-search keywords. For example, **Retro Sci-Fi** requests rounded modules, antennae, enamel panels, and optimistic analog technology while avoiding modern minimalism and excessive cyberpunk clutter. The generated world records `cv_style_label` and `cv_asset_keywords`, making the style available to the upcoming asset matcher.

The **Retro Sci-Fi** quick-start button fills the world-description fields and selects the matching style automatically. All generated prompt text remains editable before building.

### Atmosphere

Choose Golden Hour, Rainy Cafe, Moonlit, Misty Dawn, Bright Day, or Blue Hour, or adjust the controls directly. Time of Day rotates the real `CV_Sun`; sunlight, warmth, ambient light, and Exposure update Blender light, World, and color-management properties. Practical Lights can be enabled independently, with editable intensity and color temperature from 1,800 K to 6,500 K. These changes never rebuild geometry.

Atmosphere changes target the active world shown at the top of the panel. The controls update immediately. **Apply to Active** reruns the complete mapping, **Reset** returns to Golden Hour, **Save Look** stores versioned JSON in the scene and active world, and **Load Saved** restores it. Selecting a different world in **Activity & Safety** restores that world's saved look. Version 1 and 2 look data is validated and migrated to schema 3 when loaded.

Choose Clear, Rain, Fog, or Snow. Rain and snow are editable preview meshes inside the active world's atmosphere collections; Preview Quality changes their bounded density. Fog uses the Blender World volume input. Wind displays an editable direction guide and stores its strength on `CV_Wind`. Wetness reduces roughness only on materials owned by the active CozyVerse world. Season recolors that world's foliage to Spring, Summer, Autumn, or Winter. These are art-direction previews rather than physical weather simulation or animation.

Atmosphere Lab shows supplied visual references for fog, snow, wind, wet surfaces, and all four seasons. The images communicate the intended mood; they do not replace the editable Blender implementation or promise identical rendered geometry.

### Image to World

Choose a PNG, JPEG, WebP, or TIFF and click **Analyze Composition Locally**. The image stays on your machine. CozyVerse samples its palette plus aspect, brightness, contrast, warmth, focal position, and an approximate horizon, then labels the inferred day/dusk/night direction. Choose **Blockout** for the cheapest viewport preview, **Balanced** for everyday work, or **Detailed** for more editable objects, then click **Create Editable Interpretation**.

This is deliberately an approximation: local analysis does not identify exact houses, characters, streets, or props. It creates a composition-aware, editable starting point and records its source cues and quality on the world collection. Use Asset Match & Placement to replace procedural stand-ins with your own models.

Choose a PNG, JPEG, WebP, or TIFF diorama reference. CozyVerse loads it locally and displays a preview. **Extract Color Palette** samples the image inside Blender; it does not upload the image. **Create Editable Interpretation** builds a new native Blender world using deterministic geometry and the extracted palette. This is an editable artistic interpretation—not exact single-image geometry reconstruction.

The resulting world collection records the local reference path and reconstruction mode for provenance. External vision analysis remains disabled until an approved milestone adds an inspectable scene plan, privacy review, and explicit upload consent.

### Activity

Review the last operation, offline-engine state, and latest build prompt. A success message means Blender completed the operator; suggestions or text alone never imply that the scene changed.

The **World Versions** list shows up to eight recent CozyVerse worlds. Select a version to make it active and frame it in the 3D View. The eye button hides or shows a version without deleting it. CozyVerse does not offer destructive deletion from this panel.

The **Redacted Activity Log** keeps the latest 50 milestone operations in the scene. Credential-shaped values and loaded session keys are removed before storage. This log is intended for recovery context, not provider request bodies.

### Recovery checkpoints

Save the project normally once, then select **Create Recovery Checkpoint** from the completed-world or Activity panel. CozyVerse writes a timestamped `*.cv-checkpoint-*.blend` copy beside the active project without changing the current file path. Restore it explicitly with **File > Open** if needed. Unsaved projects receive an actionable prompt instead of writing to an arbitrary location.

Blender Undo is also enabled on build operators. Undo immediately after an approved revision removes the new version while leaving the source version intact. Once you continue editing, prefer a checkpoint because Blender's global undo history is sequential and cannot independently remove an older operation while retaining every later edit.

### Recovery messages

The Create panel displays operation progress, the exact failure when an action cannot continue, and a recommended next step. A rejected build usually means the plan was not approved or contains invalid values. Return to the plan, correct the highlighted values, and build again; earlier worlds remain untouched.

### Connections & Settings

Choose Local Only or configure fields for a future AI provider adapter. The foundation validates only whether the required fields exist. It does not contact a provider.

The 3D Generation section provides separate masked session fields for Tripo and Meshy. Select a provider and use **Check Setup Locally** to confirm that its key is loaded. This check never contacts Tripo or Meshy. Generation submission remains disabled until a later approved adapter adds request previews, estimated cost, explicit per-job consent, polling, cancellation, download validation, and provenance.

Under **Your Asset Sources**, CozyVerse can index Blender Asset Library folders already configured in Blender and one optional local folder. Supported files are `.blend`, `.glb`, `.gltf`, `.fbx`, and `.obj`. Indexing reads filenames only and does not open model files.

### Asset Match & Placement

1. Configure a local folder or enable your configured Blender Asset Libraries.
2. Select **Index Local Sources**. CozyVerse derives human-readable names, categories, and search tags from filenames and folders.
3. Enter optional search terms, choose a category, and select **Find Best Matches**. Ranking considers the current prompt, scene-plan title and composition, visual-style keywords, and your search.
4. Select a result. Review its source, format, category, and tags.
5. Set location, rotation, and scale, then choose **Preview with Proxy**. The wireframe proxy is safe and does not open the source file.
6. Enable **I approve importing this local asset** and choose **Import Approved Asset**.

Imported content is placed under `CV_IMPORTED_ASSETS` and wrapped in a transform object named `CV_ASSET_*`. The wrapper records the source path, category, and `user_approved_local_asset` provenance. Imported objects remain editable. CozyVerse removes animation drivers from imported objects and does not execute generated Python.

`.blend`, GLB/GLTF, and OBJ are supported when their Blender importers are available. FBX depends on the importer included with the installed Blender version. A failed import leaves the existing world intact and reports a recovery message.

### 3D Asset Factory

The Generate workspace prepares an official-contract request for Tripo or Meshy. It shows the pinned model, current estimated credits, provider warning, and SHA-256 fingerprint for the exact payload. Previewing a request resets all earlier approvals.

Use **Start Safe Mock Job** first. Refresh it twice to exercise Pending, In Progress and Succeeded states without network access or credits. Download the mock result, approve quarantine import, inspect the reported object/vertex/material counts, then separately approve promotion to `CV_ASSET_FACTORY`.

For a live job, enter the provider key in Settings, set a maximum-credit ceiling at or above the displayed estimate, approve the exact paid request, and select **Review & Submit Paid Job**. A final dialog repeats the fingerprint, estimate and ceiling. Submission and status polling run asynchronously so Blender remains responsive. Tripo's verified contract does not expose cancellation; Meshy can delete and refund a PENDING task but rejects cancellation after it enters IN_PROGRESS.

Successful results are accepted only from approved HTTPS provider hosts, must identify GLB/GLTF output, and are limited to 100 MB. Downloaded GLBs are validated before persistence. Import requires approval and enters `CV_ASSET_QUARANTINE`; CozyVerse removes animation drivers and records provider, job, fingerprint and cost-estimate provenance. Promotion into the reusable `CV_ASSET_FACTORY` requires a second approval. Provider failure, rejection or cancellation does not modify the scene.

## API key safety

The **Session Key** field is masked and attached to Blender's runtime window manager. It is not stored in the scene, `.blend` file, source tree, or CozyVerse logs. You must enter it again after restarting Blender.

For automation, enter the name of an environment variable rather than the secret itself. Configure the environment variable outside Blender before launch. The current foundation records only the variable name and does not read or transmit its value.

Use **Clear Key** before screen sharing or handing the running Blender session to another person. **Validate Locally** checks the fields without sending a network request.

## Editability and recovery

- All demonstration geometry is ordinary Blender mesh data.
- The light and camera are standard Blender datablocks.
- Use Blender Undo immediately after generation to revert the operation.
- Save a normal `.blend` file to preserve the demo and non-secret CozyVerse settings.
- Uninstalling or disabling CozyVerse does not delete scene objects.

## Current limitations

- Live provider contracts were verified on 2026-10-12 but paid submissions were not executed during automated testing.
- Credit estimates are snapshots of provider documentation and are not guaranteed charges.
- Provider fields are checked locally; CozyVerse does not spend credits merely to validate a key.
- Multiline prompts use a Blender Text datablock rather than an embedded sidebar text area.
- Local asset matching uses filename and folder metadata; it does not generate thumbnails yet.
