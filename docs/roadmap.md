# InnerSanctum roadmap

**Proposed, 2026-11-25.** This is a product plan, not a release schedule or
approval for live work.

## Long-term goal

Make a personal OKF bundle easy to start, useful to explore, and safe to
develop over time. The bundle itself is the source of truth. A person can
still read the Markdown without the app, and the UI's search indexes and
graph can be rebuilt from it.

| Component | Responsibility | What it does not own |
| --- | --- | --- |
| **OKF Builder** | Lead a back-and-forth conversation about purpose, scope, sources, and useful concept types. Draft a bundle structure and sample concepts for review. | Ongoing editing or unreviewed setup changes. |
| **OKF Clerk** | Search and read the bundle, explain validation findings, guide source review, and apply approved changes through the guarded writer. | Direct writes to Markdown, indexes, or audit state; claiming verification just because validation passed. |
| **OKF Viewer** | Give the human a web-based card browser, facets, readable concept details, and navigable connections. Surface trust evidence and hand off edits or checks to the Clerk. | Canonical writes or a second source of truth. |

The first prototype should answer one question: **Can I find a concept,
understand its context, and safely change it without dropping to the shell?**
Start with the Clerk and Viewer together. A hand-authored bundle is enough
to test the loop; no Builder, production deployment, or sibling integration
is required.

## 1. Make one Clerk edit work end to end

Use a synthetic v0.3 bundle outside the checkout, rebuilt from a deterministic
fixture. Start with the existing Video route and a few cross-linked concepts.
Include similar titles, absent optional fields, both v0.3 link forms, and
at least one unresolved link. The fixture should make the interface's behavior
visible without copying private records or attachments.
First, verify that the guarded CLI can create, read, update, and delete on
that v0.3 fixture; treat this as a baseline check, not as live qualification.

Build the smallest web flow that can search by title or text, open a card,
read the Markdown and source references, and hand off an edit. Search can
start with plain text; semantic search is not a prerequisite. The Clerk
proposes a change against the revision the user opened. Show a readable diff
and any affected index or audit paths before confirmation. On approval, use
the existing CLI, then reopen the canonical record and refresh the card.
Show one schema refusal and keep the draft so the user can fix it. Validate
the mechanics with a deterministic proposal before adding an LLM. Use an
unverified record for this first edit; don't add a trust badge yet.

**Done when:** The user can find the intended record, approve a body change,
and see it in the detail and card views. A stale revision leaves the user's
draft intact and offers a fresh comparison instead of overwriting. One
successful operation produces one audit entry.

## 2. Round out CRUD and failure handling

| Action | Proposed user flow |
| --- | --- |
| **Create** | Choose a supported type and route, fill a schema-backed template, preview the target and required fields, then open the saved concept. A preview does not reserve an ID. |
| **Read** | Open from search, a facet, or a link. Show rendered Markdown, source references, and a raw view. The editor keeps the exact revision that was opened. |
| **Update** | Show the before/after change. Include the parent listing change when a title changes. Apply against the opened revision; don't offer a move in this prototype. |
| **Delete** | Confirm the exact title and path, note that deletion is permanent, and show known incoming links. Explain that the operation does not remove attachments or fix those links. |

Cover the expected failures: bad schema input, a stale revision, an ambiguous
parent listing, and an interrupted or uncertain write. For a retryable
integration request, retain a stable request ID for the same arguments;
distinguish a completed historical receipt from current content. An uncertain
write should lead to request status and documented recovery, not an automatic
new write. Keep ordinary concepts as the first scope; journal entries already
have their own date-and-entry workflow and can follow later.

**Done when:** All four operations work on the fixture. Successful writes
are reflected in canonical files, any affected listings, the audit, and the
Viewer after read-back. Refused writes don't change canonical files, and an
interrupted request can be reconciled without duplicating the operation.

### Clerk validation and trust

