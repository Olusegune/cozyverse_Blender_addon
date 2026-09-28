# CozyVerse Builder User Guide

## Start in under a minute

1. Install the CozyVerse ZIP through **Edit > Preferences > Get Extensions > Install from Disk**.
2. In the 3D View, press `N` and select the **CozyVerse** tab.
3. Expand **Create World**, choose a template or select **Compose Detailed Prompt**, and choose a style.
4. Select **Build Editable World**.
5. Open `CV_WORLD` in the Outliner and edit its meshes, lights, materials, and camera normally.

The current foundation build is deterministic and offline. It creates a demonstration from Blender primitives so you can evaluate the interaction without an account, API key, or paid service.

## Sidebar sections

### Create World

Choose one of six quick-start templates, paste a prompt from the clipboard, or select **Compose Detailed Prompt**. The composer is a bounded dialog with Setting, Subject, Mood, Details, and Avoid fields plus clear **Apply Prompt** and **Cancel** actions; it does not replace the Blender workspace. Select a style and build the local demonstration. Each new build creates a numbered `CV_WORLD` collection so earlier generated worlds and manual edits remain intact.

For unusually long free-form prompts, **Open Full Text Editor** creates a `CV_World_Prompt` Text datablock and switches the current area to Blender's Text Editor. Select **Use Prompt and Return**, or press **Shift+F5** to return to the 3D View. This is deliberately labeled as an advanced path.

#### Style Studio

Choose a visual style before building, or choose it directly inside **Compose Detailed Prompt**. Available styles are Cozy Village, Retro Sci-Fi, Cozy Fantasy, Solarpunk, Cyberpunk, Storybook, Low-Poly, Clay Miniature, Paper Craft, Art Deco, Gothic, and Tropical.

Styles affect the generated prompt, negative constraints, procedural material palette, metallic treatment, collection metadata, and asset-search keywords. For example, **Retro Sci-Fi** requests rounded modules, antennae, enamel panels, and optimistic analog technology while avoiding modern minimalism and excessive cyberpunk clutter. The generated world records `cv_style_label` and `cv_asset_keywords`, making the style available to the upcoming asset matcher.

The **Retro Sci-Fi** quick-start button fills the world-description fields and selects the matching style automatically. All generated prompt text remains editable before building.

### Atmosphere

Choose Golden Hour, Rainy Cafe, Moonlit, or Misty Dawn, or adjust the controls directly. Time of Day rotates the real `CV_Sun`; the sunlight, warmth, ambient, and interior controls update Blender lights and World nodes. Clear hides `CV_Rain_Preview`; Rain displays its editable rain-streak mesh. Fog, wind, and wetness are visible but disabled because R1 does not implement them.

The controls update immediately. **Apply** reruns the complete mapping, **Reset** returns to Golden Hour, and **Save Custom Preset** stores versioned JSON in the current scene.

### Image to World

Choose a PNG, JPEG, WebP, or TIFF diorama reference. CozyVerse loads it locally and displays a preview. **Extract Color Palette** samples the image inside Blender; it does not upload the image. **Create Editable Interpretation** builds a new native Blender world using deterministic geometry and the extracted palette. This is an editable artistic interpretation—not exact single-image geometry reconstruction.

The resulting world collection records the local reference path and reconstruction mode for provenance. External vision analysis remains disabled until an approved milestone adds an inspectable scene plan, privacy review, and explicit upload consent.

### Activity

Review the last operation, offline-engine state, and latest build prompt. A success message means Blender completed the operator; suggestions or text alone never imply that the scene changed.

### Connections & Settings

Choose Local Only or configure fields for a future AI provider adapter. The foundation validates only whether the required fields exist. It does not contact a provider.

The 3D Generation section provides separate masked session fields for Tripo and Meshy. Select a provider and use **Check Setup Locally** to confirm that its key is loaded. This check never contacts Tripo or Meshy. Generation submission remains disabled until a later approved adapter adds request previews, estimated cost, explicit per-job consent, polling, cancellation, download validation, and provenance.

Under **Your Asset Sources**, CozyVerse can index Blender Asset Library folders already configured in Blender and one optional local folder. Supported files are `.blend`, `.glb`, `.gltf`, `.fbx`, and `.obj`. This milestone records filenames only; it does not open, execute, or automatically import those files. Asset matching and reviewed placement are the next stage.

### 3D Asset Factory

The Generate workspace prepares an official-contract request for the selected provider. It shows the pinned model, provider cost warning, and a fingerprint for the exact payload. Approval resets whenever the request is previewed. **Run Safe Mock Job** creates an editable placeholder with the plan fingerprint and never contacts a provider or spends credits. Live submission remains disabled until asynchronous polling, cancellation, validated download, and import review are complete.

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

- No AI provider request is implemented.
- No paid generation service is implemented.
- Provider fields do not test remote credentials.
- Multiline prompts use a Blender Text datablock rather than an embedded sidebar text area.
- Local asset scanning begins only after recovery milestone R2 is approved.
