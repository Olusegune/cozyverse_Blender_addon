# Installation and Verification

## Supported foundation target

CozyVerse Builder targets Blender 4.5 LTS through 5.2 LTS. Automated Blender testing for this delivery was run with Blender 5.2.2 LTS on Windows.

## Install the extension ZIP

1. Open Blender.
2. Choose **Edit > Preferences > Get Extensions**.
3. Open the menu in the upper-right and choose **Install from Disk**.
4. Select `outputs/cozyverse_builder-0.7.0.zip`.
5. Enable **CozyVerse Builder** if Blender does not enable it automatically.
6. Open the 3D View and press `N` to show the sidebar.
7. Select the **CozyVerse** tab.

## Run the local demonstration

1. Enter or edit the world prompt and choose a style.
2. Select **Build World**.
3. Expand the `CV_WORLD` collection in the Outliner.
4. Move or edit any generated mesh, light, or camera using Blender's native tools.
5. Open **Atmosphere**, change the time and light sliders, then switch Weather to **Rain**.
6. Use Blender Undo immediately after an operation to revert it.
7. Save and reopen the `.blend` file to confirm the scene and CozyVerse settings persist.

The R1 build never connects to a network or calls a paid service. Each build creates a new numbered `CV_WORLD` collection, preserving earlier generated worlds and unrelated user objects.

## Developer test commands

From the repository root in PowerShell:

```powershell
& 'C:\Users\eduni\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -p 'test_*.py' -v
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python tests\blender_smoke.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --background --factory-startup --python tests\render_r1_demo.py
& 'C:\Program Files\Blender Foundation\Blender 5.2\blender.exe' --command extension validate blender_addon\cozyverse_builder
```
