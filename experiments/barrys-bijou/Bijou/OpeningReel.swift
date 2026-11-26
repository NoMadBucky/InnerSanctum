import AVFoundation
import SwiftUI
#if os(macOS)
import AppKit
#else
import UIKit
#endif

/// A single, local picture-and-piano print. Pausing either track pauses both.
@MainActor
private final class ReelProjection: ObservableObject {
    let player = AVPlayer()
    private var endObserver: NSObjectProtocol?
    private var failureObserver: NSKeyValueObservation?

    func start(muted: Bool, finish: @escaping () -> Void) {
        guard let url = Bundle.main.url(forResource: "BijouOpening", withExtension: "mp4") else { finish(); return }
        let item = AVPlayerItem(url: url)
        endObserver = NotificationCenter.default.addObserver(forName: AVPlayerItem.didPlayToEndTimeNotification,
                                                            object: item, queue: .main) { [weak self] _ in
            Task { @MainActor in if self?.player.currentItem === item { finish() } }
        }
        failureObserver = item.observe(\.status, options: [.new]) { [weak self] item, _ in
            if item.status == .failed {
                Task { @MainActor in if self?.player.currentItem === item { finish() } }
            }
        }
        player.isMuted = muted
        player.volume = 0.85
        player.actionAtItemEnd = .pause
        player.replaceCurrentItem(with: item)
    }

    func stop() {
        player.pause()
        if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
        endObserver = nil
        failureObserver = nil
        player.replaceCurrentItem(with: nil)
    }
}

// AVPlayerLayer presents frames on their media timestamps without transport controls.
#if os(macOS)
private struct ReelScreen: NSViewRepresentable {
    let player: AVPlayer
    func makeNSView(context: Context) -> NSView {
        let screen = NSView()
        screen.wantsLayer = true
        screen.layer = AVPlayerLayer(player: player)
        return screen
    }
    func updateNSView(_ screen: NSView, context: Context) {}
}
#else
private struct ReelScreen: UIViewRepresentable {
    final class Screen: UIView {
        override class var layerClass: AnyClass { AVPlayerLayer.self }
    }
    let player: AVPlayer
    func makeUIView(context: Context) -> Screen {
        let screen = Screen()
        (screen.layer as? AVPlayerLayer)?.player = player
        return screen
    }
    func updateUIView(_ screen: Screen, context: Context) {}
}
#endif

struct OpeningReel: View {
    let finish: () -> Void
    @Environment(\.scenePhase) private var phase
    @StateObject private var projection = ReelProjection()
    @State private var finished = false
    @AppStorage("openingReelMuted") private var muted = false

    private func leave() {
        guard !finished else { return }
        finished = true
        projection.stop()
        finish()
    }

    var body: some View {
        ZStack {
            Color(white: 0.045).ignoresSafeArea()
            ReelScreen(player: projection.player)
                .aspectRatio(4.0 / 3, contentMode: .fit).frame(maxWidth: 720).padding(12)
                .allowsHitTesting(false).accessibilityHidden(true)
            VStack {
                Spacer()
                HStack {
                    Button { muted.toggle() } label: {
                        Label(muted ? "Unmute piano" : "Mute piano",
                              systemImage: muted ? "speaker.slash.fill" : "speaker.wave.2.fill").labelStyle(.iconOnly)
                    }
                    Button("Skip intro", action: leave)
                        .keyboardShortcut(.cancelAction).accessibilityIdentifier("skip-intro")
                }.buttonStyle(.bordered).foregroundStyle(.white)
            }.padding(20)
        }
        .onAppear {
            projection.start(muted: muted, finish: leave)
            if phase == .active { projection.player.play() }
        }
        .onDisappear { projection.stop() }
        .onChange(of: muted) { _, silent in projection.player.isMuted = silent }
        .onChange(of: phase) { _, next in
            if next == .active && !finished { projection.player.play() } else { projection.player.pause() }
        }
    }
}
