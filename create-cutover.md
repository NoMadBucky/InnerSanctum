# Live Create cutover

## Status

The InnerSanctum writer is **not live**. MatterKeep Personal still owns
`OKF/`, its writer marker is present, and the CLI refuses live Create under
that marker. A candidate for an exact-checkout handover has been rehearsed
on a disposable checkout.
This is separate from the completed [Personal relocation](relocation-plan.md)
and does not change the bundle's OKF v0.2 format or the `SourceFiles/` binding.

A November 24 read-only check resolved `Video` to `Resources/videos` from
116 indexes and found 1,008 unique IDs. In-memory formatting checks passed
for the videos index and the root audit log. The implementation now preserves
repeated historical date sections and reads legacy IDs without interpreting
tagged metadata. It still refuses an ambiguous target date or ID. These checks
do not establish writer exclusion, service readiness, or live publication.

## Decide what stays running

Use one writer for the entire bundle, not one writer per collection. Create
changes the shared root audit log and checks bundle-wide IDs. Until an explicit
reader-only deployment is qualified, the simplest first handover is to keep
the Personal writer stopped and keep its publishers held.

| Existing surface | Required disposition before cutover |
| --- | --- |
| Personal editor, local operator commands and delegated clients | Disable write access for this workspace. Preserve drafts, completed receipts and recovery state. |
| Clerk ordinary edits and managed Transcript publication | Hold and reconcile in-flight operations; retain confirmed receipts. A new broker is separate work. |
| Daily Briefing | Hold publication and reconcile both halves of each Note/Transcript pair. Do not replay uncertain attempts. |
| Personal browsing, search and attachments | Keep offline for the first handover unless a reader-only configuration is verified unable to write, recover, provision or take over authority. |
| Inbound sync and manual writes | Keep excluded. A local lock cannot enforce remote or noncooperating writer exclusion. |

## Handover gates

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

## Candidate commands

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
