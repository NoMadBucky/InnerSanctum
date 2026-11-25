# InnerSanctum

InnerSanctum is a local-first proof of concept for creating, exploring, and
developing a personal [Open Knowledge Format (OKF) v0.3](OKF_SPEC/index.md)
bundle. The goal is a collection a person can browse and understand, and an
assistant can help maintain, without moving the knowledge out of Markdown.

| Component | Role | Where it stands |
| --- | --- | --- |
| **OKF Builder** | An LLM-led conversation that works out what the user wants to collect, what belongs in scope, and how to structure the bundle. | Deferred; use a small hand-authored fixture first. |
| **OKF Clerk** | Finds and edits concepts, explains validation findings, and guides review against sources. | Guarded CLI CRUD and schema checks exist. The Clerk workflow and trust features are proposed. |
| **OKF Viewer** | A web interface for exploring the bundle through cards, facets, and connection graphs, with trust and source details where available. | Proposed here; existing Personal and BHO reader evidence is separate. |

**First milestone:** On a disposable bundle, find a concept in a card view,
review and apply an edit through the Clerk, then see the canonical change in
the Viewer. The [roadmap](docs/roadmap.md) lays out the full CRUD loop and
the visual prototype.

## Start here

* [Project index](index.md): Map of the repository and its historical records.
* [Operator guide](docs/operator-guide.md): Existing concept and journal
  commands, previews, receipts, recovery, and migration references.
* [Agent guide](AGENTS.md): Repository rules and verification commands.

## Private data and operations

The live Personal bundle is `OKF/`; its native attachments and source catalog
live beside it in `SourceFiles/`, outside the bundle. Both are Git-ignored
and absent from fresh clones. InnerSanctum is the sole Personal writer; the
former SynologyDrive store remains inactive and inbound sync stays excluded.
Use disposable bundles outside the checkout for development. See the
[writer cutover record](create-cutover.md) for authority and handover evidence.

### Personal v0.3 readiness

The November 25, 2026 offline snapshot audit found that Personal already
declared v0.3 and reported zero readiness findings. That is format evidence,
not a restore backup or live reader acceptance. See the
[full audit and readiness command](docs/operator-guide.md#personal-v03-readiness).

## Project hub

The [project registry](project-registry.md) routes work for seven sites. In
OpenCode v2, this checkout defaults to the read-only `project-hub` agent:

```text
/project-status
/project-status https://matterkeep.com/
/project-plan design review a navigation change
```

Both commands select `project-hub` in the current session. Status is dated
evidence, not a health check. For authorized repository changes, select
`project-build`; it grants tool permissions, not permission to touch private
stores or operate live services. For another site's source work, use its owning
checkout and instructions. The hub is not the OKF Builder, Clerk, or Viewer.
