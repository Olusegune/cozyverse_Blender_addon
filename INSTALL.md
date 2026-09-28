# Installation and Verification

## Supported foundation target

CozyVerse Builder targets Blender 4.5 LTS through 5.2 LTS. Automated Blender testing for this delivery was run with Blender 5.2.2 LTS on Windows.

## Install the extension ZIP

1. Open Blender.
2. Choose **Edit > Preferences > Get Extensions**.
3. Open the menu in the upper-right and choose **Install from Disk**.
4. Select `outputs/cozyverse_builder-0.1.0.zip`.
5. Enable **CozyVerse Builder** if Blender does not enable it automatically.
6. Open the 3D View and press `N` to show the sidebar.
7. Select the **CozyVerse** tab.

## Run the local demonstration

1. Enter or edit the world prompt and choose a preset.
2. Select **Create Local Demo**.
3. Expand the `CV_DEMO` collection in the Outliner.
4. Move or edit any generated mesh, light, or camera using Blender's native tools.
5. Use Blender Undo immediately after creation to revert the operation.
6. Save and reopen the `.blend` file to confirm the scene and CozyVerse settings persist.

The foundation build never connects to a network or calls a paid service. Re-running the demo replaces only objects in the managed `CV_DEMO` collection that carry CozyVerse demo metadata.

## Developer test commands

From the repository root in PowerShell:

```powershell
& 'C:\Users\eduni\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python tests\blender_smoke.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --command extension validate blender_addon\cozyverse_builder
```
