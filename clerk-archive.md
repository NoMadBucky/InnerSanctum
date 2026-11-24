# Clerk archive and edit provenance

**Qualified on disposable standalone and adopted bundles, not deployed.**
A Clerk session is not an OKF concept. Its conversation export lives in the sibling
`SourceFiles/ClerkArchive/` tree. A session with no canonical edits does
not add anything to `log.md`.

## Stable private references

The producer assigns one random, opaque 32-character lowercase hex ID
per session and retains it with the native session mapping. Each
nonblank UTF-8 Markdown export (at most 8 MiB) is stored verbatim in an
immutable snapshot. The reference is `clerk-archive:SESSION/SHA256`:
the session ID stays fixed as the conversation grows, and the digest
selects exactly the snapshot available for a particular edit. Repeating
an identical archive operation returns the existing reference. A later
snapshot does not overwrite older snapshots.

The URI is a standard Markdown link to an external resource; it is not
a bundle path, a public URL, or an access token. The local archive read
command resolves it against the selected bundle's sibling archive and
checks the exact bytes. No browser protocol handler, web route, source
catalog entry, or attachment-search integration is installed.

## Disposable workflow

Use an existing standalone bundle **outside any repository**, with an
owned `0700` sibling `SourceFiles/ClerkArchive/` and `0700` `SourceFiles`.
Do not point these commands at the live checkout.

```sh
uv run --locked innersanctum clerk-archive store \
  --bundle "$DISPOSABLE_OKF" --session "$SESSION" --from "$PRIVATE_EXPORT"

uv run --locked innersanctum concept update "$CONCEPT_ID" \
  --bundle "$DISPOSABLE_OKF" --from "$REVIEWED_SOURCE" \
  --revision "$OPENED_REVISION" --actor "$ACTOR" \
  --request-id "$REQUEST_ID" --clerk-session "$ARCHIVE_REFERENCE"
```

Give the actual producer as `--actor`. The update needs a stable request
ID, the exact original frontmatter, and a replacement body. It verifies
the archived snapshot before accepting the write. InnerSanctum publishes
one audit entry identifying the action, concept, actor, resulting
revision, and archived session. The note and its audit entry use the same
recoverable write; Clerk does not write a second log entry. The receipt
retains the same session reference. Changes to the archive reference are
changes to the request, not retries.

To follow the audit link, pass the URI verbatim to the private resolver.
Redirect the exact bytes to a new private file rather than printing
conversation content to a shared terminal:

```sh
(
  umask 077
  set -C
  uv run --locked innersanctum clerk-archive read "$ARCHIVE_REFERENCE" \
    --bundle "$DISPOSABLE_OKF" > "$NEW_PRIVATE_EXPORT"
)
```

Keep archive snapshots and receipts together in backups. If an archive
store is interrupted, resubmit the exact export to finish an intact
stage. The command refuses a partial or conflicting stage. If an edit
is interrupted, use `concept recover` with the same target; it refuses
to publish an audit link if the frozen snapshot is missing or changed.
Recovery is roll-forward, not atomic visibility to readers.

Use `concept receipt "$REQUEST_ID" --bundle "$DISPOSABLE_OKF"` to check
the original request without retrying or running recovery. The disposable
BHO review lane uses this to settle interrupted acknowledgements.

## Live boundary

An adopted bundle requires a separate, explicitly provisioned
`SourceFiles/ClerkArchive/.owner-binding.json`. `clerk-archive bind`
requires the exact adoption digest, an existing private empty archive,
the Personal owner, and a publisher namespace. The resulting digest
pins that owner, namespace, adoption, bundle identity and archive
directory identity. `clerk-archive binding`, `store` and `read` require
both pins. Adopted `concept update` additionally pins the Note ID and
path, uses the bound namespace, and requires an exact archived session.
An archive reference or digest is not a credential.

Recovery of an interrupted adopted Clerk write requires
`concept recover` with both original pins and the unchanged snapshot.
Older un-attributed writes retain their existing recovery format.
If an archive is moved or restored into a different directory inode,
the old pin will not authorize it; do not recreate the binding or
restore an older database over accepted edits.

Only disposable adopted checkouts were provisioned. The default-off BHO
handoff can archive and review an edit from a finished Personal Clerk
session without using the old Transcript publisher. It does not resume
prompt admission. Live `SourceFiles/`, Notes Save, other publishers and
historical Transcripts were untouched. Approve the exact session, custody,
retention, backups, publisher grant and backout before live rollout.