Use [OKF v0.3 conformance rules](../OKF_SPEC/SPEC.md#11-conformance) and
[provenance, trust, and lifecycle rules](../OKF_SPEC/SPEC.md#5-provenance-trust-and-lifecycle)
as distinct parts of the workflow:

| Question | Proposed Clerk behavior |
| --- | --- |
| **Is it valid?** | Explain OKF format findings separately from this bundle's schema and the writer's safety checks. Point to the field or file and say whether the proposed write is blocked. A broken link or missing optional metadata is not an OKF conformance failure. |
| **Where did it come from?** | Show `sources` and `generated` when present. Let the reviewer follow a claim's footnote to the matching `sources[].id`. Show an unresolved source or scope descriptor honestly; don't invent a citation or a credibility score. |
| **Was this version checked?** | Make verification a separate action against the exact opened revision and its sources or resource. Writing, approving an edit, and passing schema checks do not verify its claims. Record the actual verifier in `verified`; never record human review just because an assistant checked the material. |
| **Does it need another look?** | Show `stale_after` separately from the trust tier and lifecycle `status`. A human-reviewed concept can still be stale; stale does not mean false, and an unreadable review date does not mean fresh. |

Start with pre-save findings from the guarded writer. Later, explore a
read-only bundle check that lists findings and links to the affected files.
Review what the existing offline readiness report already covers before
reusing it; a ready snapshot is not proof that every claim is correct.

Calculate the tier from current verification events only: **unverified**,
**machine-confirmed**, or **human-reviewed**. Events before `generated.at`
remain visible as history but do not count. Use the same calculation in
the Clerk and Viewer. Show who checked the concept and when, alongside
recorded source references; don't imply that `verified` identifies exactly
which claims were checked.
Keep unverified concepts visible by default. Runtime attestation for
computations is separate and out of scope for this prototype.

**Writer gap to close before showing trust badges in the editable Viewer:**
Today's ordinary Update preserves `generated` and `verified`. Plan an explicit,
guarded way to record a meaningful change in `generated` without erasing
prior verification, and a separate revision-checked verification action.
Trivial edits such as formatting shouldn't advance `generated.at`. Decide how
the Clerk proposes that distinction and how the user confirms it. Don't
work around the existing guard with direct file writes.

**Acceptance case:** Open a fixture concept with a source-linked claim and a
current human review. Change the claim; the prior review goes into history,
and the tier falls to unverified if no current event remains. Check the new
claim against its source and record explicit human verification; the tier
returns to human-reviewed. Also test a machine-only check, a formatting-only
edit, a revision that changes while review is open, and an independently stale
concept. Use fixed times to test equal timestamps, date-only values, and the
single-event and list forms of `verified`.

## 3. Make the Viewer worth using

Develop the visual language from the first card, then add breadth once the
edit loop works. Keep the same selected concept as the user moves between
browsing, reading, and inspecting connections.
Give the title and excerpt visual priority. Use consistent type labels and
accent colors across cards and graph nodes, with text as well as color.
Make the reading view quieter than the browse view, and let cards work even
when a concept has no image or optional metadata.

| Surface | What the first useful version shows |
| --- | --- |
| **Cards** | Clear title and type, a short description or excerpt, and a few meaningful fields. Let the layout breathe on desktop and reflow to one column on narrow screens. |
| **Facets** | Type, collection, and one meaningful type-specific field such as `video_status`. Show counts, active filters, a clear-all action, and a useful empty state. Don't conflate viewing state with lifecycle `status`. |
| **Concept detail** | Readable Markdown with source references and incoming and outgoing connections. Once the trust workflow is safe, lead with the evidence here before adding dense card badges or a trust facet. Show unavailable targets without treating them as invalid records. |
| **Graph** | Start with a concept's immediate neighborhood. Label nodes and show direction. Pair it with a keyboard-accessible link list; avoid a whole-bundle graph as the starting view. |

Follow the [OKF v0.3 path and graph rules](../OKF_SPEC/SPEC.md#6-links-and-paths):
resolve both bundle-root and document-relative links, and draw directed edges
from standard Markdown links and recognized path fields that actually resolve
to concepts. Don't infer relationship types from link text, silently read
outside the bundle, or make broken links prevent browsing. Use synthetic
cards for visual review; confirm that editing a link refreshes both endpoints'
connection lists and the graph.

**Done when:** A person can narrow the card grid, understand why a result
matches, open it, and follow a connection without losing their place. Review
desktop and narrow layouts, keyboard navigation, and empty and broken-link
states. Capture screenshots of representative states for design review.

## 4. Revisit the Builder after real use

Take note of where creating the fixture or adding a new concept type was
unclear. If that friction repeats, prototype a short conversation that gathers
the user's goals, proposes types and a folder layout, and produces a reviewed
plan and starter files on disposable data. Test whether someone else can
create a different useful bundle without hand-editing configuration. Until
then, don't introduce a general setup wizard or a second write path.

## Boundaries and open decisions

* **Next decision:** Choose the fixture's subject and sketch the card grid,
  concept detail, and review screen around one realistic edit. Use the result to
  decide which fields earn space on the cards and in the facets.
* **Decide after the first loop:** Whether the Clerk is primarily a chat
  surface or an edit panel with conversational help, and whether plain-text
  search is enough. Leave framework and deployment choices open for now.
* **Separate operations:** Personal backup and restore coverage still merits
  its own plan; the November 25 format audit was not a restore backup. No
  live integration follows from prototype success. Any later operation needs
  approval for the exact target, action, verification, and rollback. Don't
  change writer authority, bindings, sync, or publisher holds as part of
  this roadmap.
