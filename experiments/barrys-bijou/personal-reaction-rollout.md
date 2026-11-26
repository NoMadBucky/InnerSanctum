# Personal reaction filing: proposed rollout

**Decision as of November 26, 2026: InnerSanctum is designated the sole
source writer; live activation is pending.** Bijou has rehearsed filing one WAV through an authenticated
practice adapter, retrying it, and removing the local copy. That is evidence
for the workflow, not authority to write the Personal source catalog.

## Who owns what?

| Target | Evidence | Decision needed |
| --- | --- | --- |
| `OKF/` | The [Create cutover](../../create-cutover.md) names InnerSanctum as its sole writer. | Keep that writer; approve the additive reaction schema and route separately. |
| `SourceFiles/catalog.json` and native media | On November 26 the operator confirmed there are no writers or processes adding sources and designated InnerSanctum to own that process. MatterKeep Personal's `catalog_context.py` reads the catalog. | Implement new imports through InnerSanctum only. The earlier OKF cutover did not install or activate a source writer. |
| Bijou | `reaction_filing.py` requires a physical external fixture and its private store binding; the HTTP adapter refuses fixture uploads in Personal mode. | Keep fixture guards. Implement a separately bound Personal operation only after the ownership decision. |

The designated owner is **InnerSanctum**, not the phone. Its source writer must
coordinate *all* modifications of the shared catalog: reserving the `audio/`
directory alone cannot stop two tools from replacing `catalog.json` with
different snapshots. Route future producers through the same local importer.
A local lock cannot fence external sync or manual replacement.

### Initial read-only baseline

On November 26 all 91 version-1 catalog entries resolved to local files of
the recorded size and SHA-256. The catalog bytes were unchanged across the
check. No `audio/` directory, reaction source keys, or `OKF/Documents/reactions/`
directory existed. This establishes a starting point, not a stopped checkpoint
or evidence of a completed backup. Repeat verification before activation.

### Implementation and rehearsal status

The Personal importer and schema installer are implemented but not activated.
Tests on a disposable adopted checkout with an existing version-1 catalog
recovered an interrupted schema install, retried a filing after source
publication, preserved the existing catalog entry and refused a stale catalog
and a replaced source directory. The native upload rehearsal uses the practice
adapter; physical-device Personal filing and live restore are not yet verified.

### External restore rehearsal · November 26, 2026

The two live trees were copied to a private checkpoint outside the checkout
while holding the adopted OKF marker lock. No OKF publication was pending.
Source and checkpoint manifests matched before releasing the lock. A separate
restore from that checkpoint matched the manifests for 1,161 OKF files and
95 source-store files, including hidden writer state. All 91 restored catalog
entries resolved to files with the recorded sizes and SHA-256 digests.
The checkpoint, restored copies, manifest and receipt are private on the Mac.

This was a lock-coordinated capture and an external restore, not an in-place
restore, service stop or independent off-Mac backup. Recheck the baseline
and drain writers before an approved installation; repeat the checkpoint if
anything has changed.

`adapter/prepare_reactions.py` is a stopped, separately authorized operator
step. It checks the exact checkout, expected OKF adoption and approved catalog
SHA-256, creates the private `SourceFiles/.innersanctum-sources/` state and
`audio/`, and installs `Documents/reactions/index.md` via a recoverable OKF
writer operation. It returns a source binding pin. An existing unbound audio
directory or partially prepared unknown state requires inspection, not removal.
The Personal adapter advertises filing only when started with the separate
`--source-writer-pin`. Omitting this option disables uploads. Neither serving
requests nor ordinary sync prepares or adopts a store.

During import, an interrupted catalog replacement retains the take UUID and
both revisions in private state. Retry the same take; never manually advance
the cursor. For an interrupted OKF publication, recover the pending operation
through the adopted checkout before retrying. Keep the phone copy until the
receipt is saved.

## Scope of one filing

* Target: the exact adopted `InnerSanctum/OKF` and its physical sibling
  `InnerSanctum/SourceFiles`. Bind both independently; never infer the
  destination from a path supplied by a device. Recheck bindings on retry.
* Accept one explicitly selected kept PCM WAV, one take UUID, one existing
  movie identity, timestamp, optional viewing date and expected checksum.
  Bound upload size and duration, authenticate before reading the upload,
  and verify audio format, length and SHA-256 on the Mac.
* The source writer may create a missing `audio/<sha256>.wav`, register
  `Documents/reactions/<take-uuid>.wav` in the version-1 catalog, and
  retain private recovery state. Never overwrite a conflicting key or blob,
  remove an original, or modify unrelated catalog entries.
* InnerSanctum creates one `Film Reaction` in `OKF/Documents/reactions/`,
  using its guarded Create, normal ID allocator, parent index and root log.
  It points to the source key and checksum and the movie's ID and path.
  No movie-body or ranking change. The receipt is returned only after both
  stores read back correctly. Device removal deletes only the phone copy.

## Before requesting activation

1. Retain the operator's sole-writer decision above. Check that existing source
   consumers resolve a new WAV key and tolerate the reaction schema on an
   external copy; the paired-client rehearsal alone does not prove this.
2. Build the Personal-specific guarded importer, adapter capability and
   schema installer against disposable stores. Test simultaneous submissions,
   stale catalog revisions, store replacement, altered retry payloads, disk
   full, and interruption after each durable write. Replay the same UUID;
   refuse conflicts rather than rebasing or allocating another concept.
3. Prepare a stopped, private checkpoint of both stores, including writer
   journals, receipts, bindings and catalog. Verify catalog-to-file hashes
   and rehearse restoring that checkpoint to **separate external paths**.
   Record manifests and approvals outside Git. Earlier backups are historical
   evidence, not a preflight for this change.
4. Submit the exact paths, expected baseline revisions, permitted schema,
   affected services, first genuine take/movie selection, verification and
   rollback for separate operational approval. No deployment from this plan.

## First approved filing and rollback

First enable schema and routing; verify their diff separately. Then file one
real take while retaining its device copy. Compare against the new baseline:
one verified playable original (or reuse identical bytes), one catalog key,
one reaction concept, one parent listing and one Create log entry. Verify
the film ID, viewing date, checksum and receipt on retry. All other entries,
movie bodies and ranks must be unchanged; no journal may remain pending.

On mismatch, disable **only reaction filing**, retain the take, journals,
catalog and original, and inspect both sides before any recovery. A missing
concept after a successful source import is recoverable; an orphan is not
permission to delete a blob. Reconcile the original request and verify it
before reopening filing. If restoration is necessary, stop affected writers,
compare both stores for intervening writes, and obtain approval for a
coordinated restore or forward repair. Never restore just an old catalog over
new entries. Ordinary ranking sync does not require the filing capability.
