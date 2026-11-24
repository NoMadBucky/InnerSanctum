# Notes Save rollout

**2026-11-24T19:23:54Z · Candidate rehearsed; no live preflight or activation.**
The [project registry](project-registry.md) resolves `barry` and `bho`.
The [cutover record](create-cutover.md) remains the source for writer authority.
The November 24 record is not a fresh observation of either service.

## Candidate

The Personal `serve` command now skips the legacy Auth bootstrap in
successor mode. The successor app itself requires the existing Auth
database, workspace identity and active owner before opening Notes.
A missing Auth store must not be initialized by an attempted launch.

| Component | Rehearsed source | Wheel SHA-256 |
| --- | --- | --- |
| InnerSanctum | `328641c` | `e0eee00dd45864492114c89f8277ef9aba554cda80114afe449c82085f488386` |
| MatterKeep Personal | `cc82510` plus the `serve` guard change | `46dbf252d59f3d8dab2f51df2ea2d6ae7010161768e91d722bf65b74f748da04` |
| MatterKeep OKF validator | `cc82510`, unchanged | `651aec9dd3a18dce9112eb4ec39f1d61a7387f531bedb430063a2358e55a20b4` |
| MatterKeep OKF CRUD library | `cc82510`, unchanged | `44e6da9feac5b2b3a2bc30cc0a636cc90aff3b4c469a3b769f2a9b863268cd44` |
| BHO | `82d131b75`, unchanged | No BHO wheel or source change |

The noneditable wheels were tested in fresh runtimes with locked
dependencies: 110 InnerSanctum and 359 focused Personal tests passed.
The installed `serve` command bound an ephemeral loopback port over a
disposable adopted checkout at `/barry`; anonymous access was refused,
an authenticated Save succeeded, and retry returned the same receipt.
The test stopped its server. BHO's existing Source host passed 105
regression tests. These checks do not establish live schema, launcher,
grant, browser, or HTTPS readiness. The Personal fix still needs a
reviewed source pin; temporary artifacts are not production selections.

## Gate 1 — exact read-only preflight approval

Request approval to inspect only the adopted Personal checkout's
metadata and supported Note schemas and indexes; the original Auth and
Notes state and sealed handover checkpoint; and the current Personal
and BHO job, listener, and selector metadata. Use the expected
`system/com.matterkeep.personal.barry` (loopback `5564`) and
`gui/501/com.matterkeep.dashboard` (loopback `5555`) as historical
identifiers to verify, not as authority to operate them.

Report only counts and pass/fail reasons; keep paths, IDs and digests
needed for operator approval privately. Do not print source, drafts,
bearers, grant material or launcher contents. No launch, restart,
service request, grant issuance/extension, write, recovery, replay or
configuration edit is part of this gate.

* Verify the marker and that its sealed checkpoint names the original
  Notes database and expected owner. Check physical Notes identity,
  checkpoint database digest, writer/draft schema and absence of
  pending legacy intents or ambiguous receipts. Verify the existing
  Auth workspace and active owner separately: the checkpoint excludes
  Auth. Inspect SQLite in a non-recovering, read-only manner.
* Check the eligible Note/Draft declarations, exact chosen paths and
  parent listings against the candidate, distinguishing body-only
  from title-change eligibility. Execute candidate write previews only
  against a separately approved private disposable copy, not the live
  store. Choose one real existing note with the owner for later
  acceptance. Do not create a synthetic live record.
* Verify the current service and hold posture, no inbound sync, and
  the BHO registry binding and dedicated Notes selector disposition.
  Check whether the existing grant is in scope and unexpired without
  using the bearer, and whether an original BHO Save remains unsettled.
  Unknown or mismatched evidence blocks activation. Do not renew an
  expired grant or clear a hold as part of the preflight.

## Gates 2 and 3 — separate operational approval

1. **Personal first.** Pin exact artifacts, configuration and service
   action. Before any start, preserve a verified checkpoint of the
   current stopped Personal pair, including InnerSanctum receipts,
   and separate private Auth evidence. Qualify the preservation method
   for the successor marker; the former Personal checkpoint command
   is not a fallback. Confirm legacy Personal and
   all other publishers remain excluded. Start only the Notes-only
   successor host with `delegated_api = false`; leave BHO untouched.
   Verify the process, loopback listener, HTTPS route, owner-only
   signed-in read and draft visibility before asking for one exact
   owner-selected Save. Verify the note, legitimate index changes,
   one audit entry, draft generation and no pending write.
2. **BHO later.** Consider enabling only the existing delegated Notes
   route and Source selector after Personal acceptance, with exact
   grant, publisher fence and service action approved separately.
   Reconcile retained BHO operations before new writes. Verify
   read, original receipt behavior and one owner-approved Save.
   Do not select Clerk concept or Transcript, Daily Briefing,
   journal publication, or Work publishing in either gate.

**Backout:** On any mismatch, stop and restart-inhibit only the
candidate Personal host if it was started. If the BHO Source selector
was separately armed, take it back to its prior held setting and
verify the dashboard's read path. Preserve the newest canonical bytes,
marker, pending plans, Notes state and receipts. Do not restart the old
writer, restore the handover checkpoint over newer data, rebind the
workspace, reopen inbound sync or retry an uncertain request under a
new ID. Any recovery of an accepted write needs its own review.
