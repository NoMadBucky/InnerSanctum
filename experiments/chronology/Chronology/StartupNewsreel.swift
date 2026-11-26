import AVKit
import SwiftUI

struct StartupNewsreel: View {
    var explicitReplay = false
    let finish: () -> Void
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.accessibilityVoiceOverEnabled) private var voiceOver
    @Environment(\.scenePhase) private var scenePhase
    @State private var player: AVPlayer?
    private var bypass: Bool { !explicitReplay && (reduceMotion || voiceOver) }

    var body: some View {
        VStack(spacing: 16) {
            if let player {
                VideoPlayer(player: player)
                    .onReceive(NotificationCenter.default.publisher(for: .AVPlayerItemDidPlayToEndTime,
                                                                      object: player.currentItem)) { _ in finish() }
                    .onReceive(NotificationCenter.default.publisher(for: .AVPlayerItemFailedToPlayToEndTime,
                                                                      object: player.currentItem)) { _ in finish() }
            } else {
                Spacer()
            }
            Button("Skip Intro", action: finish).buttonStyle(.borderedProminent)
        }
        .padding(.vertical)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color.black.ignoresSafeArea())
        .environment(\.colorScheme, .dark)
        .task {
            guard !bypass, let url = Bundle.main.url(forResource: "MilestonesNewsreel", withExtension: "mp4") else {
                finish()
                return
            }
            let reel = AVPlayer(url: url)
            player = reel
            if scenePhase == .active { reel.play() }
        }
        .onChange(of: bypass) { _, skip in if skip { finish() } }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active && !bypass { player?.play() } else { player?.pause() }
        }
        .onDisappear { player?.pause() }
    }
}
