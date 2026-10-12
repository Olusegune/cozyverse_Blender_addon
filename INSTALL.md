# Installation and Verification

## Supported foundation target

CozyVerse Builder targets Blender 4.5 LTS through 5.2 LTS. Automated Blender testing for this delivery was run with Blender 5.2.2 LTS on Windows.

## Install the extension ZIP

1. Open Blender.
2. Choose **Edit > Preferences > Get Extensions**.
3. Open the menu in the upper-right and choose **Install from Disk**.
4. Select `outputs/cozyverse_builder-0.15.3.zip`.
5. Enable **CozyVerse Builder** if Blender does not enable it automatically.
6. Open the 3D View and press `N` to show the sidebar.
7. Select the **CozyVerse** tab.

## Run the local demonstration

1. Enter or edit the world prompt and choose a style.
2. Select **Build World**.
3. Expand the `CV_WORLD` collection in the Outliner.
4. Move or edit any generated mesh, light, or camera using Blender's native tools.
5. Open **Atmosphere Lab**, choose a look, adjust time/exposure/practical lights, and use **Save Look**. Switch worlds through **Activity & Safety** to verify each version keeps its own look.
6. Use Blender Undo immediately after an operation to revert it.
7. Save and reopen the `.blend` file to confirm the scene and CozyVerse settings persist.

Local creation and mock provider jobs never connect to a network or call a paid service. Live Tripo/Meshy submission is optional and requires a session key, exact request preview, sufficient credit ceiling, paid-request consent, and final confirmation. Each approved world revision preserves earlier generated worlds, locks, manual edits, and unrelated user objects.

## Developer test commands

From the repository root in PowerShell:

```powershell
& 'C:\Users\eduni\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python tests\blender_smoke.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --factory-startup --python tests\blender_undo_smoke.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python tests\render_r1_demo.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --command extension validate blender_addon\cozyverse_builder
```
