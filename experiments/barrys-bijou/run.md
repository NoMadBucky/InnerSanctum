# Build and try Bijou

## Rehearse reaction filing in a disposable library

When creating a **new** external practice bundle with `adapter/fixture.py`,
pass `--reactions`. This also creates a private sibling source store named
`BijouSources-<fixture library ID>`. Both belong to that disposable fixture.
Pair with its practice adapter as usual. Keep a WAV take on a fixture film
and select **File in practice library**. The Mac archives the original bytes,
reads back the SHA-256 source catalog entry, and files a `Film Reaction`
concept in `Documents/reactions/`. Its `film_id` and Markdown link identify
the movie; `source_key` identifies the recording in the sibling catalog.
The file name in the media store is derived from the checksum.

If filing is interrupted, retain the device copy and retry the same take.
A pending OKF publication requires the existing fixture recovery command
before retry. Removing a filed take from the phone leaves the archive intact.
Legacy AAC imports, adoption of the live source catalog, and installation of
the reaction schema in Personal are outside this rehearsal.

## Open a library movie in Plex on iPhone

1. On the Mac, open Plex Web. Select a movie **from your server’s Movies
   library**, then choose **⋯ → Get Info → View XML**. Copy the address of
   the XML page. It can include a Plex access token; keep it local.
2. In Terminal, from the InnerSanctum checkout, run:

   ```sh
   uv run --locked python experiments/barrys-bijou/adapter/plex_export.py
   ```

3. Paste the address at the hidden prompt and press Return. The helper reads
   all movie sections visible to you on that server and saves exact,
   unambiguous TMDb-to-Plex matches in the Personal adapter’s Application
   Support folder. You do not need to download or send an XML file.
4. With the updated Personal adapter running and the new Bijou build on your
   phone, choose **Home Sync → Sync now**. Open **Library**, select a matched
   film, and tap **Open movie in Plex**. Unmatched films show **Open Plex**.
   Rerun the helper after adding movies or rebuilding your Plex library.

## First screening

### Use Personal as the main library

The Personal adapter is distinct from practice. On home Wi-Fi, open
**Home Sync**, select **Bijou Personal on …** (or enter the Mac’s address
with port **8766**), and pair with a fresh code from the Mac’s private
**New Pairing Code.command**. Each device needs its own code. Pairing opens
Watched from Personal and makes it the startup library. Older builds call
it **Paired home library**. Confirmed edits are queued offline and published
to Personal when home; **Synced to OKF** means the writer read them back.
Screening copies remain independent. Sync pending practice edits before
switching a device to a different paired library.

The separately launched job is `org.innersanctum.bijou.personal`; its
private pairing database, certificate and thumbnail cache are outside OKF.
**Stop Personal Sync.command** stops access without reverting records. Use
**Start Personal Sync.command** on the Mac after logging in again or
after stopping the job. Keep the Mac awake while syncing.

### Try the sample

Open [Bijou.xcodeproj](Bijou.xcodeproj/) in Xcode 27.2. Choose scheme
**Bijou**, select **My Mac**, and press **Run**. Choose **Enter theater** to open **Watched**
with six fictional movies. Choose one, tap **Rank**, then **Confirm
placement**. Rank a second film and **Rerank** the first. Quit and reopen:
the positions persist, and the watched dates stay the same.

For iPhone, select your paired phone in the same scheme. In the **Bijou**
target’s **Signing & Capabilities**, select your **Personal Team**; press
**Run**. The app needs iOS 27.0 or newer. The built-in sample works without
pairing with a home adapter. Sample rankings are private to each device and
remain accessible after connecting to a separate fixture.

To build from Terminal, start at the InnerSanctum repository root:

```sh
export DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer
BIJOU=experiments/barrys-bijou
xcodebuild -project "$BIJOU/Bijou.xcodeproj" -scheme Bijou -configuration Debug \
  -destination 'platform=macOS' -derivedDataPath "$BIJOU/Build/Mac" build
open "$BIJOU/Build/Mac/Build/Products/Debug/Bijou.app"
```

## Try home sync

**Upgrading from the long pairing string?** Keep your existing practice
library. Run the updated app from Xcode, stop the old `serve` command with
Ctrl-C, and restart it as in step 2. Already-paired devices keep their
credentials. For a new pairing, use the short code from the restarted Mac.

1. **Make a practice library.** From the repository root, choose a **new**
   directory outside repositories, SynologyDrive and existing OKF bundles:

   ```sh
   BIJOU=experiments/barrys-bijou
   ROOM="$HOME/BijouPractice"
   uv run --locked python "$BIJOU/adapter/fixture.py" "$ROOM"
   ```

   This creates a Personal-shaped v0.3 bundle with six watched movies, a
   watchlist movie, a non-movie, and five generated test posters. Normal
   InnerSanctum Create supplies the ID of the empty `Film Ranking`. The
   adapter binds to this particular bundle and ranking; restarting it uses
   the existing folder. Create a new directory for a fresh test.
