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
do not come with a clone and need their own backup. MatterKeep Personal is the
sole writer; the former SynologyDrive store is retained but inactive. Keep
inbound sync excluded. The [relocation plan](relocation-plan.md) records the
binding change and verification. Any v0.3 conversion is separate.

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
