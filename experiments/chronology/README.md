# Chronology

Open `Chronology.xcodeproj`, select the Chronology scheme and run on a portrait
iPhone (iOS 18 or later). Each round deals one dated anchor and ten guesses.
Slide the continuous row of dated cards under the fixed center marker.
A flick coasts across multiple cards; when it settles, the marker and year
caption identify the proposed insertion gap. First, Earlier, Later and Last
also move the timeline.
Only Place Here commits. A correct guess grows the table; a miss shows the
correct gap until Draw Next. A perfect round has eleven dated cards.

`Chronology/events.json` holds the offline deck. Each clue names one event;
`date` preserves the source's date precision and `year` controls grading.
Each `id` is the corresponding Wikipedia article key. When no separate source
is specified, that article is the source. Learn More optionally requests an
article description; the result never affects a guess.

## Playtest

Use Product > Test in Xcode with an iPhone simulator. `TimelineTests` starts
at guess ten with ten dated cards, swipes toward the far end, jumps to Last,
submits a miss and checks the ghost at the beginning and the final score.
On a small phone, also try a slow swipe and a fast flick, revisit the reveal
after Learn More, and repeat with VoiceOver and Reduce Motion.

To run the engine checks from this directory without an iPhone runtime:

```sh
swiftc Chronology/Round.swift Tests/main.swift -o "$TMPDIR/chronology-tests"
"$TMPDIR/chronology-tests" Chronology/events.json
```

## After the prototype

Target 100 reviewed cards across regions, eras and disciplines, then consider
250 and a subset with custom reveal artwork. A longer-play mode should deal
without replacement until the deck runs out or its stopping rule is reached.
Three misses is a playtest candidate, not a settled rule.
