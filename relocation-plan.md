# Personal v0.2 relocation plan

**Status: prepared for review, not authorized to execute.** The destination is
this checkout's `OKF/` and sibling `SourceFiles/`. The SynologyDrive store
remains authoritative until verified cutover. This plan does not convert OKF to
v0.3, change Auth or publisher grants, or retire the SynologyDrive copy.

## Before scheduling downtime

- [x] Qualify the relocation source on disposable data. The candidate
  noneditable wheel from MatterKeep `d33c4ff` passed 481 focused tests on the
  serving host's CPython 3.14.6. The four former Auth/receipt concurrency
  failures passed on both this candidate and the pre-relocation baseline on
  that interpreter. This was not a full-suite or live acceptance run.
- [ ] Select a deployment release. The tested wheel is **not** a drop-in for
  the two installed Personal consumers. It changes 10 package files outside
  the relocation commits, including Auth, managed publishers, workspace
  handling and Work-pilot modules. Installed dependency versions matched.
  Prefer a relocation-only candidate built and tested against the installed
  baseline. Review `app.py`, `cli.py`, `configuration.py`, `notes.py` and
  `recovery.py` explicitly: the installed baseline already differs in each
  of those relocation-touched modules. A broader release needs its own
  approval. Keep the tested wheel and comparison as evidence only.
- [ ] Identify the serving configuration, the independent local Personal
  operator configuration, and any registration or reader that still resolves
  the old path. Keep existing owner/actor, Notes and Auth locations, route,
  grants, and publisher holds unchanged. Prepare inactive configs that select
  the new roots and the explicit catalog. Record the old and candidate config
  digests and launcher selections privately. Where protected launcher settings
  need elevation, arrange for the owner to make or verify that selection.
- [ ] Use `MatterKeep/Personal/publisher-coverage.md` and the latest deployment
  record to identify active publishers. Check ordinary Clerk Transcripts,
  Daily Briefing (which publishes both a Note and a Transcript), and BHO's
  delegated editors. Do not infer a drain from a disabled broker or an empty
  queue; reconcile any submitted, uncertain, or partially delivered operation
  before the stop.
- [ ] Confirm the checkout, the retained-copy and checkpoint directories, and
  working space on the service host. The checkout must have a physical `.git/`
  and root ignore rules `/OKF/` and `/SourceFiles/`, with neither tree in the
  Git index or `HEAD`. Relocation staging, target `OKF/`, and private Notes
  storage must be on the same filesystem; plans, checkpoints, and private
  state must remain outside Git. Pause Git operations that can move, stage,
  or remove ignored files throughout the maintenance window.
- [ ] Set aside a private `0700` directory outside Git to retain the existing
  InnerSanctum copies as-is. They are incomplete and their current permissions
  do not qualify. Keep the earlier verified stage and private diff for
  reference only, not as the final source. Use source bytes as the baseline;
  retain the differing local movie record without merging it during cutover.
  Confirm an independent backup destination for `OKF/` and `SourceFiles/`
  before making this checkout their permanent home.

### Read-only control map

| Surface | Verified or documented boundary |
| --- | --- |
| Personal server | `system/com.matterkeep.personal.barry` owns the loopback `5564` listener. The loaded selection invokes `matterkeep_personal.cli` with a private config on CPython 3.14.6. The root-owned `0600` launcher was not readable to this session; compare its exact bytes in the owner's Terminal before control. |
| Personal operator | The independent `~/.local/share/matterkeep-personal-log-operator/bin/personal-log-entry` wrapper selects CPython 3.14.6 and passes a config to the CLI. Bind its exact runtime and config alongside serving. |
| BHO / Clerk | `gui/501/com.matterkeep.dashboard` owns the loopback `5555` listener. The documented drain order is BHO before Personal if a BHO stop is approved. Shared OpenCode can host Clerk tools independently of that service: a BHO stop alone is not proof of exclusion. |
| Publisher and sync controls | Confirm the existing owner-specific application hold and independent client, Briefing, manual, local-operator, and inbound-sync exclusions. No journal, hold, sync task, or publisher was changed or verified drained in this preflight. Never use a legacy `allow-write` to resume the coordinated clients. |

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
   The earlier inventory saw one `0644` file in the source `OKF/`; recheck
   rather than assuming it has been corrected. A custody refusal is a stop:
   identify exact offending paths and seek approval for any source repair;
   do not bulk `chmod` or omit files merely to get a checkpoint.
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
   digest. **Pause for explicit approval of that exact digest.** Planning
   does not switch the writer or authorize apply.
5. **Apply and select the new configuration.** Only with exact approval and
   continued exclusion, run `relocation-apply` with the old config and
   approved plan digest. After read-back confirms both the Notes database and
   new marker, select the approved configs for both Personal consumers and
   update only registrations or readers identified in preflight. Use the
   checkout opt-in, the new `OKF/`, the new `SourceFiles/`, and its exact
   catalog path. Restart only the approved service; keep publishers held.

## Acceptance and handback

- [ ] Verify the serving and operator selections against the approved artifact
  and config digests. Read a known note and a catalog-backed attachment through
  their normal consumers. Check that the original note ID, draft, and a known
  completed receipt remain available without resending its request.
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
