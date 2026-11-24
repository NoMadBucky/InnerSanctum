# Personal v0.2 relocation plan

**Status: prepared for review, not authorized to execute.** The destination is
this checkout's `OKF/` and sibling `SourceFiles/`. The SynologyDrive store
remains authoritative until verified cutover. This plan does not convert OKF to
v0.3, change Auth or publisher grants, or retire the SynologyDrive copy.

**Checkpoint-only window completed.** The stopped OKF/Notes pair passed
MatterKeep's offline verifier. Separate local backups of `SourceFiles/` and
Auth passed byte-for-byte verification; all 84 cataloged attachments matched.
The approved root `.DS_Store` mode repair changed no file bytes. Both services
returned on their original launchers and bindings. The retained local
checkpoint protects against a failed move, not disk loss. Before a later
cutover, take another fresh stopped checkpoint; this one does not authorize
relocation or supersede later writes.

## Before scheduling downtime

- [x] Qualify the relocation source on disposable data. The candidate
  noneditable wheel from MatterKeep `d33c4ff` passed 481 focused tests on the
  serving host's CPython 3.14.6. The four former Auth/receipt concurrency
  failures passed on both this candidate and the pre-relocation baseline on
  that interpreter. This was not a full-suite or live acceptance run.
- [x] Build a relocation-only release candidate from the matching installed
  serving and operator package payloads. The broader `d33c4ff` wheel is
  evidence only; it differs in 10 unrelated files. The replacement candidate
  changes or adds only 12 relocation files and leaves the other 30 byte
  identical. It passed 941 focused tests on CPython 3.14.6 with matching
  installed dependency versions and byte-identical first-party dependency
  packages. An independent patch replay built the same wheel bytes.
- [ ] Select the relocation-only wheel for both Personal consumers during
  an approved window. Its SHA-256 is
  `258602f4e4a452af26c3136d7bb6b7a6cb7adc9d0dd617040e66e47c9260f064`.
  The private qualification packet holds the wheel, replay patch, and
  baseline and candidate hashes. Recheck both installed baselines immediately
  before selection and preserve their dependency payloads. Do not install the
  broader wheel or replace the deployed OKF validator with a same-version
  source build: two validator files differ.
- [x] Prepare the inactive Personal config. The loaded serving job and local
  operator wrapper select the same TOML file. A private candidate replaces
  only `okf`, `source_root`, and `source_catalog`, and adds
  `innersanctum_checkout`. The original config and wrapper were verified
  unchanged. The owner-local helper verified the root-owned launcher's bytes
  during the checkpoint window; recheck them before another service stop.
  Runtime validation waits for the private replacement trees.
- [x] Build and rehearse the Barry-only BHO binding. The candidate keeps
  the existing registry rules for all other owners and leaves BHO's runtime
  state where it is. A matching private selector and Barry's existing
  registry row are both required to read `InnerSanctum/OKF`. A partial
  transition fails closed. Brokered record and attachment reads use the
  new paths; direct BHO writes and new native Clerk path access are denied.
  Existing managed Personal API grants are not changed. On CPython 3.14.6,
  451 focused and 81 managed-reader checks passed (the groups overlap).
  The legacy Clerk Desk suite had the same 96 failing cases on the
  unchanged baseline and candidate, with no candidate-only failures.
- [x] Prepare the BHO transition for review without applying it. The
  private packet pins the serving source and launcher inputs, Clerk's
  independent records and concept bridge files, the absent
  `system/innersanctum-barry.json` selector, and the expected and intended
  values of Barry's single registry row. An in-memory rehearsal against the
  observed registry schema changed exactly that row, rejected a repeat,
  and rolled back without changing other rows or schema. The review digest
  is `24d655d8ced741ced28d5af6e43e571464d09fc762521bde912be19fe2eda34d`;
  it is not cutover approval or a frozen live registry preimage.
- [ ] During the approved stopped window, recheck the source, launcher and
  Clerk inputs, confirm the selector is still absent, and retain a verified
  private registry backup. Freeze the exact BHO selection alongside the
  Personal relocation plan for approval. Keep independent Clerk clients held
  with BHO until the source, selector, and Barry row agree. Do not change the
  global Personal content base, other owner rows, session bindings, or
  publisher journals. The file checks did not exercise live Clerk tools.
