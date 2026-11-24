# InnerSanctum agent guide

## Keep the stores separate

* This is a repository for a personal OKF bundle. The root [index.md](index.md) describes the project at OKF v0.3; it does not declare the version of the Personal bundle.
* `OKF/` is the live Personal v0.2 bundle. Its sibling `SourceFiles/` holds native attachments and the source catalog **outside** that bundle. Both are Git-ignored and absent from fresh clones. Never force-add or publish their contents, or save synthetic data to the Personal store.
* InnerSanctum is the sole writer of the live `OKF/` bundle after the [Create cutover](create-cutover.md). File real concepts through its guarded CLI, not by editing live files directly. Do not restart the former Personal writer or its held publishers, change a binding, file into the old SynologyDrive store, or allow inbound sync without separate operational approval. Any v0.3 conversion is separate.
* Test the CLI on external, disposable bundles, never on live data. Do not remove a writer marker to make a bundle eligible. `SourceFiles/` was not handed over for writing.

## Edit and verify

* Use the [vendored OKF spec](OKF_SPEC/SPEC.md) for v0.3 rules. Preserve the root `index.md` frontmatter when updating its listing. Use standard Markdown links, not Obsidian wikilinks; in OKF a leading `/` means the current bundle root, not the filesystem or necessarily the Git root.
* Run `uv run --locked pytest` for tooling changes. From the repo root run `markdownlint-cli2 AGENTS.md README.md index.md log.md relocation-plan.md OKF_SPEC/index.md`, or pass just the changed Markdown paths. Avoid a recursive glob: it can sweep in private migration copies and the upstream spec’s existing lint violations. Keep `OKF_SPEC/SPEC.md` and its license unmodified.
* Suggest a commit message for repository changes; do not commit.
