# Credential and Data Safety

CozyVerse Builder 0.15.0 keeps local creation as the default. Procedural variety, reference-image cue extraction, and Atmosphere Lab mappings are deterministic local code driven by validated scene-plan and preset data; no generated Python is executed. External generation is optional and request-specific. Asset imports remain approval-gated, imported animation drivers are removed, and reference images remain local unless a future separately approved image-upload workflow is implemented.

Revision activity is stored as a maximum of 50 scene-local entries. Credential-shaped values and current session secrets are redacted before an entry is stored. Checkpoints are explicit user actions and are written as timestamped `.blend` copies beside an already-saved project; CozyVerse never silently changes the active file path.

Tripo and Meshy keys remain masked `WindowManager` properties with `SKIP_SAVE`; they are not stored in scenes or `.blend` files. Provider submission requires a matching SHA-256 request fingerprint, an adequate maximum-credit approval, a consent checkbox and a final dialog. Downloads are restricted to approved HTTPS hosts, GLB/GLTF paths, 100 MB, and GLB binary validation. Generated models are isolated in `CV_ASSET_QUARANTINE`, stripped of animation drivers, and require separate approval before entering `CV_ASSET_FACTORY`.

Director, Tripo, and Meshy API keys entered in the sidebar are runtime-only Blender properties marked `SKIP_SAVE`. They are masked in the interface and excluded from scene properties. Automated Blender testing verifies that known secret sentinels do not appear in the saved `.blend` bytes.

The provider, model, and environment-variable name are configuration metadata and may be saved in Blender preferences. Do not place an API key in any of those fields. CozyVerse never logs the session key.

Persistent credential storage is intentionally absent. A future implementation must use an approved operating-system credential vault or an equivalently reviewed mechanism. It must not store plaintext secrets in `.blend` files, Blender preferences, logs, project JSON, or source control.

No provider adapter, credential verification request, or paid API action exists in this foundation release.

## The Director and AI models

- The Director is optional. With no provider or key, planning and follow-ups run entirely on this computer.
- Before any request is sent, the add-on shows the provider, the model, and exactly what leaves the machine. Nothing is sent without that confirmation.
- Requests go only to `api.anthropic.com`, `api.openai.com`, or a custom server you enter (https, or http for localhost only; no embedded credentials). Your key is sent as a header, kept in memory for the session, and redacted from errors and logs.
- A model's reply is parsed as data and validated field by field. Replies containing code-like text or executable keys are rejected whole. A model can never name local files, and follow-up edits are limited to a fixed list of commands. No model output is ever executed.
- Locked objects are never changed. Removals archive objects instead of deleting them.
