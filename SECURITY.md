# Credential and Data Safety

CozyVerse Builder 0.10.0 keeps live provider submission disabled. Scene plans are validated structured data rather than executable Python. Asset indexing and placement proxies do not open model files. A local model is imported only after explicit approval, imported animation drivers are removed, and provenance is recorded. Reference images remain local, and no provider request is made.

Director, Tripo, and Meshy API keys entered in the sidebar are runtime-only Blender properties marked `SKIP_SAVE`. They are masked in the interface and excluded from scene properties. Automated Blender testing verifies that known secret sentinels do not appear in the saved `.blend` bytes.

The provider, model, and environment-variable name are configuration metadata and may be saved in Blender preferences. Do not place an API key in any of those fields. CozyVerse never logs the session key.

Persistent credential storage is intentionally absent. A future implementation must use an approved operating-system credential vault or an equivalently reviewed mechanism. It must not store plaintext secrets in `.blend` files, Blender preferences, logs, project JSON, or source control.

No provider adapter, credential verification request, or paid API action exists in this foundation release.
