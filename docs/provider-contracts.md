# Provider contract snapshot

Verified against official documentation on 2026-10-12. Provider contracts and prices are externally controlled and must be reviewed before each release.

## Tripo

- API root: `https://api.tripo3d.ai/v2/openapi`
- Create task: `POST /task`; status: `GET /task/{task_id}`.
- Authentication: Bearer API key; Tripo documents `tsk_` keys and warns against client-side exposure.
- Baseline request: `text_to_model`, model `v3.1-20260211`, standard texture, GLB/GLTF output.
- Baseline estimate at verification: 20 API credits. The add-on treats this as an estimate, not a guaranteed charge.
- The verified v2 schema did not publish a cancellation endpoint, so CozyVerse does not claim Tripo cancellation support.
- Official sources: https://platform.tripo3d.ai/docs/quick-start, https://platform.tripo3d.ai/docs/schema, https://platform.tripo3d.ai/docs/billing

## Meshy

- API root: `https://api.meshy.ai/openapi/v2`
- Text-to-3D preview: `POST /text-to-3d`; status: `GET /text-to-3d/{id}`.
- Baseline request: mode `preview`, model `latest`, standard geometry, remesh target 20,000, GLB output.
- Baseline estimate at verification: 20 API credits for the current latest standard preview mesh.
- `DELETE /text-to-3d/{id}` refunds a still-PENDING task. Meshy documents that IN_PROGRESS tasks cannot be deleted or refunded and return HTTP 409.
- Official sources: https://docs.meshy.ai/en/api/text-to-3d, https://docs.meshy.ai/en/api/pricing, https://docs.meshy.ai/en/api/changelog

## CozyVerse safety envelope

- No submission occurs from request preview, key validation, mock jobs, polling mock jobs, or asset inspection.
- Live submission requires the exact request fingerprint, an adequate user-set credit ceiling, a paid-request checkbox, and a final confirmation dialog.
- Network I/O runs outside Blender's main thread; worker code never imports or calls `bpy`.
- Downloads require HTTPS, an allowlisted provider host, a `.glb` or `.gltf` URL, a 100 MB maximum, and binary GLB magic before persistence.
- Imports enter `CV_ASSET_QUARANTINE`. Animation drivers are removed. Promotion to `CV_ASSET_FACTORY` requires a second explicit approval.
