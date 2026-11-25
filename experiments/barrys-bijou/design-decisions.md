# Barry’s Bijou design decisions

**Design baseline · 2026-11-25.** The [experiment brief](README.md) sets the
scope. Barry settled three product choices:

* **Rank once, rerank in either direction, no removal.** Moving a film after
  further reflection changes only its place, never its watch history.
* **Rank on both devices.** One person, one iPhone and one Mac, with the
  same controls and the ability to save a placement locally on either.
* **Sync at home.** A placement made at the theater is saved immediately.
  It reaches OKF on the next sync when the Mac is reachable at home.

The catalog review below establishes the inputs for the prototype.

## Personal catalog review

On 2026-11-25, a read-only inspection covered the Personal v0.3 Video
collection and 116 bundle indexes. The scoped file inventory and bytes
matched a second read. Poster references were inspected without fetching
images.

* **Watched:** Of 399 `Video` concepts, 398 are `video_type: Movie`.
  Exactly 210 movies meet the Watched rule. All 210 have both
  `video_status: watched` and one scalar `date_watched` in `YYYY-MM-DD`
  form. Only 35 are marked `in_library: true`. Personal declares no
  structured rewatch history. Several films share a viewing date.
* **Artwork:** All 210 watched films have an HTTPS `poster` URL. Of those,
  207 point to TMDb image hosts and three point elsewhere. Many point to
  original-size images. Only 30 watched films embed a Markdown image;
  reading the frontmatter covers the whole list.
* **Film detail and identity:** `release_date` is a calendar date on 206
  watched films, a timestamp with an offset on one, and absent on three.
  Display its recorded year or omit the year. All 210 have a Markdown body
  and a unique Personal ID matching their seven-digit filename. Of those,
  198 have `sources` entries; the other 12 have a `url` to show as a link.
* **Ranking:** No Video record uses `ranked`; the `Video` declaration neither
  declares nor forbids it. `Documents/index.md` exists, but
  `Documents/rankings/` and a `Film Ranking` declaration do not. In memory,
  all 210 watched records passed schema validation with a proposed optional
  `ranked: {type: bool}`, both absent and set to `true`; the string `"true"`
  was rejected. The proposed ranking type and ID-based route also resolved
  against a synthetic index in memory. These are schema checks, not a test
  of publishing a ranking.

## What a placement means

* One film has one slot, even after a rewatch. Number one is best; there are
  no ties. Watched stays in viewing-date order. Show the current position in
  film detail. Use `date_watched` as a calendar day without timezone
  conversion. Put undated watched films last and break ties by title, then
  by bundle path. A rewatch history can supply the latest day if added later.
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
  offline restores both. A readable Markdown export includes confirmed
  local placements.
* **Artwork:** the Mac fetches the recorded `poster` URL and downsamples the
  result. Cache thumbnails separately by source URL. Transfer them for the
  whole Watched list on home sync, after the text catalog is usable. This
  lets Barry see a poster away from home even if he never opened that film.
  Show a placeholder until a thumbnail is available.
* **In OKF:** use one `Film Ranking` concept in `Documents/rankings/`. Set
  up that directory and its `index.md` on the disposable v0.3 fixture, link
  it from `Documents/index.md`, and give the fixture an explicit creation
  route. Declare the new type there and the optional boolean in the existing
  `Resources/videos/index.md` Video schema.
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

1. A Mac-side adapter supplies the watched catalog, thumbnails, and the
   ranking with its revision. The Mac app connects
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

## Prototype verification

* Rehearse on an external, disposable Personal-shaped bundle. Verify the
  offline move across relaunch, a lost acknowledgment with one audit entry,
  and the two-device example above. Compare movie files before and after a
  rerank: none should change.
* Include synthetic cases for two films watched the same day, a watched
  non-movie, an undated watched movie, a missing release year, a release
  timestamp, and an unavailable poster. Verify a cached poster displays
  offline on the phone. Use a separately approved snapshot for eventual
  app acceptance on real films; live setup remains a separate decision.
* Later audio/video reactions belong to a film and optionally a viewing,
  independent of rank. Give each take its own identity, private original,
  and retryable transcript state. For eventual filing, retain the original
  until both an external attachment and its OKF reference are verified.
  The attachment owner must establish the destination and reference format.
* The test iPhone runs iOS 27.x and the development Mac runs macOS 27.2.1.
  Target iOS 27.0 and macOS 27.0 for the first builds. Full Xcode 27.2 was
  verified at `/Applications/Xcode.app`; the default developer directory
  points to Command Line Tools. Set `DEVELOPER_DIR` to
  `/Applications/Xcode.app/Contents/Developer` for builds. Device signing
  and installation still need a first build.
