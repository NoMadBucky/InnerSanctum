# InnerSanctum

InnerSanctum is a local-first personal knowledge project for collecting notes and
finding their sources. Start with the [project index](index.md). The target format
for its Personal bundle is [Open Knowledge Format (OKF) v0.3](OKF_SPEC/SPEC.md).

## Project hub

Use the [project registry](project-registry.md) to route work for seven sites.
In OpenCode v2, new sessions in InnerSanctum default to the read-only
`project-hub` agent. You can name a URL directly or use:

```text
/project-status
/project-status https://matterkeep.com/
/project-plan design review a navigation change
```

Status is the last recorded evidence, not a health check. Both commands select
`project-hub` in the current session. Switch to Build for authorized
InnerSanctum development, or open the owning checkout in a separate session for
source work there. The hub configuration does not change global permissions,
other agents, or any deployment.

## Local Personal store

* [`OKF/`](OKF/index.md) holds the live MatterKeep Personal v0.2 bundle,
  including its own indexes and log.
* [`SourceFiles/`](SourceFiles/) is the sibling store for native attachments and
  the source catalog. It is outside the OKF bundle.

Both folders are local to this checkout and intentionally ignored by Git. They
do not come with a clone and need their own backup. InnerSanctum is the sole
writer; the former SynologyDrive store is retained but inactive. Keep inbound
sync excluded. The [cutover record](create-cutover.md) records current writer
authority. Any v0.3 conversion is separate.

## Concepts

InnerSanctum can create, read, update and delete ordinary Markdown concepts
without MatterKeep or a browser. Use **disposable, standalone bundles outside the
checkout**. Standalone mode refuses repository paths, SynologyDrive and
bundles carrying Personal's writer marker. Do not remove a marker to make
a bundle eligible. The [live Create cutover](create-cutover.md) verified that
InnerSanctum is now the sole writer of `OKF/`. MatterKeep Personal remains
offline. The BHO dashboard is online with its Personal publishers and delegated
Notes editing disabled.

Use an existing bundle with a root `index.md` and `log.md`, a declaring index
with a fenced `okf_schema` block, and a destination index with a
`## Directory Listing` section. A [route](concept-routes.toml) points to the
declaring index and selects the exact destination; `directory` inside the
schema still limits the allowed subtree. Routes cannot override the schema.
Add types as data, not Python code. The supplied Video route expects the
declaration and destination index at `Resources/videos/index.md`.

```sh
uv run --locked innersanctum concept template Video \
  --bundle "$DISPOSABLE_OKF" --routes concept-routes.toml

uv run --locked innersanctum concept create --from "$DRAFT" \
  --bundle "$DISPOSABLE_OKF" --routes concept-routes.toml --actor "human:your-name"
```

For real records in the adopted checkout, use `--live-checkout "$CHECKOUT"`
instead of `--bundle`. Use standalone mode for tests and examples.

Supply the actual producer as `--actor`. The draft supplies `type`, `title`,
other schema fields and any Markdown body. The command allocates a seven-digit
`bho:` ID and adds generation provenance without reformatting the draft. It
validates required and declared fields, leaves extra metadata alone unless
forbidden, and refuses unsupported schema rules. It writes the new concept
without overwriting an existing file, adds the parent index entry and audit
entry, then verifies all three. It returns a JSON path, ID and source revision.
Create does not deduplicate by title or external URL, create directories, or
fetch attachments.

Read by exact bundle-relative path or `bho:` ID. Read returns JSON with the
original `markdown` and a SHA-256 `revision`. For Update, start from that
Markdown (for example, extract it with `jq -j .markdown`), then supply the full
edited document. Keep the type, ID and other managed fields (`generated`,
`verified`, `owner`, `scope`). Update validates against the existing type
declaration and changes the parent index label if the title changes. It does
not move the concept. Updates requiring unsupported legacy YAML are refused.

```sh
uv run --locked innersanctum concept read "$SELECTOR" --bundle "$DISPOSABLE_OKF"

uv run --locked innersanctum concept update "$SELECTOR" --bundle "$DISPOSABLE_OKF" \
  --from "$EDITED_MARKDOWN" --revision "$REVISION" --actor "human:your-name"

uv run --locked innersanctum concept delete "$SELECTOR" --bundle "$DISPOSABLE_OKF" \
  --revision "$REVISION" --actor "human:your-name" --dry-run
```

Delete permanently removes the concept file and its parent listing, leaving
an audit entry that keeps the ID from being assigned again. It does not remove
attachments or rewrite other links to the concept. Delete and title changes
refuse missing, duplicate or nonstandard
parent listing entries rather than guessing which text to change. Update and
Delete both refuse a stale revision: read the current version before retrying.

For Clerk edits, the [Clerk archive workflow](clerk-archive.md) shows how
to keep conversation exports outside OKF and link their exact snapshots
from the edit audit. It is available for standalone rehearsals only.

## Personal journal

