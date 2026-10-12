# Credential and Data Safety

CozyVerse Builder 0.13.0 keeps live provider submission disabled. Procedural variety and Atmosphere Lab mappings are deterministic local code driven by validated scene-plan and preset data; no generated Python is executed. Asset imports remain approval-gated, imported animation drivers are removed, reference images remain local, and no provider request is made.

Revision activity is stored as a maximum of 50 scene-local entries. Credential-shaped values and current session secrets are redacted before an entry is stored. Checkpoints are explicit user actions and are written as timestamped `.blend` copies beside an already-saved project; CozyVerse never silently changes the active file path.

Director, Tripo, and Meshy API keys entered in the sidebar are runtime-only Blender properties marked `SKIP_SAVE`. They are masked in the interface and excluded from scene properties. Automated Blender testing verifies that known secret sentinels do not appear in the saved `.blend` bytes.

The provider, model, and environment-variable name are configuration metadata and may be saved in Blender preferences. Do not place an API key in any of those fields. CozyVerse never logs the session key.

Persistent credential storage is intentionally absent. A future implementation must use an approved operating-system credential vault or an equivalently reviewed mechanism. It must not store plaintext secrets in `.blend` files, Blender preferences, logs, project JSON, or source control.

No provider adapter, credential verification request, or paid API action exists in this foundation release.
