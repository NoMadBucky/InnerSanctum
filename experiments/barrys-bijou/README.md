# Barry’s Bijou

**Status: proposed experiment, 2026-11-25.** The first prototype ranks watched
films and proves a local-first round trip into a disposable OKF bundle.
No app has been built and no live access or writes are approved.

Barry’s Bijou is a SwiftUI **movie journal for iPhone and Mac**, using the
Personal OKF bundle as its film library. It opens to **Watched**, most recently
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

* Read Personal `Video` concepts from `Resources/videos/`. Show the poster,
  title, and release year where available. Show the recorded metadata,
  notes, and source references in film detail. Use a placeholder when artwork
  is missing or offline. Check how Personal references posters before
  choosing a loading and caching policy; don’t assume the images are local.
* Include only `video_type: Movie` concepts with a recorded watched date or
  `video_status: watched`. Films marked watched without a date sort last,
  rather than getting a guessed date. Keep `video_status` separate from OKF
  lifecycle `status`.
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
best to worst. The prototype doesn’t use public ratings.

1. From film detail, select **Rank**. Open near the middle of the ranked
   posters. For reranking, leave the selected film out of the comparison
   list without changing its saved placement until confirmation.
2. Scroll through the posters in **personal ranking order**. Select a gap
   between adjacent films, or before the first or after the last. Preview the
   two comparisons: **Worse than [film above]** and **Better than [film
   below]**. At either end, show just the applicable comparison. If the list
   is empty, invite Barry to make this the first ranked film.
3. **Confirm placement** to save the order on the device immediately, even
   offline. Browsing or canceling changes nothing. If the list changed and
   the chosen neighbors no longer bound the same gap, reopen the placement
   for review rather than guessing.

## Local-first storage and sync

Follow [Ink & Switch’s local-first principles](https://www.inkandswitch.com/essay/local-first/):
the phone’s copy is usable without the Mac, and confirmed local edits are
durable even before they reach the bundle. Keep an offline film catalog,
the current local order, the last acknowledged bundle revision, and pending
ranking changes in private device storage. Commit a placement and its
pending sync state together. Provide a readable Markdown export as a
fallback, not a required step for routine use.

* **Bundle representation:** one dedicated OKF concept holds a numbered list
  of links to the ranked movies. It is the source of truth for the order and
  membership recorded in the bundle. Film frontmatter has a Personal
  `ranked` boolean as a derived convenience: set `true` on addition and
  `false` on removal if supported. Interpret an absent flag as false for
  unranked films; don’t backfill the whole library. A rerank doesn’t change
  the flag. On the device, derive the badge from the local list so it responds
  immediately. If bundle flags and the list disagree, use the list and flag
  the mismatch for reconciliation.
* **Sync attempts:** try on app open or return to foreground, periodically
  while active with changes pending, and via **Sync now**. Background attempts
  on iPhone are best-effort, not a guaranteed schedule. Show **Saved on this
  device**, **Synced to OKF**, or **Needs review**; offline use never waits
  for an acknowledgment.
* **Writer boundary:** sync ranking requests, not folders. A narrow,
  authenticated Mac-side adapter is proposed; only InnerSanctum would
  publish to the live bundle. Validate the movie references and the expected
  ranking revision. The guarded write needs to coordinate the ranking
  concept, changed membership flags, and audit entry as one recoverable
  operation. Don’t assume that a multi-file write is atomically visible to
  readers. Acknowledge only after read-back and retain a receipt for retries
  of the same request.
* **Conflicts:** if the bundle ranking changed since the last acknowledged
  revision, keep the local order and pending work. Show the two versions for
  review; don’t overwrite one with the other or silently reorder the films.
  Don’t retry an uncertain write with a new request ID. Start with one phone
  and explicit conflict review, not automatic multi-device merging.

The sync transport, canonical ranking path and schema, and live activation
are separate decisions. Rehearsing the sync workflow does not authorize
inbound folder sync or changing writer authority.

## Prototype and verification

1. Build Watched, film detail, and the ranking carousel on a disposable
   Personal-shaped bundle. Test sorting, empty rankings, top/middle/bottom
   placement, cancellation, and reranking.
2. Rank films offline, relaunch, then sync to the disposable bundle. Read
   back the exact order and membership flags. Test a lost acknowledgment
   without a duplicate write, a newer bundle ranking without lost local work,
   and an unavailable Mac without blocked ranking.
3. Use a separately approved private Personal snapshot to verify that the
   real watched films, posters, and details are usable. Keep mutation tests
   on disposable data; enabling automatic sync to live Personal needs
   separate operational approval.

Full Xcode is needed for the iPhone build. The first phone test can use free
Personal Team signing. For any eventual live integration,
[InnerSanctum remains the sole OKF writer](../../create-cutover.md).
