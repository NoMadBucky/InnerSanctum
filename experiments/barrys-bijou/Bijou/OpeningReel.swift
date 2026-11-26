import AVFoundation
import SwiftUI

@MainActor
private final class ReelAccompaniment: ObservableObject {
    private var player: AVPlayer?

    func play(from elapsed: TimeInterval) {
        guard let url = Bundle.main.url(forResource: "ReelPiano", withExtension: "m4a") else { return }
        let p = player ?? AVPlayer(url: url)
        player = p
        p.volume = 0.85
        p.automaticallyWaitsToMinimizeStalling = false
        p.seek(to: CMTime(seconds: elapsed, preferredTimescale: 44100), toleranceBefore: .zero, toleranceAfter: .zero)
        p.play()
    }

    func stop() { player?.pause(); player = nil }
}

/// An original silent short in a 4:3 academy frame.
struct OpeningReel: View {
    let finish: () -> Void
    @Environment(\.scenePhase) private var phase
    @State private var started: Date?
    @State private var played: TimeInterval = 0
    @StateObject private var piano = ReelAccompaniment()
    @AppStorage("openingReelMuted") private var muted = false
    private let length = 12.0

    var body: some View {
        ZStack {
            Color(white: 0.045).ignoresSafeArea()
            TimelineView(.animation(minimumInterval: 1.0 / 60, paused: phase != .active)) { timeline in
                let t = played + (started.map { max(0, timeline.date.timeIntervalSince($0)) } ?? 0)
                Canvas { context, size in
                    var c = context
                    c.scaleBy(x: size.width / 640, y: size.height / 480)
                    let frame = CGRect(x: 0, y: 0, width: 640, height: 480)
                    c.clip(to: Path(roundedRect: frame, cornerRadius: 14))
                    let tick = Int(t * 12) // Age the print, not the camera movement.
                    if t < 3 { leader(c, t) } else { street(c, t - 3) }
                    wear(c, tick)
                    c.fill(Path(frame), with: .radialGradient(Gradient(colors: [.clear, .black.opacity(0.4)]),
                                                              center: CGPoint(x: 320, y: 230), startRadius: 140, endRadius: 403))
                    if t > 11 { c.fill(Path(frame), with: .color(.black.opacity(min(1, t - 11)))) }
                }
            }
            .aspectRatio(4/3, contentMode: .fit).frame(maxWidth: 720).padding(12)
            .accessibilityHidden(true)
            VStack {
                Spacer()
                HStack {
                    Button { muted.toggle() } label: {
                        Label(muted ? "Unmute piano" : "Mute piano",
                              systemImage: muted ? "speaker.slash.fill" : "speaker.wave.2.fill").labelStyle(.iconOnly)
                    }
                    Button("Skip intro") { piano.stop(); finish() }
                        .keyboardShortcut(.cancelAction).accessibilityIdentifier("skip-intro")
                }.buttonStyle(.bordered).foregroundStyle(.white)
            }.padding(20)
        }
        .task(id: phase) {
            guard phase == .active else { return }
            let start = Date()
            started = start
            if !muted { piano.play(from: played) }
            do { try await Task.sleep(for: .seconds(max(0, length - played))) }
            catch { return }
            piano.stop(); finish()
        }
        .onDisappear { piano.stop() }
        .onChange(of: muted) { _, silent in
            if !silent, phase == .active, let started {
                piano.play(from: played + max(0, Date().timeIntervalSince(started)))
            } else { piano.stop() }
        }
        .onChange(of: phase) { _, next in
            if next != .active, let start = started {
                piano.stop()
                played += max(0, Date().timeIntervalSince(start)); started = nil
            }
        }
    }