- [ ] Use `MatterKeep/Personal/publisher-coverage.md` and the latest deployment
  record to identify active publishers. Check ordinary Clerk Transcripts,
  Daily Briefing (which publishes both a Note and a Transcript), and BHO's
  delegated editors. Do not infer a drain from a disabled broker or an empty
  queue; reconcile any submitted, uncertain, or partially delivered operation
  before the stop. A read-only preflight found no pending intents or incomplete
  receipts in the nine sampled Personal tables, and all 86 frozen Clerk
  Transcript operations had confirmed read-back. Four Clerk deliveries lacked
  a provider message mapping and did not match an observed session fence or
  ready Briefing day. One other action was marked `submitted` / `not-sent`.
  Two matching, complete OpenCode history reads for each of the five
  original actions found one exact new user message after the stored
  prefix, a final response, and a success marker. All five inboxes were
  empty. Even the action marked `not-sent` had this evidence; do not
  resend it. None had a confirmed action-bound Clerk receipt. The five
  current canonical Transcripts and their existing receipts matched
  Personal's records. Two Transcripts contain the exact final response;
  three do not contain it verbatim. Before scheduling, review an exact
  no-resend recovery or preservation disposition for these original actions.
  Do not edit the journals or reuse the old, deferred session-fence preview.
  One old Briefing recovery manifest remains `paired` even though its day
  is `ready` with both publications confirmed; treat that as bookkeeping, not
  permission to republish. The sampled concept operation marked `uncertain`
  matched its exact local closure, and the unsent BHO Save form contained
  only its original source. These samples do not establish a writer hold.
- [ ] Confirm the checkout, the retained-copy and checkpoint directories, and
  working space on the service host. The checkout must have a physical `.git/`
  and root ignore rules `/OKF/` and `/SourceFiles/`, with neither tree in the
  Git index or `HEAD`. Relocation staging, target `OKF/`, and private Notes
  storage must be on the same filesystem; plans, checkpoints, and private
  state must remain outside Git. The current checkout, Notes, and private
  plan directory passed the same-filesystem check; the existing data roots
  still have mode `0755`. Pause Git operations that can move, stage, or
  remove ignored files throughout the maintenance window.
- [x] Preserve both existing InnerSanctum copies outside Git. The private
  archive has 459 OKF files and 85 source files, all independently verified
  by SHA-256; it retains the differing movie record and leaves both originals
  in place. This is a backup of the incomplete local copies, not a stopped
  checkpoint or a backup of the authoritative store.
- [x] Record Barry's decision to forego an independent off-device backup
  for this cutover. Retain the earlier stage for reference only. A fresh,
  verified stopped OKF/Notes checkpoint and separate local `SourceFiles/`
  and Auth preservation are still required. Same-host copies do not
  protect against loss of the serving disk.

### Read-only control map

| Surface | Verified or documented boundary |
| --- | --- |
| Personal server | `system/com.matterkeep.personal.barry` owns the loopback `5564` listener. The loaded selection invokes `matterkeep_personal.cli` with a private config on CPython 3.14.6. The checkpoint helper verified the root-owned `0600` launcher in the owner's Terminal; recheck it there before control. |
| Personal operator | The independent `~/.local/share/matterkeep-personal-log-operator/bin/personal-log-entry` wrapper selects CPython 3.14.6 and passes the same TOML as the serving job. Verify both runtime selections against that shared binding. |
| BHO / Clerk | `gui/501/com.matterkeep.dashboard` owns the loopback `5555` listener. Its deployed registry still selects the old tree. The documented drain order is BHO before Personal if a BHO stop is approved. Shared OpenCode can host Clerk tools independently of that service: a BHO stop alone is not proof of exclusion. |
| Publisher and sync controls | A read-only sample found the owner-specific BHO maintenance flag **off**; this is not evidence for or against any other write gate. Confirm separate exclusion for Clerk, Briefing, manual and local-operator writers, and inbound sync. No journals were verified drained, and no holds, publishers, or sync tasks were changed. Never use a legacy `allow-write` to resume coordinated clients. |

## Stopped-writer window

