# Live Create cutover

## Status

**Cutover complete.** InnerSanctum owns write authority for the live `OKF/`
bundle. The former installed Personal runtime refused the new marker before
opening Notes and remains retired as a writer. BHO did not take over writer
authority.

At the November 24, 2026 [Notes Save acceptance](notes-save-rollout.md#bho-notes-source-activation),
the Personal Notes-only successor and BHO Notes Source both saved through
InnerSanctum. Other BHO publishers and Work writing remained held. This
records acceptance, not current service health or approval to release
another publisher.

A fresh stopped Personal checkpoint of OKF and Notes verified independently
before and after the marker change. Separate private Auth and `SourceFiles/`
backups passed byte-for-byte checks, and all 91 catalog entries verified.
The first real Video Create read back exactly the new concept, one parent
index insertion, and one root audit entry. No other canonical bytes or
attachments changed, and no publication was left pending. Retained evidence
is outside Git. This does not change the OKF v0.2 format or move `SourceFiles/`.

A November 24 read-only check resolved `Video` to `Resources/videos` from
116 indexes and found 1,008 unique IDs. In-memory formatting checks passed
for the videos index and the root audit log. The implementation now preserves
repeated historical date sections and reads legacy IDs without interpreting
tagged metadata. It still refuses an ambiguous target date or ID. These checks
were preparation, not evidence of the later writer transfer.

## Decide what stays running

The first handover kept both services offline. BHO subsequently returned on
its existing user job with only four Personal API launcher selections removed:
delegated Notes editing, Clerk Transcript publication, Clerk concept changes,
and Daily Briefing publication. The original launcher is preserved privately.
The owner publication hold is active, native Personal writes still refuse,
and the existing brokered read of the InnerSanctum bundle passed without
changing the binding. Local and public HTTPS sign-in responded; no publisher
was invoked. The sampled canonical files and publisher journals were unchanged.

Use one writer for the entire bundle, not one writer per collection. Create
changes the shared root audit log and checks bundle-wide IDs. At this stage
the Personal service stayed stopped and its publishers stayed held. The
later Notes-only successor did not restore the former writer.

| Existing surface | Required disposition before cutover |
| --- | --- |
| Personal editor, local operator commands and delegated clients | Disable write access for this workspace. Preserve drafts, completed receipts and recovery state. |
| Clerk ordinary edits and managed Transcript publication | Hold and reconcile in-flight operations; retain confirmed receipts. A new broker is separate work. |
| Daily Briefing | Hold publication and reconcile both halves of each Note/Transcript pair. Do not replay uncertain attempts. |
| Personal browsing, search and attachments | Keep offline for the first handover unless a reader-only configuration is verified unable to write, recover, provision or take over authority. |
| Inbound sync and manual writes | Keep excluded. A local lock cannot enforce remote or noncooperating writer exclusion. |

## Handover sequence

1. **Prepare a candidate on disposable data.** The candidate introduces an explicit
   exact-checkout opt-in for `InnerSanctum/OKF`, an InnerSanctum writer binding,
   and a guarded transfer of ownership. Keep default refusal for repositories,
   other workspaces and active Personal markers. Rehearse interruption,
   conflicting authority and recovery. Do not rename or remove the live
   Personal marker to bypass the existing gate.
2. **Approve an exact maintenance window.** Pin the candidate, target and
   service actions. Account for the Personal service and local operator, BHO
   and independent Clerk processes, Briefing and other publishers. An empty
   queue or a stopped dashboard alone is not evidence of exclusion.
3. **Drain and checkpoint.** Verify no pending or uncertain write remains
   after stopping or holding the approved writers. Take a fresh verified
   stopped Personal checkpoint of OKF and Notes, and preserve Auth and
   `SourceFiles/` separately. Capture the writer marker and bindings. Keep
   private evidence outside Git.
4. **Transfer authority and verify.** Activate only the approved InnerSanctum
   binding. Verify that the old writer cannot start or publish against this
   bundle and that any retained readers can still read without mutating it.
   Leave the old SynologyDrive tree untouched.
5. **Run one real Create.** Check for the title and TMDb ID again before adding
   *The Uprising* as watched on November 24, 2026. Read back the new concept,
   the sole videos index insertion, and the sole audit entry. Verify that no
   other canonical files or attachments changed and that no publication is
   pending. Do not write synthetic acceptance records into the live store.

If interrupted, reconcile the original journal before any retry or service
restart. After an InnerSanctum write, do not reactivate Personal against the
new state or restore an old checkpoint without separately approving how the
new records, drafts and receipts will be preserved.

## Adoption command reference

Only after writer and publisher exclusion, backup preservation, and independent
verification with the installed Personal offline checkpoint verifier:

```sh
uv run --locked innersanctum concept adopt --live-checkout "$CHECKOUT" \
  --checkpoint "$STOPPED_CHECKPOINT" --sha256 "$RECEIPT_SHA256" \
  --writers-stopped
```

`adopt` does not stop services, inspect their queues, create backups, or verify
Personal's APFS custody evidence. It checks the sealed receipt and canonical
preimage, including the backup's file bytes and Notes copy, while holding the
current Personal writer lock. It then replaces the marker atomically with one
bound to the selected checkout and bundle. Personal's configured writer
requires its v2 marker and rejects the successor format. The original marker
remains in the verified checkpoint. If the result is uncertain, inspect the
current marker; do not retry or start either service on an assumption.

Use `concept create --live-checkout "$CHECKOUT"` with the normal draft, actor
and routes arguments only after adoption is verified. Use the same explicit
checkout argument with `concept recover` for an interrupted Create.
Do not rerun `adopt` for the current live bundle.

## Journal client source slice

InnerSanctum exposes durable request receipts for concept and journal
mutations. The journal append command can require an exact existing day
revision. The first two clients use the guarded CLI, not a new canonical
writer or a shared Python runtime:

| Client | Source coverage |
| --- | --- |
| MatterKeep Personal | Explicit `successor-journal` local operator command: add, read, update, delete and recover. Uses the existing explicit checkout configuration but does not open Notes or Auth. |
| BHO dashboard | Default-off append from the composer on an existing Personal day. Rechecks the signed-in owner, registered checkout, maintenance fence and source revision; no legacy or Work fallback. |

This does not restore the Personal web editor or delegated Note Save,
Clerk ordinary concept changes or managed Transcript publication, or Daily
Briefing. Those clients still depend on private-draft checks, reviewed
plans or managed publication state not supplied by ordinary CRUD receipts.
BHO journal editing, deletion and opening a missing day are not enabled by
this slice. Work writing and other owners are unchanged.

Both clients passed focused tests against a noneditable InnerSanctum
wheel on disposable checkouts. No deployment, service restart,
binding/grant change, hold release or live write was performed.
Do not remove the owner hold to enable this one lane without first
reconciling and independently fencing every publisher that the hold covers.

The next source work can proceed without enabling any publisher:

1. **Personal and BHO Notes:** qualify an owner-only read and Save adapter
   against the retained private-draft generations. Keep any original Save
   receipts resolvable; a fresh InnerSanctum revision is not draft clearance.
2. **Clerk concept changes:** preserve owner review of the exact change,
   including the index and deletion protections, before replacing Apply.
3. **Clerk history:** use the [private archive](clerk-archive.md) and link
   edits from the canonical audit, rather than restoring automatic Transcript
   concepts. Daily Briefing remains held; any future Briefing change must
   reconcile retained attempts separately.

Native document/event writers, lifecycle markers, moves and distribution
are outside this slice. Do not replay old requests into new operations to
rebuild missing receipts.

## Notes Save client source slice

MatterKeep Personal can now select a Notes-only adapter for the adopted
checkout. The two existing save surfaces—Personal's owner editor and
BHO's delegated Source editor—keep their authentication, source revision,
draft generation, and response formats. The old Personal writer remains
ineligible. Only InnerSanctum publishes the canonical note, parent index
if the title changed, and audit log. No BHO client code change is needed.

The adapter verifies the stopped checkpoint named in the successor marker
and requires the original Notes database and active owner. It keeps old
delegated receipts readable under their original, still-valid grant. A
new Save freezes its request privately. If interrupted, the adapter checks
the matching InnerSanctum receipt before advancing the draft generation.
It never recovers a canonical write itself, uses a new request to guess
the outcome of an old one, or replays a request after revocation.

This is source work on disposable data, not a live Note compatibility
check or release approval. Before rollout, verify the exact checkpoint,
runtime, Note schemas and indexes, owner binding, and BHO grant and hold.
Keep Clerk, managed publishers, and the Work socket disabled. Preserve
the current Notes database and InnerSanctum receipts if rolling back the
client; do not restore the legacy writer or overwrite current data.

The [Notes Save rollout card](notes-save-rollout.md) pins the rehearsed
candidate and separates read-only preflight from live activation.
