import AVKit
import SwiftUI

struct StartupNewsreel: View {
    let finish: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.accessibilityVoiceOverEnabled) private var voiceOver
    @Environment(\.scenePhase) private var scenePhase
    @State private var player: AVPlayer?
    @State private var showRules = false
    private var reading: Bool { reduceMotion || voiceOver || showRules }

    var body: some View {
        VStack(spacing: 16) {
            if reading {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        Text("Milestones Newsreel").font(.system(.largeTitle, design: .serif).bold())
                        Text("Begin with a dated event. Draw a card with its date hidden.")
                        Text("Slide the timeline to a gap, then tap Place Here.")
                        Text("A correct guess scores one point and keeps the card. A miss reveals the correct gap and discards the card.")
                        Text("Standard gives you ten guesses. Long Play ends after three misses or when the deck runs out.")
                    }.padding()
                }
            } else if let player {
                VideoPlayer(player: player)
                    .onReceive(NotificationCenter.default.publisher(for: .AVPlayerItemDidPlayToEndTime,
                                                                      object: player.currentItem)) { _ in finish() }
                    .onReceive(NotificationCenter.default.publisher(for: .AVPlayerItemFailedToPlayToEndTime,
                                                                      object: player.currentItem)) { _ in showRules = true }
            } else {
                Spacer()
            }
            HStack {
                if !reading {
                    Button("Read Rules") { showRules = true }
                    Spacer()
                }
                Button(reading ? "Continue" : "Skip Intro", action: finish)
                    .buttonStyle(.borderedProminent)
            }.padding(.horizontal)
        }
        .padding(.vertical)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.ignoresSafeArea())
        .environment(\.colorScheme, .dark)
        .task {
            guard !reading else { return }
            guard let url = Bundle.main.url(forResource: "MilestonesNewsreel", withExtension: "mp4") else {
                showRules = true
                return
            }
            let reel = AVPlayer(url: url)
            player = reel
            if scenePhase == .active { reel.play() }
        }
        .onChange(of: reading) { _, reading in if reading { player?.pause() } }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active && !reading { player?.play() } else { player?.pause() }
        }
        .onDisappear { player?.pause() }
    }
}