    private func box(_ c: GraphicsContext, _ x: Double, _ y: Double, _ w: Double, _ h: Double, _ gray: Double) {
        c.fill(Path(CGRect(x: x, y: y, width: w, height: h)), with: .color(Color(white: gray)))
    }
    private func letters(_ c: GraphicsContext, _ text: String, at point: CGPoint, size: Double, gray: Double) {
        c.draw(Text(verbatim: text).font(.system(size: size, weight: .medium, design: .serif))
            .foregroundStyle(Color(white: gray)), at: point)
    }
    private func leader(_ c: GraphicsContext, _ t: Double) {
        box(c, -2, -2, 644, 484, 0.74)
        let center = CGPoint(x: 320, y: 240)
        var sweep = Path()
        sweep.move(to: center)
        sweep.addArc(center: center, radius: 420, startAngle: .degrees(-90),
                     endAngle: .degrees(-90 + 360 * (t - floor(t))), clockwise: false)
        sweep.closeSubpath()
        c.fill(sweep, with: .color(.black.opacity(0.16)))
        box(c, 319, 0, 2, 480, 0.38); box(c, 0, 239, 640, 2, 0.38)
        for r: CGFloat in [148, 160] {
            c.stroke(Path(ellipseIn: CGRect(x: 320-r, y: 240-r, width: 2*r, height: 2*r)),
                     with: .color(.white.opacity(0.8)), lineWidth: 3)
        }
        letters(c, "\(3 - Int(t))", at: center, size: 225, gray: 0.13)
    }
    private func street(_ c: GraphicsContext, _ t: Double) {
        box(c, -2, -2, 644, 484, 0.71)
        var set = c
        let pan = -t * 3
        set.translateBy(x: pan, y: 0)
        // Shopfronts and individually lit upper windows behind the theatre.
        for i in 0..<9 {
            let x = Double(i) * 93 - 47, y = Double([108, 135, 94, 120][i % 4])
            box(set, x, y, 92, 373-y, 0.36 + Double(i % 3)*0.06)
            box(set, x-2, y-4, 96, 7, 0.28)
            for row in 0..<3 {
                for col in 0..<3 {
                    box(set, x+10+Double(col)*27, y+17+Double(row)*42, 15, 26,
                        (i+row+col).isMultiple(of: 4) ? 0.67 : 0.23)
                }
            }
        }
        for step in 0..<4 {
            let n = Double(step)
            box(set, 205+n*21, 153-n*14, 270-n*42, 217+n*14, 0.49+n*0.04)
        }
        box(set, 250, 268, 180, 103, 0.20)
        for i in 0..<4 { box(set, 257+Double(i)*43, 286, 34, 68, 0.38) }
        box(set, 183, 193, 315, 77, 0.23)
        box(set, 188, 198, 305, 62, 0.84)
        set.stroke(SteppedRail().path(in: CGRect(x: 193, y: 202, width: 295, height: 54)),
                   with: .color(Color(white: 0.35)), lineWidth: 1.5)
        var sign = set
        sign.translateBy(x: 340, y: 225)
        let name = sign.resolve(Text(verbatim: "Bijou Theatre").font(BijouWordmark.font).foregroundStyle(Color(white: 0.14)))
        let size = name.measure(in: CGSize(width: 1000, height: 200))
        let scale = min(1.25, 213 / max(1, size.width), 47 / max(1, size.height))
        sign.scaleBy(x: scale, y: scale)
        sign.draw(name, at: .zero)
        for x in [230.0, 300.0, 370.0] {
            let lamp = CGPoint(x: x + 40, y: 265)
            set.fill(Path(ellipseIn: CGRect(x: lamp.x-8, y: lamp.y-8, width: 16, height: 16)),
                     with: .radialGradient(Gradient(colors: [.white, .clear]), center: lamp, startRadius: 2, endRadius: 8))
        }
        for x in [204.0, 455.0] {
            box(set, x, 224, 21, 2, 0.45); box(set, x+3, 230, 15, 1, 0.45)
        }
        box(c, 0, 371, 644, 111, 0.33)
        box(c, 0, 417, 644, 2, 0.62); box(c, 0, 430, 644, 2, 0.52)
        // Ease into the stop, hold while the passengers alight, then accelerate out.
        let arrival = max(0, 1 - t / 1.9)
        let departure = max(0, t - 5.9)
        let stopX = -26.0
        let carX = stopX - 260 * arrival * arrival + 64 * departure * departure
        if departure > 0 { crowd(set, t: t) }
        var car = c
        car.translateBy(x: carX + pan, y: 0)
        box(car, 6, 288, 261, 10, 0.17); box(car, 0, 298, 274, 107, 0.26)
        for i in 0..<7 { box(car, 8+Double(i)*31, 305, 24, 38, 0.65) }
        box(car, 2, 352, 270, 3, 0.75)
        letters(car, "C I T Y   L I N E", at: CGPoint(x: 138, y: 375), size: 14, gray: 0.85)
        for x in [34, 212] { cWheel(car, x: x) }
        box(car, 228, 302, 36, 99, 0.12)
        let door = min(smooth((t - 1.7) / 0.4), 1 - smooth((t - 5.45) / 0.45))
        for x in [228.0, 246 + 18 * door] { box(car, x, 302, 18 * (1 - door), 97, 0.46) }
        if departure == 0 { crowd(set, t: t) }
        if t > 6.5 {
            var title = c
            title.opacity = smooth(t - 6.5)
            letters(title, "A Bijou Presentation", at: CGPoint(x: 320, y: 451), size: 28, gray: 0.95)
        }
    }
    private func smooth(_ fraction: Double) -> Double {
        let u = min(1, max(0, fraction))
        return u * u * (3 - 2 * u)
    }

