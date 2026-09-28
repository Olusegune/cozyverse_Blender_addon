# CozyVerse Builder User Guide

## Start in under a minute

1. Install the CozyVerse ZIP through **Edit > Preferences > Get Extensions > Install from Disk**.
2. In the 3D View, press `N` and select the **CozyVerse** tab.
3. Keep **Create** selected, describe a miniature world, and choose a style.
4. Select **Generate Local World**.
5. Open `CV_DEMO` in the Outliner and edit its meshes, light, and camera normally.

The current foundation build is deterministic and offline. It creates a demonstration from Blender primitives so you can evaluate the interaction without an account, API key, or paid service.

## Sidebar workspaces

### Create

Enter a concise world description, select a style, and generate the local demonstration. Running the action again refreshes CozyVerse-managed demo objects while preserving unrelated objects you added to the collection.

### Activity

Review the last operation, offline-engine state, and latest build prompt. A success message means Blender completed the operator; suggestions or text alone never imply that the scene changed.

### Settings

Choose Local Only or configure fields for a future AI provider adapter. The foundation validates only whether the required fields exist. It does not contact a provider.

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
- The compact native prompt field is not a full multiline editor.
- Local asset scanning begins only after M2 is approved.