1. **Drain and hold.** The owner approves the exact maintenance window, service
   and launcher changes, and which publishers are paused. Drain Personal and
   client publication journals without resending requests. Prevent automatic
   restarts, manual writes, and inbound sync touching either tree. Do not stop
   unrelated services or change unrelated sync tasks. If an intent is pending
   or an outcome is uncertain, stop and reconcile the original workflow.
2. **Checkpoint the old pair.** Run `checkpoint-create` under the unchanged old
   configuration and `checkpoint-verify` offline using the independently
   retained receipt digest. The stopped-writer flag asserts exclusion; it
   does not establish it. Retain the current Auth authority separately under
   its existing backup procedure, and independently back up `SourceFiles/`
   (the OKF/Notes checkpoint covers neither). Inventory hidden files as well.
   The checkpoint-only window changed the source `OKF/.DS_Store` from `0644`
   to `0600` without changing its bytes. Verify its custody and mode again;
   stop on drift rather than assuming permission for another repair. No
   other mode repair, deletion, or omission on the live source is approved.
3. **Replace only the destination copies.** Preserve both current InnerSanctum
   trees in the private hold directory before installing anything. Prepare a
   fresh, byte-for-byte OKF copy from the stopped checkpoint, including the old
   writer marker. Prepare `SourceFiles/` from the stopped source. Independently
   compare relative paths, file bytes by SHA-256, and all catalog targets by
   size and digest. Verify ownership, `0700` directories, `0600` single-link
   files, and no symlinks. Install the verified copies at the two final paths
   while writers remain stopped, and repeat destination and Git checks there.
4. **Freeze and approve the binding change.** Follow the *New-path relocation*
   and *InnerSanctum checkout opt-in* sections of
   `MatterKeep/Personal/OPERATIONS.md`. Run `relocation-plan` with the **old**
   config and digest, stopped checkpoint and receipt digest, `--target-okf`
   naming this checkout's `OKF/`, and `--target-innersanctum-checkout` naming
   this checkout. Retain the plan, its staging directory, and its returned
   digest, along with the exact Personal runtime and config and the stopped
   BHO selection. **Pause for explicit approval of the exact relocation
   digest and accompanying selections.** Planning does not switch the
   writer or authorize apply.
5. **Apply and select the new configuration.** Only with exact approval and
   continued exclusion, run `relocation-apply` with the old config and
   approved plan digest. After read-back confirms both the Notes database and
   new marker, select the approved configs for both Personal consumers and
   use the checkout opt-in, the new `OKF/`, the new `SourceFiles/`, and its
   exact catalog path. With BHO stopped and Clerk held, install and verify
   the approved BHO source and selector, then update just Barry's pinned
   registry row. Read back all three before restarting BHO. Restart only
   the approved services; keep publishers held.

## Acceptance and handback

- [ ] Verify the serving and operator selections against the approved artifact
  and config digests. Read a known note and a catalog-backed attachment through
  their normal consumers. Check that the original note ID, draft, and a known
  completed receipt remain available without resending its request.
- [ ] Verify the BHO and independent Clerk brokered reads at the new path
  and verify that the relocated workspace refuses native BHO writes. Do not
  restart shared OpenCode or alter existing grants for these checks.
- [ ] Make one owner-approved write through the normal Personal interface.
  Verify the exact resulting record and expected index/log updates at the new
  path, no changes at the old path, and no unresolved publication. Record a
  fresh clean checkpoint at the new path: stop the writer again after the
  canary, verify offline, then restore the approved service selection before
  handback. Only then resume approved publishers through their existing
  controls; keep the old tree intact and inactive.
- [ ] Retain the old checkpoint, old source as read-only evidence, the displaced
  copies, decision on the local movie record, and the new backup separately
  from Git. Any future v0.3 conversion is a separate operation.

## If something fails

| Point of failure | Response |
| --- | --- |
| Before `relocation-apply` | Keep the destination inactive. If the old binding and original pair are verified unchanged, resuming the original configuration is a separate owner decision. |
| Apply interrupted or outcome unknown | Keep both trees, the plan, its staging directory, and the newest state. Keep writers stopped. Reconcile using the **same** approved plan and digest; do not replan, initialize, or restart. |
| After apply or after a write at the new root | Do not flip back to the old config: the Notes database now binds the new path. Preserve the newest data, drafts, receipts, and Auth. Obtain separate recovery approval, including reconciliation of any newer writes, before any restore. |
