# InnerSanctum agent guide

## Keep the stores separate

* This is a repository for a personal OKF bundle. The root [index.md](index.md) describes the project at OKF v0.3; it does not declare the version of the Personal bundle.
* `OKF/` is a local migration copy of the Personal v0.2 bundle. Its sibling `SourceFiles/` holds native attachments and the source catalog **outside** that bundle. Both are Git-ignored and absent from fresh clones. Never force-add or publish their contents, or save synthetic data to the Personal store.
* MatterKeep still files to the registered SynologyDrive store. Do not file into the migration copies or change a binding without explicit operational approval. Follow the [relocation plan](relocation-plan.md) for the stopped checkpoint, checkout opt-in, and binding approval. Keep the live bundle at v0.2 through the move.

## Edit and verify

* Use the [vendored OKF spec](OKF_SPEC/SPEC.md) for v0.3 rules. Preserve the root `index.md` frontmatter when updating its listing. Use standard Markdown links, not Obsidian wikilinks; in OKF a leading `/` means the current bundle root, not the filesystem or necessarily the Git root.
* There is no application build or test suite. From the repo root run `markdownlint-cli2 AGENTS.md README.md index.md log.md relocation-plan.md OKF_SPEC/index.md`, or pass just the changed Markdown paths. Avoid a recursive glob: it can sweep in private migration copies and the upstream spec’s existing lint violations. Keep `OKF_SPEC/SPEC.md` and its license unmodified.
* Suggest a commit message for repository changes; do not commit.
