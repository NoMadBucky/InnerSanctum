import SwiftUI

/// An original silent short, drawn in a 4:3 academy frame at silent-film speed.
struct OpeningReel: View {
    let finish: () -> Void
    @Environment(\.scenePhase) private var phase
    @State private var started: Date?
    @State private var played: TimeInterval = 0
    private let length = 12.0

    var body: some View {
        ZStack {
            Color(white: 0.045).ignoresSafeArea()
            TimelineView(.animation(minimumInterval: 1 / 18, paused: phase != .active)) { timeline in
                let t = played + (started.map { max(0, timeline.date.timeIntervalSince($0)) } ?? 0)
                Canvas { context, size in
                    var c = context
                    c.scaleBy(x: size.width / 640, y: size.height / 480)
                    let frame = CGRect(x: 0, y: 0, width: 640, height: 480)
                    c.clip(to: Path(roundedRect: frame, cornerRadius: 14))
                    let tick = Int(t * 18)
                    c.translateBy(x: sin(Double(tick) * 1.7) * 0.7, y: cos(Double(tick) * 0.9) * 0.7)
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
                Button("Skip intro", action: finish)
                    .buttonStyle(.bordered).foregroundStyle(.white)
                    .keyboardShortcut(.cancelAction).accessibilityIdentifier("skip-intro")
            }.padding(20)
        }
        .task(id: phase) {
            guard phase == .active else { return }
            let start = Date()
            started = start
            do { try await Task.sleep(for: .seconds(max(0, length - played))) }
            catch { return }
            finish()
        }
        .onChange(of: phase) { _, next in
            if next != .active, let start = started {
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
        set.translateBy(x: -t * 5, y: 0)
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
        letters(set, "B I J O U", at: CGPoint(x: 340, y: 227), size: 50, gray: 0.18)
        for i in 0..<26 { box(set, 190+Double(i)*12, 263, 4, 3, 0.86) }
        box(c, 0, 371, 644, 111, 0.33)
        box(c, 0, 417, 644, 2, 0.62); box(c, 0, 430, 644, 2, 0.52)
        // The passing streetcar briefly masks the doors, then clears the marquee.
        var car = c
        car.translateBy(x: -285 + t * 122, y: 0)
        box(car, 6, 288, 261, 10, 0.17); box(car, 0, 298, 274, 107, 0.26)
        for i in 0..<8 { box(car, 8+Double(i)*33, 305, 25, 38, 0.65) }
        box(car, 2, 352, 270, 3, 0.75)
        letters(car, "C I T Y   L I N E", at: CGPoint(x: 138, y: 375), size: 14, gray: 0.85)
        for x in [34, 212] { cWheel(car, x: x) }
        if t > 5 {
            var title = c
            title.opacity = min(1, t - 5)
            letters(title, "A Bijou Presentation", at: CGPoint(x: 320, y: 451), size: 28, gray: 0.95)
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
