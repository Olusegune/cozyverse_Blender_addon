# Credential and Data Safety

CozyVerse Builder 0.2.0 operates offline and makes no network requests.

API keys entered in the sidebar are runtime-only Blender properties marked `SKIP_SAVE`. They are masked in the interface and excluded from scene properties. Automated Blender testing verifies that a known secret sentinel does not appear in the saved `.blend` bytes.

The provider, model, and environment-variable name are configuration metadata and may be saved in Blender preferences. Do not place an API key in any of those fields. CozyVerse never logs the session key.

Persistent credential storage is intentionally absent. A future implementation must use an approved operating-system credential vault or an equivalently reviewed mechanism. It must not store plaintext secrets in `.blend` files, Blender preferences, logs, project JSON, or source control.

No provider adapter, credential verification request, or paid API action exists in this foundation release.
