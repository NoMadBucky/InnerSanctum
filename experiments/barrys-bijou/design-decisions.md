# Barry’s Bijou design decisions

**Design baseline · 2026-11-25.** The [experiment brief](README.md) sets the
scope. Barry settled three product choices:

* **Rank once, rerank in either direction, no removal.** Moving a film after
  further reflection changes only its place, never its watch history.
* **Rank on both devices.** One person, one iPhone and one Mac, with the
  same controls and the ability to save a placement locally on either.
* **Sync at home.** A placement made at the theater is saved immediately.
  It reaches OKF on the next sync when the Mac is reachable at home.

The rest is the working design for the prototype. Change it if rehearsal
or review of the actual library gives us a reason.

## What a placement means

* One film has one slot, even after a rewatch. Number one is best; there are
  no ties. Watched stays in viewing-date order. Show the current position in
  film detail. Use the latest recorded viewing if several exist, put undated
  watched films last, and break ties by title, then by bundle path.
* Open **Rerank** at the film’s **current gap**. Barry can see its neighbors
  before deciding how far to move it. Start **Rank** near the middle for a
  film without a position. Selecting a gap is a preview. Canceling or
  confirming the original gap produces no change or sync request.
* Identify a film by bundle-relative path and check its Personal ID when
  present. If a ranked reference disappears or its ID changes, keep its
  labeled slot and show **Needs review**. A missing poster gets a placeholder;
  a missing film never quietly promotes every film below it.

## Where the data lives

* **On each device:** use one shared SwiftUI ranking flow and placement model.
  Use a private SQLite database for the watched catalog, last acknowledged
  order and revision, current local order, and queue of confirmed placements.
  Save the new order and its queue entry in one transaction. Relaunching
  offline restores both. Keep replaceable poster thumbnails in a separate
  cache. Use artwork referenced by the catalog, with a placeholder on a
  cache miss offline; don’t look films up by title to fill missing artwork.
  A readable Markdown export includes confirmed local placements.
* **In OKF:** propose one `Film Ranking` concept in `Documents/rankings/`.
  Declare the type in that directory’s `index.md` on the disposable fixture.
  Use the [writer’s normal Create convention](../../docs/operator-guide.md#concepts):
  it assigns the Personal ID and seven-digit filename. Set up one empty
  ranking and bind the adapter to that ID and expected path. A missing bound
  record is an error, not a fresh empty list.
* **On the page:** use `type: Film Ranking`, a display `title`, and a
  `## Ranking` section with one numbered Markdown link per film, best first.
  Write bundle-root links such as `/Resources/videos/1234567.md`. The order
  of the links is authoritative. On first placement set the movie’s `ranked`
  flag to `true`; a move only changes the ranking and its audit entry. No
  position numbers need to be rewritten across movie files.

## How a confirmed move reaches the bundle

1. A Mac-side adapter supplies the watched catalog, poster references or
   thumbnails, and the ranking with its revision. The Mac app connects
   locally; the iPhone connects over home-network HTTPS while the Mac is
   awake and the adapter is running. Pair the phone once using a code shown
   by the Mac that identifies its TLS key and authorizes enrollment. Keep a
   revocable device credential in Keychain. After the first catalog load,
   browsing and ranking on either device work without a connection.
2. Send one **place this film in this gap** request per changed placement,
   oldest first. It carries a stable request ID, expected ranking revision,
   film reference, and the neighbors above and below (either can be absent at
   an end). Tie the first move to the revision Barry worked from; fetching a
   newer list cannot silently change that starting point. Subsequent moves
   build on the preceding receipt. Freeze each payload before sending. The
   writer validates references and the gap with the selected film excluded.
3. Use the SHA-256 revision of the ranking document, as for ordinary concept
   reads. Add a **guarded placement operation** to InnerSanctum: under its
   writer lock, plan the order, first-placement flag, and one audit entry
   together. Use its [journal and receipts](../../docs/operator-guide.md#preview-and-recovery)
   for recovery and read-back. With two ordinary CLI updates, the flag could
   be saved even if the list update never starts, or vice versa. Serve
   snapshots only from a consistent, completed publication.
4. If the acknowledgment is lost, reconcile or retry the identical request.
   A receipt proves *that move* completed; refresh to see the current order.
   On a stale revision, retain the local order and queue. Show both orders,
   highlight the film Barry moved, and let him choose its gap in the latest
   order, accept its current bundle placement if it has one, or leave the
   decision pending. Keep later queued moves and recheck their gaps in order.
   A reviewed change gets a new request only after the old request’s outcome
   is known.

For example, Barry moves a film from second to fifth on the offline phone.
Meanwhile he adds another film on the Mac. Review asks **“Where should this
film go now?”** The Mac addition stays in the list, and the phone remembers
the intended move. Barry never has to discard one device’s entire ranking.

## What needs evidence

* Rehearse on an external, disposable Personal-shaped bundle. Verify the
  offline move across relaunch, a lost acknowledgment with one audit entry,
  and the two-device example above. Compare movie files before and after a
  rerank: none should change.
* An approved read-only Personal snapshot can establish actual poster and
  watched-date formats, support for the `ranked` field, and whether the
  proposed ranking route fits. These are facts to verify, not reasons to
  leave the prototype’s data model open. Live setup is separately authorized.
* Later audio/video reactions belong to a film and optionally a viewing,
  independent of rank. Give each take its own identity, private original,
  and retryable transcript state. For eventual filing, retain the original
  until both an external attachment and its OKF reference are verified.
  The attachment owner must establish the destination and reference format.
* Before the first device build, confirm the target iPhone and Mac OS
  versions and full Xcode availability. These set deployment targets and
  signing details; they don’t change the placement or sync model.