For a real entry, provide a Markdown file or pipe the text on stdin. Use the
actual author for `--actor`. For examples and development, substitute
`--bundle "$DISPOSABLE_OKF"` and use a standalone fixture.

```sh
uv run --locked innersanctum journal add --live-checkout "$CHECKOUT" \
  --from "$ENTRY_FILE" --actor "human:your-name" --subject "Optional subject"
```

The command defaults to the current local timestamp and `Personal` category.
To record a different time or day, pass `--at` with an ISO 8601 timestamp
including seconds and a UTC offset; `--date`, if supplied, must match that
timestamp's calendar date. Entries accept paragraphs with inline Markdown.
To append only to an existing day, pass its exact `--revision` from
`journal read`. Clients can pass `--entry-json` with `--from -` to supply
both `markdown` and `subject` (string or `null`) on stdin rather than
putting a private subject in process arguments.

`journal add` uses the Journal schema and the date-named layout
`Documents/journal/YYYY-MM/YYYY-MM-DD.md`. It inserts the entry in timestamp
order, without rewriting earlier entries or frontmatter. If the day is new,
it creates and links it in the monthly and journal indexes, creating the
month and its index if needed. It refuses an ambiguous existing ledger or an
existing month with no index. The root audit log records the operation but
not the entry text or subject.

`journal read DATE` returns JSON with the day's `revision` and a numbered list
of entries, each with `at` and `markdown`. Use the reported entry number and
day revision together. Any change to the day, including a new entry, makes
the old revision stale.

```sh
uv run --locked innersanctum journal read "$DAY" --bundle "$DISPOSABLE_OKF"

uv run --locked innersanctum journal update "$DAY" --bundle "$DISPOSABLE_OKF" \
  --entry "$NUMBER" --revision "$REVISION" --from "$ENTRY_FILE" --actor "human:your-name"

uv run --locked innersanctum journal delete "$DAY" --bundle "$DISPOSABLE_OKF" \
  --entry "$NUMBER" --revision "$REVISION" --actor "human:your-name" --dry-run
```

Update replaces the entry text and keeps its original time and author.
Use `--category` or `--subject` to change those fields, or `--clear-subject`
to remove the subject. Delete removes only the selected entry. The day's
frontmatter and indexes stay in place, even when you delete the last entry.
The audit records the operation, not the entry text or subject.

## Preview and recovery

All write commands for concepts and journal entries accept `--dry-run` to
validate and report affected paths without writing. A Create preview does not
reserve its proposed ID. Concept and journal operations share one lock and
one pending write in the private `.innersanctum/` directory.

After an interruption, use `concept recover` or `journal recover` with the
same target instead of resubmitting. Recovery finishes the original changes
or stops if it encounters unexpected bytes; it does not roll back or merge.
Files change one at a time. The lock coordinates InnerSanctum writes on one
host, not other readers, sync or another writer. If no write is pending,
check the record and audit log before resubmitting: the command may have
finished without reporting success.

For integrations, all six mutating commands accept a stable `--request-id`
(16–128 ASCII letters, digits, underscores or hyphens). The writer retains a
private receipt after canonical read-back and before clearing the pending
write. After recovery, an exact retry with the same ID and arguments returns
the original receipt, not a fresh write or evidence of current content.
Reusing an ID with different arguments is refused. Dry runs do not reserve
the ID or write a receipt. Keep receipts with the bundle's writer state;
removing one loses the retry guarantee for that ID.

Clients of the adopted checkout can inspect an ID with `concept receipt`.
This does not recover anything or return source. It reports `pending` if
any canonical write is pending; otherwise it reports `missing` or a
`completed` historical receipt and its argument fingerprint. An ID-based
`concept update` can also require the original `--expect-path`. Clients can
pin the adoption receipt digest with `--expect-adoption` on either command.

The [publisher migration record](create-cutover.md#journal-client-source-slice)
distinguishes the journal adapters from the publishers that are still held.

## Format requirements

The v0.3 target uses:

* [YAML 1.2](https://yaml.org/spec/1.2.2/) with the core schema for frontmatter.
* CommonMark with [GitHub Flavored Markdown (GFM) tables](https://github.github.com/gfm/#tables-extension-)
  and footnotes in `[^label]` form for document bodies. No other Markdown
  extensions are required.
* [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) for dates and timestamps.
  Date-times include `Z` or an explicit UTC offset; date-only values use
  `YYYY-MM-DD` where allowed.

## Specification source

[`OKF_SPEC/SPEC.md`](OKF_SPEC/SPEC.md) is an unmodified copy of the
[upstream specification](https://github.com/open-knowledge-format/open-knowledge-format/blob/527e81aff55992be21507e97004286789126f88c/SPEC.md)
at commit `527e81aff55992be21507e97004286789126f88c`. The upstream
[Apache License 2.0](OKF_SPEC/SPEC-LICENSE.txt) applies to the vendored specification,
not to the rest of this repository.
