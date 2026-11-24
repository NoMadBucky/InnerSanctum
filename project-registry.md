# Project registry

This is InnerSanctum's read-only routing registry. Accept an alias or the exact
host and path in the URL column, with or without `https://` or the final slash.
Match the whole path: `matterkeep.com` means `landing`, not every MatterKeep
workspace. `cove` and `gallery` are separate applications.

Checkout paths are relative to the InnerSanctum repository root and describe
the local layout reviewed on 2026-11-24. A source branch is not a deployed
revision. Use the owner repository's root and component `AGENTS.md` where
present before separately authorized source work.

## Routing

| Alias | URL | Checkout · component · source branch | Operating guidance |
| --- | --- | --- | --- |
| `landing` | <https://matterkeep.com/> | `../MatterKeep` · `Guide/public-site/` · `main` | `Guide/public-site/DEPLOYMENT.md`, Current state |
| `barry` | <https://matterkeep.com/barry/> | `../MatterKeep` · `Personal/` · `main` | [InnerSanctum cutover](create-cutover.md) governs live writer authority; `Personal/DEPLOYMENT.md` documents the former application |
| `litigation` | <https://matterkeep.com/litigation/> | `../MatterKeep-Litigation` · `Demo/` and `website/` · `feature/litigation-workspace` | `Demo/docker/README.md`, Current observed owner-review state; `Demo/progress.md` |
| `bho` | <https://matterkeep.com/bho/> | `../BHO` · `website/` · `main` | `website/README.md` and root `AGENTS.md` for the live desk; [InnerSanctum cutover](create-cutover.md) for Personal publisher holds |
| `cove` | <https://matterkeep.com/bloniencove/> | `../MatterKeepCove` · repository root · `main` | `docs/deployment.md`; confirm current reader binding before relying on it |
| `design` | <https://design.matterkeep.com/> | `../MatterKeep` · `Guide/design-site/` · `main` | `Guide/design-site/README.md` for component operations and release state |
| `gallery` | <https://bloniencove.com/> | `../BlonienCove` · repository root · `main` | `README.md` and `main.py` identify the gallery; no current operator runbook found |

## Last recorded status

These are dated observations or documentation records, not current health
checks. External evidence paths below are locators, not instructions to open
those files or contact the services during a hub lookup.

| Alias | Evidence date | Recorded status and source |
| --- | --- | --- |
| `landing` | 2026-11-06 | `Guide/public-site/DEPLOYMENT.md` records the completed launcher path cutover for `system/com.matterkeep.public`; HTTPS apex and chooser returned 200. |
| `barry` | 2026-11-24 | The [InnerSanctum cutover](create-cutover.md) records Personal stopped and restart-disabled. InnerSanctum is the only writer of the Personal `OKF/`; use its guarded CLI for authorized filing, never the retired store or publisher. |
| `litigation` | 2026-11-03 | `Demo/progress.md` records a healthy demo container, anonymous HTTPS sign-in, and closed enrollment. Signed-in acceptance was not established by that check. A second linked worktree, `../MatterKeep-Litigation-open-enrollment` (`feature/demo-open-enrollment`), exists; confirm the exact worktree and reviewed revision before planning a release. |
| `bho` | 2026-11-24 | The [InnerSanctum cutover](create-cutover.md) records the live dashboard restored on its existing job, sign-in responding, and Personal publishers and delegated Notes editing still held. Use an isolated worktree for source changes that could trigger the live reloader. |
| `cove` | 2026-10-23 | `../BHO/website/ACCEPTANCE.md` records an operator-reported tunnel mapping, not current service or reader acceptance. `docs/deployment.md` describes the independent read-only workspace. |
| `design` | 2026-11-09 | `Guide/design-site/README.md` and `Guide/design-site/docs/signing-c3b-2026-11-09.md` record the running invite-only signing candidate and scoped wallet acceptance. This does not establish deployment of newer editor source. |
| `gallery` | 2026-10-23 | `../BHO/website/ACCEPTANCE.md` records an operator-reported tunnel route and tailnet reachability on port 4304. This is not a fresh HTTPS check or authenticated gallery acceptance; supervisor and rollback procedure are unconfirmed. |

## Operating boundary

The hub reports and plans; it does not fetch live URLs, open private stores,
edit sibling checkouts, or run operator commands. A later live operation needs
separate approval for the exact target and action, with verification and
rollback agreed in advance. Keep authentication and write authority with the
owning application. The registry does not change the Personal cutover or grant
access to any service.
