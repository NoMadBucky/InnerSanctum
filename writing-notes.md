---
type: Guide
title: Writing notes
description: How to add portable notes, link them, and record their sources.
sources:
  - id: okf-spec
    resource: references/okf/SPEC.md
    title: Open Knowledge Format v0.3 specification
---

# Writing notes

Add each note as a UTF-8 `.md` file. Start with YAML frontmatter between two `---` lines. A non-empty `type` is the only required field; use `Note` for a general note. Add a `title` or `description` when it helps someone find the note.[^okf-spec]

Use standard Markdown links with relative file paths rather than `[[wikilinks]]`. For claims drawn from a source, add it to `sources` and use a Markdown footnote whose label matches the source's `id`. Don't add verification metadata unless someone or something actually checked the content against its sources.[^okf-spec]

Use descriptive, lowercase filenames with hyphens. Update the [bundle index](index.md) as useful entry points emerge. Keep sensitive notes local unless you explicitly intend to share them.

[^okf-spec]: [Open Knowledge Format v0.3](references/okf/SPEC.md), §§3–6.
