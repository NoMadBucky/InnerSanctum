# Milestones: A Snap History Game

**Find your place in history.**

Open `Chronology.xcodeproj`, select the Chronology scheme and run on a portrait
iPhone (iOS 18 or later). Choose New Game to inspect the dated opening card,
then Draw First Card to begin. Standard gives you ten scored guesses.
Choose Long Play before New Game to play without repeats until your third
miss or the last card in the deck. Each correct placement earns one point;
the opening anchor is free. Both modes let you inspect the final reveal.
Slide the continuous row of dated cards under the fixed center marker.
A flick coasts across multiple cards; when it settles, the marker and year
caption identify the proposed insertion gap. First, Earlier, Later and Last
also move the timeline.
Only Place Here commits. A correct guess grows the table; a miss shows the
correct gap. You can keep browsing after either result. Tap any dated card
to read about it, even on the final table. A perfect round has eleven cards.
High Scores keeps the best ten finished rounds per mode on this iPhone, newest first
for ties. If you make the board, See Results invites you to sign your score
with three initials. Skipping keeps the score unsigned.
The welcome screen plays a silent, bundled montage. Reduce Motion
shows a still; the player stops when the welcome screen is covered or inactive.

## Intro montage

Before the welcome screen, a separate 19.96-second newsreel plays once per app
launch. Skip Intro opens the menu immediately. Read Rules, VoiceOver and
Reduce Motion provide a text introduction to the rules. The Blonien Productions
newsreel pairs its narrated question with these public-domain sources:

- [San Francisco earthquake aftermath](https://commons.wikimedia.org/wiki/File:San_Francisco_Earthquake_aftermath,_1906.ogv),
  Market Street after the 1906 earthquake, Prelinger Archives (`quake.ogv`).
- [The first Wright Flyer flight](https://commons.wikimedia.org/wiki/File:Wrightflyer.jpg),
  John T. Daniels’s photograph of Orville Wright piloting the Flyer (`Wrightflyer.jpg`).

The announcer uses Kokoro's British male voice Lewis (`bm_lewis`) with British
phonemes for “Blah-nee-in,” second-syllable stress on *presents*, and a
midrange lift for the vintage newsreel sound.
Shots follow the recorded phrases without stretching or accelerating the voice.
An original fanfare leads in before the announcer and ducks beneath speech.
The answer card compares the Wright flight (1903) with the earthquake (1906).
Speech is rendered when building the film; the app only plays the audio track.
To rebuild on macOS, place the two source files named above together with
`kokoro-v1.0.int8.onnx` and `voices-v1.0.bin` from the
[Kokoro ONNX model release](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0).
Install FFmpeg and Python packages `kokoro-onnx==0.4.9`, `soundfile`, and
`Pillow`, then run `python3 Tools/build_newsreel.py /path/to/originals`.

The 14.5-second, 60 fps loop dissolves between five images:

- [Diamond Sutra frontispiece](https://commons.wikimedia.org/wiki/File:Diamond_sutra.jpg),
  868; International Dunhuang Project, public domain.
- [Under the Wave off Kanagawa](https://commons.wikimedia.org/wiki/File:The_Great_Wave_off_Kanagawa.jpg),
  Katsushika Hokusai, early 1830s.
- [First flight of the Wright Flyer](https://commons.wikimedia.org/wiki/File:Wrightflyer.jpg),
  John T. Daniels, 1903.
- [Earthrise](https://commons.wikimedia.org/wiki/File:NASA-Apollo8-Dec24-Earthrise.jpg),
  William Anders / NASA, Apollo 8, 1968.
- [Mandela voting in 1994](https://commons.wikimedia.org/wiki/File:Mandela_voting_in_1994.jpg),
  Paul Weinberg. The photograph is cropped, panned and dissolved in the film.
  The montage is released under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/).

To rebuild the H.264 video and matching still, download the originals under
their linked filenames and run `python3 Tools/build_intro.py /path/to/originals`
from this directory with Pillow and FFmpeg installed.

`Chronology/events.json` holds the offline deck. Each clue names one event;
`date` preserves the source's date precision and `year` controls grading.
Each `id` is the corresponding Wikipedia article key. When no separate source
is specified, that article is the source. Learn More optionally requests an
article description; the result never affects a guess.

The prototype deck contains 322 distinct years: the original 22 cards plus
300 clues selected from the English Wikipedia On This Day event feed.
Added cards link to the source day and a related article, with attribution
in Learn More. Their adapted Wikipedia text is under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
The entire text deck is bundled; no live feed, image download or API call is
needed to start a round. Only the drawn hand enters the timeline.

## Playtest

Use Product > Test in Xcode with an iPhone simulator. `TimelineTests` starts
at guess ten with ten dated cards, swipes toward the far end, jumps to Last,
submits a miss and checks the ghost at the beginning and the final score.
On a small phone, also try a slow swipe and a fast flick, revisit the reveal
after Learn More, and repeat with VoiceOver and Reduce Motion.

To run the engine checks from this directory without an iPhone runtime:

```sh
swiftc Chronology/{Round,ScoreHistory}.swift Tests/main.swift -o "$TMPDIR/chronology-tests"
"$TMPDIR/chronology-tests" Chronology/events.json
```

## After the prototype

Playtest the expanded pool for clue clarity, difficulty and coverage across
regions, eras and disciplines before choosing cards for custom artwork.
