import AVFoundation
import SwiftUI

struct IntroBackdrop: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @Environment(\.scenePhase) private var scenePhase
    let visible: Bool

    var body: some View {
        GeometryReader { bounds in
            ZStack {
                Image("IntroStill").resizable().scaledToFill()
                    .frame(width: bounds.size.width, height: bounds.size.height)
                if !reduceMotion, visible, scenePhase == .active,
                   let url = Bundle.main.url(forResource: "HistoricalIntro", withExtension: "mp4") {
                    Film(url: url)
                }
                LinearGradient(colors: [.black.opacity(0.30), .black.opacity(0.68), .black.opacity(0.94)],
                               startPoint: .top, endPoint: .bottom)
            }.clipped()
        }
        .ignoresSafeArea().allowsHitTesting(false).accessibilityHidden(true)
    }
}

private struct Film: UIViewRepresentable {
    let url: URL
    final class Surface: UIView {
        override class var layerClass: AnyClass { AVPlayerLayer.self }
        let queue = AVQueuePlayer()
        var looper: AVPlayerLooper?
    }

    func makeUIView(context: Context) -> Surface {
        let view = Surface()
        let layer = view.layer as! AVPlayerLayer
        view.queue.isMuted = true
        layer.videoGravity = .resizeAspectFill
        layer.player = view.queue
        view.looper = AVPlayerLooper(player: view.queue, templateItem: AVPlayerItem(url: url))
        view.queue.play()
        return view
    }

    func updateUIView(_ view: Surface, context: Context) {}

    static func dismantleUIView(_ view: Surface, coordinator: ()) {
        view.queue.pause()
        view.looper?.disableLooping()
        view.queue.removeAllItems()
    }
}
