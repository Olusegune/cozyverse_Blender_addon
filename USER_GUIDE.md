# CozyVerse Builder User Guide

The sidebar now includes bundled visual previews for the current style and supported atmosphere looks, illustrated Quick Start buttons, a branded header, and an image empty state. These are interface previews only, not 3D assets. Blender-native controls remain available when a preview cannot load.

## Start in under a minute

1. Install the CozyVerse ZIP through **Edit > Preferences > Get Extensions > Install from Disk**.
2. In the 3D View, press `N` and select the **CozyVerse** tab.
3. Type a description (or press the dice for an idea), pick a style, and press **Conjure World**. The world is built, framed, lit and revealed in one step. Every build is a new version; nothing is ever overwritten.
4. Follow the **What next?** buttons: set the mood, frame a shot, bring it to life, or add your own models.

Shortcuts in the 3D View: `Alt+W` opens a pie menu (looks, remix, shots, turntable); `Shift+Alt+W` conjures from a small popup. Both can be changed under **Preferences > Keymap**. Turn on **Review the plan first** under *Fine-tune the prompt* if you want to inspect and approve a plan before anything is built.

## The workspaces

The panel has one row of tabs:

| Tab | What it does |
|---|---|
| **Create** | Describe, pick a style, conjure. After a build: remix the layout, start a new version, select and frame, protect and recover. |
| **Mood** | Ten one-click looks, time of day, weather, clouds and stars. **Advanced controls** reveals sun, wind, wetness, seasons, lamps and saved looks. **Animate a day** keyframes a seamless day-to-night loop. |
| **Shot** | Wide, Hero and Detail cameras (each is its own camera), a turntable orbit, **Render a clip**, and **Render Postcard**. |
| **Motion** | **Ambient life** (swaying plants, flickering lamps), the **build-up animation**, cars and a train with a station, and Story Moments. |
| **Assets** | Your **Library** of models with thumbnails, the classic catalog, reference images and the 3D Asset Factory. |
| **Activity / Settings** | Versions, recovery, the activity log, connections and keys. |

## What the new features do

- **Sky:** a gradient that follows the time of day, a warm glow at sunset, procedural stars on clear nights, and drifting clouds. Rain and snow bring heavy cloud and hide the stars. Fog is a soft box of mist around the stage, so the sky stays visible.
- **Water and land:** say "lake", "pond", "river", "canal", "harbor", "island" or "mountain" in your description, or choose **Water** and **Land** under the prompt. Lakes and ponds fill a back corner, a river runs between the road and the houses, and an island sits in a glass slab of sea. The water ripples with the timeline, reacts to wind, rain and the **Waves** slider (Mood tab), and freezes in winter. A sea island is too small for the train.
- **Build-up animation:** the diorama assembles itself in layers (stage, buildings, props, plants, characters) in *Pop*, *Rise* or *Drop* style. Move the two keys on `CV_BuildUp` to retime it; **Remove** restores everything exactly.
- **Ambient life:** swaying plants and flickering lamps run on safe built-in expressions, so they render and survive saving. They respond to the Wind slider.
- **Cars and train:** low-poly cars drive both lanes of a road; a train leaves a tunnel, stops at a small station, and leaves through the other tunnel. They loop forever on any frame range.
- **Render a clip:** builds the world up while the camera orbits it, and renders an MP4 next to your `.blend` (720p or 1080p). Everything is editable keyframes, so you can retime before rendering.
- **Library:** add any folder of `.blend`, `.glb`, `.gltf`, `.fbx` or `.obj` models (and Blender asset libraries). Models get real thumbnails, a role (Car, Tree, Street lamp, Building, Person, Prop), a licence flag, a front direction and an optional *flatten to clay colors* switch, and your choices are remembered between projects. **Place in World** stands a model on the ground at a size that suits its role. **Use as My Car** makes the cars on your road use your model, with a built-in fallback. Models marked *Editorial only* warn you before you render.

## The Director

The Director turns your description into a **plan**, then keeps editing the world when you ask.

- **Planning works offline.** Press Conjure and the Director reads your words: the kind of place, water and hills, the mood ("rainy", "dusk", "starry"), the season, whether cars or a train belong, and the specific things you named ("a sari-sari store", "a jeepney"). After the build it applies the mood and motion, uses **your own library models first** where one fits, and builds simple stand-ins for the rest. Big unique things it could not find are listed as **could be generated**, with an estimated cost, and a button fills in the 3D asset factory for you. Nothing is sent or charged until you review that there.
- **Review shows the plan** (turn on *Review the plan first*): where each thing comes from, any warnings, and the fields you can still edit.
- **Ask the Director** appears after a build. Type a change, or use a chip, and press **Preview Changes**. You see exactly what would happen. **Apply** makes the changes; **Ctrl+Z** undoes them.
  - "More flowers, less clutter, warmer" adds flowers on free, level ground, archives some props (hidden in `CV_ARCHIVE`, never deleted; *Bring back archived items* restores them) and warms the light.
  - Mood, weather, season, camera, motion, and sizes work the same way. "Add a lake" builds a **new version** and hides the old one.
  - **Locked objects are never moved, scaled or archived.** Use *Protect Selected* to lock the things you have placed by hand.
- **Plan with AI (optional).** In Settings choose a provider (Anthropic, OpenAI, or a custom OpenAI-compatible server, including one running on your own computer), set the model, and enter your key for this session. Then turn on *Plan with AI* under the prompt. Before anything is sent you see a list: the provider, the model, your description, and whether a reduced copy of your reference image goes too (off unless you tick *Include my reference image*). Follow-up requests send only a short summary of the world, never file names or paths. Your key travels in a header only and is never saved in the `.blend` or shown in logs.
- **What the AI can and cannot do.** Its answer is only ever data: it is checked field by field, clamped to safe ranges, and rejected whole if it contains anything that looks like code. It can never name files on your computer, and follow-ups are limited to a fixed list of commands. If the service fails or sends something unusable, you get the offline plan with a plain-words note.

## Your library and licences

CozyVerse only lists and previews your files; it never runs anything inside them and strips drivers from imported objects. Set each folder's licence once (the menu next to its name) and change single models as needed. Models are never copied into the add-on, so commercial packs stay on your machine.

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

### Story Moments

Build or select a CozyVerse world, then open **Story Moments**. Choose Quiet Morning, Busy Market, or Rainy Evening and set the start/end frames. **Preview Story Plan** only counts eligible objects, skipped objects, and proposed keyframes; it does not modify the scene. Review the summary, enable **I reviewed this Story plan**, and choose **Apply Story**.

Story Moments use normal Blender Actions and three-key loops. Depending on the preset, eligible characters bob subtly, foliage sways, rain travels, and practical lights pulse. Locked objects and objects or lights that already contain animation are skipped. **Clear Active Story** removes only Actions tagged with that Story identifier, restores original values and weather, and leaves unrelated/manual animation intact.

Only one Story may be active per world. Selecting another world loads that world's Story state. Camera shot sequencing and export are intentionally reserved for M8.2 and M8.3.

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