2. **Start the adapter on the Mac.** Set `HOME_IP` to the Mac’s actual
   Wi-Fi address (System Settings → Wi-Fi → Details → TCP/IP). Leave this
   process running while testing. For a Mac-only trial use `127.0.0.1`.

   ```sh
   HOME_IP=192.168.1.20  # replace with the Mac's home-network address
   uv run --locked python "$BIJOU/adapter/home.py" serve --bundle "$ROOM" --host "$HOME_IP"
   ```

3. **Pair one app.** On the same home Wi-Fi, open **Home Sync** and allow
   Local Network access if prompted. Bijou finds your Mac automatically;
   choose it if more than one appears. Type the **seven-character code**
   from the Mac’s Terminal and tap **Pair this device**. Uppercase and
   lowercase both work. If the list is empty, enter the address printed
   above the code in the **Mac address (from Terminal)** field. If an older
   build hides the field, tap **Enter Mac address manually**. Tapping **Pair
   this device** also points to the missing field and keeps your code
   while you enter the address. If Local Network access is off, turn it on
   for Bijou in **Settings → Privacy & Security → Local Network**.
   Each code works once and expires after ten minutes; expiry is checked
   by the Mac after you tap Pair.
4. **Pair the other app.** In a second Terminal at the repository root,
   request another code using the same library and address:

   ```sh
   uv run --locked python experiments/barrys-bijou/adapter/home.py invite \
     --bundle "$HOME/BijouPractice"
   ```

   Enter the new code on the other device. If a code expires or too many
   incorrect entries are made, this command issues a fresh one. Each
   paired app should now say **Paired home library**. Text arrives
   first; the Mac prepares thumbnails and the clients keep them for offline
   use. If a poster was still being prepared, **Sync now** retries it.
5. **Try a conflict.** Sync both devices. Disconnect the phone, move a film
   and relaunch. Add a different film on the Mac. Reconnect the phone and
   tap **Sync now**. **Home Sync** shows both orders and lets you place the
   affected film in the Mac’s latest list. An unresolved decision stays
   saved on the phone. **Export ranking as Markdown** works offline.

The adapter defaults to loopback. It runs only while the command is active;
Ctrl-C stops it. `devices` lists enrolled device IDs; `revoke --device ID`
invalidates one credential. Both take `--bundle "$ROOM"`. The synthetic
posters need no external service; an HTTPS artwork source requires an
explicit `--art-host HOSTNAME` at server startup.

## Open a read-only screening copy

For a later trial with an approved **offline** snapshot, `adapter/pack_snapshot.py`
accepts `--snapshot /physical/external/OKF` and `--output /private/folder/movies.bijou.json`.
The output folder must have mode `0700`, be outside repositories and bundles,
and the file must not already exist. Only watched movie details, sources,
ranking information and thumbnails are packaged. HTTPS artwork is fetched
only from explicitly specified `--art-host` names, including redirect
destinations. For TMDb, pass `--art-host media.themoviedb.org --art-host image.tmdb.org`.
The packer never opens
the input as a writer and checks the scoped files again before exporting.

Transfer that private file to the test device and choose **Home Sync →
Open screening copy…**. This library has its own local ranking. Its changes
cannot be sent to the fixture or back to Personal. For an immediate trial,
use the synthetic practice bundle as the snapshot instead.

## Verify the prototype

From the repository root:

```sh
uv run --locked pytest
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  uv run --locked python experiments/barrys-bijou/adapter/rehearse.py
```

The rehearsal creates a temporary external bundle and pairs two native
clients to an ephemeral loopback TLS server. It checks offline SQLite
relaunch, a cached-image payload, a lost acknowledgment, a cross-device
conflict, the exact final order, four audit entries and unchanged movie
bodies and dates. The writer tests also interrupt a first placement between
file writes, verify incomplete snapshots are refused, and recover the
original request. To reconcile an interrupted *fixture* publication:

```sh
uv run --locked innersanctum concept recover --bundle "$ROOM"
```

The clients keep the original request until they obtain its receipt. For a
read-back of the disposable library, use `innersanctum bijou catalog
--bundle "$ROOM"` through `uv run --locked`. These commands and the adapter
target the practice fixture. Use the separately paired Personal adapter for
real rankings.

The **BijouUITests** target exercises the native window: Watched → film →
cancel → confirm → quit → reopen. It uses an isolated temporary sample
database. Run it in Xcode with **Product → Test**, or on a Mac with Xcode
UI automation enabled:

```sh
cd experiments/barrys-bijou
DEVELOPER_DIR=/Applications/Xcode.app/Contents/Developer \
  xcodebuild -project Bijou.xcodeproj -scheme Bijou -destination 'platform=macOS' \
  -parallel-testing-enabled NO test
```

### Build record · 2026-11-25

Xcode 27.2 built the Mac app, an unsigned iPhone app and an iOS Simulator
app. The Mac app opened a window. Four native storage, screening-copy and
sync tests passed, including two clients talking to the Mac adapter over
HTTPS. The Python suite passed all 166 tests. The separate Xcode UI test
runner timed out enabling automation before it executed the click-through.
No iOS simulator runtime was installed on this Mac for that build.

### Personal library acceptance · 2026-11-25

Barry confirmed the end-to-end workflow on his iPhone and Mac: he reranked
a film in the Personal library on the phone, saw **Synced to OKF**, and
verified the new position on the Mac after syncing.
