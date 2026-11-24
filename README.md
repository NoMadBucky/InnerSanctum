# InnerSanctum

InnerSanctum is a local-first personal knowledge project for collecting notes and
finding their sources. Start with the [project index](index.md). The target format
for its Personal bundle is [Open Knowledge Format (OKF) v0.3](OKF_SPEC/SPEC.md).

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

## Standalone concept creation

InnerSanctum can create an ordinary Markdown concept without MatterKeep or a
browser. During development, use **disposable, standalone bundles outside the
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
fetch attachments. Full bundle validation, Read, Update and Delete are future work.

Use `--dry-run` to validate and preview the affected paths without writing; it
does not reserve the proposed ID. During Create, the private
`.innersanctum/` directory holds a local lock and a pending journal. If
interrupted, use `concept recover --bundle "$DISPOSABLE_OKF"` rather than
submitting another Create. Recovery finishes the original changes or stops if
it encounters unexpected bytes. It does not roll back or merge changes. File
replacements are sequential: the lock coordinates InnerSanctum commands on
one host, not readers, sync, or another writer. If an interrupted command has
no pending journal, check the concept index and audit log before resubmitting:
the write may have finished before the command could report success.

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

`journal add` uses the Journal schema and the date-named layout
`Documents/journal/YYYY-MM/YYYY-MM-DD.md`. It inserts the entry in timestamp
order, without rewriting earlier entries or frontmatter. If the day is new,
it creates and links it in the monthly and journal indexes, creating the
month and its index if needed. It refuses an ambiguous existing ledger or an
existing month with no index. The root audit log records the operation but
not the entry text or subject.

`--dry-run` validates and reports the proposed paths without writing. After
an interruption, use `journal recover` with the same target instead of
submitting the entry again. Journal and concept operations share one pending
write and one recovery mechanism.

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
