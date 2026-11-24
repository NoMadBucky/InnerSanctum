# InnerSanctum Change Log

## 2026-11-24

* **Read-only project hub**: Added the [seven-target project registry](project-registry.md)
  and project-local OpenCode status and planning commands. No global configuration,
  live service, or store changes.

* **Journal client migration**: Added replay-safe write receipts and an
  existing-day append precondition. Prepared MatterKeep Personal's local
  journal operator and a default-off BHO append adapter. No live activation.

* **Personal CRUD**: Added guarded reads, revision-checked updates and deletes
  for concepts and journal entries. New writes use the shared audit log and
  recovery mechanism. Tested on disposable bundles only.

* **Personal journal command**: Added guarded, date-addressed entry creation
  and insertion, with index updates for new days and shared write recovery.
  Tested on disposable bundles only.

* **BHO dashboard restored**: Verified the dashboard and its existing brokered
  Personal read path with Personal publisher selections disabled. MatterKeep
  Personal remains offline; sampled canonical files and journals did not change.

* **Live writer handover**: Transferred `OKF/` authority to InnerSanctum
  after verifying the stopped checkpoint and separate backups. Verified
  the first ordinary Video Create and its index and audit updates. The
  former writer and BHO remain offline; attachments were unchanged.

* **Writer handover candidate**: Added and rehearsed exact-checkout adoption
  with a stopped Personal checkpoint. No live marker or service changes.

* **Live Create preparation**: Checked the live Video route and adapted
  Create to preserve repeated historical audit sections and legacy tagged
  metadata. Added the [handover plan](/create-cutover.md); no live writes,
  service changes or writer transfer.

* **Standalone concept Create**: Added schema-driven templates and a
  recoverable local writer for disposable bundles. No MatterKeep runtime
  dependency, live store changes or writer cutover.

## 2026-11-23

* **Specification relocation** (`2026-11-23T18:18:30-06:00`, `mk-agent/gpt-6-2-sol`):
  Updated project links for the move of the specification and license to
  [OKF_SPEC](/OKF_SPEC/index.md). No Personal store changes.

* **Repository layout** (`2026-11-23T18:16:32-06:00`, `mk-agent/gpt-6-2-sol`):
  Updated the project index and README for the then-root-level [OKF v0.3 specification](/OKF_SPEC/SPEC.md)
  and its license, and documented the Git-ignored copies of the MatterKeep
  Personal bundle and source files. No registry cutover or format conversion.

* **Creation** (`2026-11-23T16:35:32-06:00`, `mk-agent/gpt-6-2-sol`): Added the
  [README](/README.md) describing the format requirements and listed it in the
  [bundle index](/index.md). Started this change log.