    private func crowd(_ c: GraphicsContext, t: Double) {
        // Draw the earlier arrivals (further upstage) first. Two streams split
        // around one another on the pavement and converge on four entrance bays.
        for i in 0..<30 {
            let age = t - 2 - Double(i) * 0.109
            let travel = 2.15 + Double(i % 4) * 0.15
            guard age >= 0, age < travel else { continue }
            let u = age / travel
            let lane = Double((i * 7) % 13)
            let endX = 274.0 + Double((i * 3) % 4) * 43
            let x = 219 + (endX - 219) * smooth(u) + sin(.pi * u) * (33 + lane)
            let y = 398 - 39 * smooth(u) + sin(.pi * 2 * u) * (8 + lane)
            let gait = sin(age * (15 + Double(i % 3)) + Double(i))
            var p = c
            p.opacity = smooth(age / 0.14) * smooth((travel - age) / 0.23)
            p.translateBy(x: x, y: y - abs(gait) * 0.7)
            let scale = (0.92 + Double(i % 5) * 0.055) * (1 - u * 0.27)
            p.scaleBy(x: scale, y: scale)
            let ink = Color(white: 0.09 + Double(i % 6) * 0.035)
            var legs = Path()
            for side in [-1.0, 1.0] {
                legs.move(to: CGPoint(x: side * 2, y: -11))
                legs.addLine(to: CGPoint(x: side * (2 + gait * 4), y: 0))
            }
            p.stroke(legs, with: .color(ink), style: StrokeStyle(lineWidth: 3, lineCap: .round))
            var coat = Path()
            coat.move(to: CGPoint(x: -3, y: -23)); coat.addLine(to: CGPoint(x: 4, y: -23))
            coat.addLine(to: CGPoint(x: i.isMultiple(of: 3) ? 8 : 5, y: -8))
            coat.addLine(to: CGPoint(x: -5, y: -9)); coat.closeSubpath()
            p.fill(coat, with: .color(ink))
            p.fill(Path(ellipseIn: CGRect(x: -3, y: -30, width: 7, height: 8)), with: .color(Color(white: 0.44)))
            if !i.isMultiple(of: 3) {
                box(p, -5, -29, 11, 2, 0.15); box(p, -3, -32, 7, 4, 0.19)
            }
            if i.isMultiple(of: 5) { box(p, 4 + gait, -13, 7, 6, 0.27) }
        }
    }
    private func cWheel(_ c: GraphicsContext, x: Int) {
        c.fill(Path(ellipseIn: CGRect(x: x, y: 394, width: 24, height: 22)), with: .color(Color(white: 0.16)))
    }
    private func wear(_ c: GraphicsContext, _ tick: Int) {
        var dust = Path()
        for i in 0..<90 {
            let n = (tick % 300 + 1) * 997 + i * 37
            let x = (n * 173 + i * i) % 640
            let y = (n * 79 + i * i * 7) % 480
            dust.addRect(CGRect(x: CGFloat(x), y: CGFloat(y), width: 1.4, height: 1))
        }
        c.fill(dust, with: .color(.white.opacity(0.24)))
        if tick % 47 < 5 { box(c, Double(tick / 47 * 79 % 640), 0, 0.7, 480, 0.68) }
    }
}
