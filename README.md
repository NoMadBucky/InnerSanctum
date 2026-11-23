# InnerSanctum

InnerSanctum is a local-first personal knowledge bundle for collecting notes and
finding their sources. Start with the [bundle index](index.md). The bundle follows
[Open Knowledge Format (OKF) v0.3](references/okf/SPEC.md).

## Format requirements

Reading and writing bundle files requires only:

* [YAML 1.2](https://yaml.org/spec/1.2.2/) with the core schema for frontmatter.
* CommonMark with [GitHub Flavored Markdown (GFM) tables](https://github.github.com/gfm/#tables-extension-)
  and footnotes in `[^label]` form for document bodies. No other Markdown
  extensions are required.
* [RFC 3339](https://www.rfc-editor.org/rfc/rfc3339) for dates and timestamps.
  Date-times include `Z` or an explicit UTC offset; date-only values use
  `YYYY-MM-DD` where allowed.
