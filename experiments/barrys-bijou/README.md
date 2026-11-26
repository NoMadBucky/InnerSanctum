# Barry’s Bijou

**Status: Personal home sync activated, 2026-11-25.** The adopted Personal
OKF library now holds the ordered ranking imported from the phone. Pair
with the separate [Personal adapter](run.md#use-personal-as-the-main-library)
to open the real Watched catalog and save subsequent placements. Open the
[Xcode project](Bijou.xcodeproj/) to try six fictional films on iPhone or
Mac. Browse Watched, rank offline, quit, and revisit the same order.
The [build and pairing guide](run.md) walks through a two-device trial
against a disposable OKF bundle.

Barry’s Bijou is a SwiftUI **movie journal for iPhone and Mac**, using the
Personal OKF bundle as its film library. Choose **Enter theater** on the opening
marquee to see **Watched**, most recently
watched first. Pick a film to see its details or give it a place in your
personal rankings. The BHO bundle is not an input, and the app does not need
Clerk or the Daily dashboard.

## Art Deco theater

Think stepped frames, geometric lettering, restrained brass, and generous
space for the posters. Use an ivory-and-brass **Working Hours** palette and
a midnight-and-brass **After Hours** palette. Let the ranking carousel feel
like a row of theater lobby posters. Keep small labels readable and use text,
not just color, to identify the selected slot and its neighbors.

## Watched list and film detail

* Read Personal `Video` concepts from `Resources/videos/`. Show the title
  and the year from `release_date` when present. Film detail shows the
  Markdown body, including notes, and the recorded source references.
* Use the `poster` frontmatter URL. The Mac caches thumbnails for the
  Watched list and sends them to the phone during home sync. A missing or
  unavailable image gets a placeholder without delaying browsing or ranking.
* Include only `video_type: Movie` concepts with a `date_watched` or
  `video_status: watched`. Sort by the recorded calendar day, newest first;
  watched films without a date go last. Neither `in_library` nor OKF
  lifecycle `status` determines whether a movie has been watched.
* Keep ranked films in the same Watched list and label them **Ranked**.
  There is no standalone Ranked view in the first prototype; the ranked
  posters appear when choosing a placement. Use the concept’s bundle-relative
  path and check its Personal ID when available; don’t match on title.
* Watchlist and watched-date editing are later features. Watch state and rank
  are independent: ranking a film does not change its watched date.

## Record a reaction (later)

From film detail, choose **Audio** or **Video**, then record, preview, and keep
or discard the take. Display a timer and stop recording at **two minutes**.
Use AVFoundation and request microphone or camera permission only when
needed. Allow multiple dated reactions per film; when a viewing date is
known, associate the reaction with that viewing without overwriting earlier
takes or dates.

Keeping a take saves the original recording, links it to the film, and starts
transcription. Save the resulting text alongside the reaction so it can be
read without playing the clip. Prefer on-device transcription; don’t send
recordings to an external service without a separate, explicit choice. If
transcription is unavailable or fails, keep the clip and show that the text
is pending or failed. Retrying transcription should not require a new
recording or duplicate the reaction. Treat generated text as a draft
transcript, not a verified quotation.

Stage this feature’s first recordings in private app storage. For real filing,
the media belongs outside the bundle and the OKF record holds the reference.
The attachment destination, reference format, and recovery behavior still
need a design and approval. This experiment does not grant write access
to `SourceFiles/`.

## Rank a film by choosing a gap

The ranking is an ordered list of **only the films Barry has ranked**, from
best to worst. A film joins on its first confirmed placement. After that,
Barry can move it up or down; it keeps exactly one place. There is no
**Remove from ranking** action. The prototype doesn’t use public ratings.

1. On iPhone or Mac, select **Rank** from film detail for a first placement
   or **Rerank** to revisit a film. A first placement opens near the middle
   of the posters. Reranking opens at the film’s current gap, with the film
   left out of the comparison list; its saved placement stays in effect until
   confirmation.
2. Scroll through the posters in **personal ranking order**. Select a gap
   between adjacent films, or before the first or after the last. Preview the
   two comparisons: **Worse than [film above]** and **Better than [film
   below]**. At either end, show just the applicable comparison. If the list
   is empty, invite Barry to make this the first ranked film. If reranking
   the only ranked film, show that it is already first.
3. **Confirm placement** to save the order on the device immediately, even
   offline. Browsing, canceling, or confirming the original gap changes
   nothing. If the list changed and the chosen neighbors no longer bound the
   same gap, reopen the placement for review rather than guessing.

## Local-first storage and sync

Follow [Ink & Switch’s local-first principles](https://www.inkandswitch.com/essay/local-first/):
the phone’s copy is usable without the Mac, and confirmed local edits are
durable even before they reach the bundle. Keep an offline film catalog,
the current local order, the last acknowledged bundle revision, and pending
ranking changes in private device storage. Commit a placement and its
pending sync state together. Provide a readable Markdown export as a
fallback, not a required step for routine use.

* **Bundle representation:** one new `Film Ranking` concept holds a numbered list
  of links to the ranked movies. It is the source of truth for the order and
  membership recorded in the bundle. The disposable fixture should match
  Personal’s `Video` schema: `ranked` is an optional boolean. Set it to
  `true` on first placement as a convenience for other readers.
  Interpret an absent flag as false for unranked films; don’t backfill the
  whole library. A rerank doesn’t change the flag or the watched date. On the
  device, derive the badge from the local list so it responds immediately.
  If bundle flags and the list disagree, use the list and flag the mismatch
  for reconciliation.
* **Sync attempts:** the iPhone syncs when it can reach the Mac on the home
  network. A placement made at the theater stays saved on the phone until
  then. Try on app open or return to foreground, periodically while active
  with changes pending, and via **Sync now**. Background attempts on iPhone
  are best-effort. Show **Saved on this device**, **Synced to OKF**, or
  **Needs review**.
* **Writer boundary:** the Mac adapter accepts authenticated placement
  requests for its selected Personal or practice library. InnerSanctum validates the film,
  neighbors and revision, then journals the ranking, first-placement flag
  and one audit entry together. Snapshots use the writer lock; a pending
  publication blocks new snapshots. The receipt follows canonical read-back.
* **Conflicts:** if the bundle ranking changed since the last acknowledged
  revision, keep the local order and pending work. Show the two versions for
  review; don’t overwrite one with the other or silently reorder the films.
  Don’t retry an uncertain write with a new request ID. Start with one iPhone
  and one Mac, both able to rank. Review the affected film’s gap against the
  latest order, keeping other films and pending moves intact.

The [design decisions](design-decisions.md) record the device and home-sync
choices and the working design for storage, pairing, and conflict review.
The Personal and practice adapters use separate device enrollments.

## Prototype and verification

1. Build Watched, film detail, and the ranking carousel on a disposable
   Personal-shaped bundle. Test sorting, empty rankings, top/middle/bottom
   placement, cancellation, and reranking. Move a film from near the top to
   the bottom: it should appear once, with the same membership and watch date.
2. Rank films offline, relaunch, then sync to the disposable bundle. Read
   back the exact order and membership flags. Test a lost acknowledgment
   without a duplicate write, a newer bundle ranking without lost local work,
   and an unavailable Mac without blocked ranking.
3. Once the app exists, check film detail and offline poster rendering on
   a separately approved private Personal snapshot. The catalog review
   verified references, not image availability. Keep mutation tests on
   disposable data; use the activated Personal adapter for actual rankings.

The first device targets are iOS 27 and macOS 27. The first phone test can
use free Personal Team signing. For live integration,
[InnerSanctum remains the sole OKF writer](../../create-cutover.md).
