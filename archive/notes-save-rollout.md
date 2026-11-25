# Notes Save rollout

**Archived.** Personal and BHO Notes Source both passed signed-in, body-only
Save acceptance through InnerSanctum on November 24, 2026. The first BHO
Notes Source Save was independently verified at `2026-11-24T20:16:54Z`.
Other BHO publishers and Work writing stayed held.

This is a historical record, not a live health check or authorization to
rerun a gate. The [project registry](../project-registry.md) resolves
`barry` and `bho`, and the [cutover record](../create-cutover.md) remains
the source for writer authority. Current backup coverage is a
[separate follow-up](relocation-plan.md#separate-follow-ups).

## Rehearsed candidate

The Personal `serve` command now skips the legacy Auth bootstrap in
successor mode. The successor app itself requires the existing Auth
database, workspace identity and active owner before opening Notes.
A missing Auth store must not be initialized by an attempted launch.

| Component | Rehearsed source | Wheel SHA-256 |
| --- | --- | --- |
| InnerSanctum | `328641c` | `e0eee00dd45864492114c89f8277ef9aba554cda80114afe449c82085f488386` |
| MatterKeep Personal | `28f11e4` | `46dbf252d59f3d8dab2f51df2ea2d6ae7010161768e91d722bf65b74f748da04` |
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
grant, browser, or HTTPS readiness. The packaged Python payloads matched
the committed InnerSanctum and Personal sources. Temporary artifacts
are not production selections.

## Gate 1 — historical read-only preflight

The preflight verified the adopted checkout, offline checkpoint seal,
physical Notes identity and matching database bytes. The original Auth
workspace and owner are active. Notes had no active private draft or
unfinished Save. Metadata checks found 123 eligible Notes compatible
with body edits and 121 with title-listing edits. No candidate write
preview ran on live data.

Personal was absent, disabled and not listening. BHO was listening only
on the expected loopback port and bound to the adopted checkout.
The Personal publishers were not selected and the owner hold was active.
The retained BHO Notes grant was active and write-capable; its journal
contained one completed Save, one unsent draft and no uncertain submission.
These were local checks with no service requests. At this point the protected
Personal launcher and inbound sync exclusion still awaited owner confirmation.

The preflight approval scope was limited to the adopted Personal checkout's
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

## Gates 2 and 3 — historical approval and execution record

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

### Attended Personal-only start

The successor backup method passed a disposable rehearsal: it held the
current writer marker, copied and independently verified canonical files
including hidden receipts, and verified separate private Notes and Auth
database copies without opening them for writing. It refused overwrite,
pending canonical work, a SQLite sidecar, and altered backup bytes.

The owner then confirmed inbound sync off and no intervening writers,
and reported the protected launcher is root-owned, mode `0600`, with
the expected label. A new private stopped backup verified independently:
1,130 canonical files, no completed InnerSanctum receipts at capture,
and separate Notes and Auth databases. No attachments were copied or
changed. The original sealed adoption checkpoint remains intact.

Both exact noneditable runtimes and a new inactive `/barry` config are
staged outside the repositories. The existing Auth identity and login
passkey matched; mail, delegated Save and other publishers are off.
The proposed launcher is attended (`KeepAlive` off). The private Terminal
runbook rechecks the stopped backup and BHO hold, archives the original
protected launcher, and changes only the Personal job. The backup sources
still matched at runbook preparation. No privileged command ran, no
service was started, and no Save was performed at that point. Signed-in read
verification awaited the owner running the reviewed Terminal step.

The owner subsequently ran the Terminal step and reported the staged
launcher started. Independent read-back matched the selected runtime
arguments and UID, configuration digest, and sole Personal loopback
listener. Public HTTPS sign-in responded; both Notes API paths refused
anonymous access. The adoption marker and lack of pending canonical
writes were verified. BHO remained running on its existing listener
with its publisher selectors absent. An attended browser opened the
Personal sign-in page without submitting it. No Save had been performed yet.

The owner reported that a note loaded correctly after sign-in. This
established owner-reported read acceptance before the Save.

For the first live Save, the owner selected one existing Note and
authorized a minimal body-only change. The source matched the stopped
backup and no private draft existed before editing. The signed-in Source
editor added one terminating newline and submitted Save once. Independent
read-back confirmed the exact revised bytes, one audit entry, one
completed InnerSanctum receipt and a cleared private draft. Only the note,
audit log, and new receipt changed within the canonical directory; title,
frontmatter and indexes were unchanged. No write remained pending. The
signed-in editor reopened the exact published revision after reload.

Personal stayed on the Notes-only candidate. No BHO selector or hold
changed during this Save. The stopped backup is historical, not a
rollback target.

### BHO Notes Source activation

After the owner approved proceeding, read-only checks matched the
retained selector and authenticated grant to the current binding. The
completed BHO Save reconciled against its matching historical Personal
receipt. Its one unsent draft remains unchanged; there were no unsettled
submissions. The owner hold remains on.

The inactive selections change only the Personal delegated Notes flag
and the BHO Notes Source selector. The owner Terminal step verifies the
existing protected launcher, stops BHO before Personal, takes a fresh
verified backup of the stopped post-Save pair, then starts Personal
before BHO. The backup method was rehearsed against a changed disposable
Notes generation. The start step leaves the broad owner hold in place
and sends no Save or replay. On failure it requests containment of the
two exact jobs and stops; do not rerun or restore a database.

The owner ran the activation step. Its immediate stopped check did not
confirm the boundary, so containment exited before copying the pair or
changing either launcher. Independent read-back subsequently found both
exact jobs absent and disabled, no listeners, the held BHO launcher and
owner hold unchanged, and no pending canonical publication. The precise
transient condition at the failed stop check is not known.

The fresh stopped backup then verified, including the first Personal
Save. A separate check matched the live canonical inventory, Notes and
Auth bytes to that backup, with the retained BHO operation journal still
unchanged. The new Terminal continuation begins at that verified boundary;
it does not replay the original stop sequence or recopy either database.
The owner then ran the continuation and reported Notes Source selected
with no Save or replay. Independent checks matched the exact two running
selections, their loopback listeners, the original grant, the unchanged
BHO operation journal and the owner hold. Public sign-in responded and
unauthenticated requests did not reach Notes content. The existing signed-in
BHO session opened its Notes Source listing with 123 eligible Notes. No
individual Source editor was opened: that would create a BHO operation.
The exact test Note and edit still awaited separate owner approval at that
point. The existing unsent draft was excluded from the test.

The initially proposed test Note was excluded because the retained unsent
BHO draft belonged to it. The owner approved one blank line at the end
of a different existing Note, with no private draft or BHO operation.
The signed-in BHO Source editor submitted the edit once and acknowledged it.
Independent read-back matched the exact revised bytes, BHO acknowledgement,
Personal's completed Save, and one InnerSanctum receipt and audit entry.
Only the note, audit log and receipt changed in the canonical directory;
the title, metadata and indexes stayed unchanged. The old BHO operations,
including the unsent draft, were unchanged, and no write remained pending.
The original-request receipt recheck produced no second publication.
Both the acknowledged BHO Source and the reopened Personal editor
matched the published revision.

At acceptance, both Notes lanes were available under their existing owner
and grant controls. Other BHO publishers and Work writing remained held.
The stopped post-Personal backup predates the accepted BHO Save and must
not be restored over it.

**Historical backout plan:** On any mismatch, stop and restart-inhibit only the
candidate Personal host if it was started. If the BHO Source selector
was separately armed, take it back to its prior held setting and
verify the dashboard's read path. Preserve the newest canonical bytes,
marker, pending plans, Notes state and receipts. Do not restart the old
writer, restore the handover checkpoint over newer data, rebind the
workspace, reopen inbound sync or retry an uncertain request under a
new ID. Any recovery of an accepted write needs its own review.
