# CozyVerse Builder Documentation Audit and Implementation Plan

## Decision

The approved foundation scope is M0 plus M1 because the consolidated PRD's First Assignment explicitly requests both, and the requested deliverable matches the M1 gate. This implementation stops before M2. The workspace arrived without a repository or `AGENTS.md`, so the consolidated PRD and the user's rules governed the bootstrap.

## Documentation audit

### Contradictions and scope conflicts

1. The PRD calls M3 the first product milestone while the roadmap defines M0 through M2 as required milestones. The First Assignment resolves this delivery to M0 plus M1, but future status reports should distinguish foundation milestones from the first user-complete product milestone.
2. The v1.0 N-panel specifies seven tabs, while the v1.1 UI replaces them with five tabs. The consolidated roadmap does not choose the final information architecture for M3 and later. M1 therefore uses one compact native panel with nested Status and Settings sections.
3. The MVP requirements include Atmosphere in a general slider and rainy example, while the v1.2 decisions defer rain, fog, wetness, wind, and animated transitions to M7+. M4 should implement only time, sunlight, practical lights, presets, and persistence.
4. The acceptance text asks for a multiline prompt inside the Blender sidebar, but Blender's native property control is a single-line string field. A true multiline editor needs a Text datablock workflow or custom UI design. The foundation keeps a bounded native prompt field and defers a larger UI pattern until user approval.
5. M1 says save and reopen without errors but does not state which data must persist. This implementation persists scene prompt, preset, status, last demo prompt, generated objects, and their CozyVerse metadata.
6. The PRD mentions clean uninstall but does not define whether generated scene data should be deleted. Uninstalling the extension must not delete user scene content. Registration state is removed; editable generated objects remain in the `.blend` file.

### Missing technical decisions

- `AGENTS.md` is absent.
- No repository, source files, license file, CI configuration, or version history was supplied.
- Commercial licensing and bundled demo asset licensing remain undecided. This foundation uses only programmatically created primitives and declares GPL-3.0-or-later for the extension package.
- The exact supported Blender matrix was pending. The foundation targets 4.5 LTS through 5.2 LTS and is executed on 5.2.2 LTS; 4.5 still needs execution evidence.
- The PRD does not define manifest migration, project metadata schema, manual-edit detection, secure credential storage, logging retention, asset database location, thumbnail generation, or performance hardware.
- A scene blueprint JSON Schema is described but not provided. It is not invented in M1.
- Undo semantics for partial failures, collision policy, object dirty-state hashes, and checkpoint reconciliation need designs and tests before M3-M5.
- Accessibility requirements lack keyboard sequences, contrast criteria, and a human test matrix.

### Unrealistic or unmeasurable requirements

- Reliable independent rollback of an AI change while preserving later manual edits is not generally guaranteed by Blender Undo. The PRD appropriately allows a checkpoint warning, but M5 needs a narrower, testable reconciliation contract.
- Detecting every manual object edit through hashes can be expensive and incomplete across Blender data types. M5 should define which properties and datablocks are tracked.
- Indexing 500 assets without freezing the UI and assembling 30-60 objects have no reference hardware or latency budget. M2 and M3 must record hardware and percentile timings before setting gates.
- Full keyboard reachability is constrained by Blender's native UI and cannot be guaranteed solely by add-on code. Human testing must record reachable and unreachable interactions.
- Cross-version save/reopen and migration cannot be a single assertion. Each supported Blender version needs a compatibility row and actual execution evidence.

## Repository state before implementation

The task directory contained only empty `work` and `outputs` directories. It was not a Git repository, and there were no project files or agent instructions to preserve. The foundation therefore starts at version 0.1.0 without claiming prior implementation.

## Milestone plan and acceptance criteria

### M0 Compatibility and bootstrap

- Pin the supported version policy and package format.
- Establish source, tests, documentation, reproducible ZIP output, and change log.
- Pass pure-Python tests and Blender extension manifest validation.
- Record the exact Blender version used for execution.

### M1 Installable native add-on shell

- Install from a ZIP containing `blender_manifest.toml` and the extension package.
- Register a `CozyVerse` 3D View sidebar and settings without errors.
- Accept a bounded prompt and preset and show status feedback.
- Create a deterministic, editable, local-only demo collection through an undo-enabled operator.
- Persist prompt metadata and generated scene data through save and reopen.
- Disable and re-enable cleanly without leaving registered RNA properties or requiring network access.

### M2 Local asset intelligence

- Scan a licensed 100-asset fixture recursively without modifying originals.
- Store stable identifiers, paths, dimensions, tags, provenance, license notes, scan time, and preview state.
- Cancel safely and report corrupt, missing, and moved assets without blocking the UI.
- Return deterministic keyword matches and placeholders with no provider key.

### M3 Director planning and editable assembly

- Approve a versioned JSON Schema before implementation.
- Validate syntax, schema, semantic ranges, operation allowlist, asset IDs, object limits, and safe paths.
- Preview the rainy Manila plan before mutation and reject invalid actions without scene changes.
- Build named native collections, editable objects, a base, camera, and stable metadata from local assets and placeholders.

### M4 Atmosphere Lab and Cozy Engine

- Map each approved control to named Blender properties with documented ranges and units.
- Change sunlight, artistic time, practical lights, and approved style settings without rebuilding geometry.
- Save, reload, reset, and migrate presets; keep weather effects outside this milestone.

### M5 Safe revisions and beta hardening

- Preview changed, created, deleted, and skipped objects before apply.
- Preserve locked descendants and detect the defined set of manual edits.
- Verify undo/checkpoint behavior, cancellation, redacted logs, recovery, and packaged beta failure paths.
- Complete the golden path with actual Blender evidence and no high-severity data-loss or security defect.

Later milestones M6-M8 remain blocked on separate approval, provider/license verification, and mini-PRDs where required.

