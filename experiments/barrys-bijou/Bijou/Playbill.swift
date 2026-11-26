import SwiftUI

/// The fixed enamel and brass of the marquee, independent of the auditorium lights.
enum MarqueeFinish {
    static let enamel = Color(red: 0.055, green: 0.13, blue: 0.18)
    static let peacock = Color(red: 0.10, green: 0.23, blue: 0.27)
    static let gold = Color(red: 0.92, green: 0.77, blue: 0.51)
    static let ivory = Color(red: 0.99, green: 0.95, blue: 0.85)
}

/// Use the lobby lettering on both the playbill and the theatre in the reel.
enum BijouWordmark {
    static let font = Font.system(.largeTitle, design: .serif).weight(.medium)
    static let text = Text("Bijou").font(font)
}

/// A brass picture rail with two setbacks at each corner.
struct SteppedRail: Shape {
    func path(in rect: CGRect) -> Path {
        let x = rect.minX, y = rect.minY, r = rect.maxX, b = rect.maxY
        let s = min(5, rect.width / 8, rect.height / 8)
        let points = [(x+2*s,y), (r-2*s,y), (r-2*s,y+s), (r-s,y+s), (r-s,y+2*s), (r,y+2*s),
                      (r,b-2*s), (r-s,b-2*s), (r-s,b-s), (r-2*s,b-s), (r-2*s,b), (x+2*s,b),
                      (x+2*s,b-s), (x+s,b-s), (x+s,b-2*s), (x,b-2*s), (x,y+2*s),
                      (x+s,y+2*s), (x+s,y+s), (x+2*s,y+s)]
        var path = Path()
        for (i, p) in points.enumerated() {
            let pt = CGPoint(x: p.0, y: p.1)
            if i == 0 { path.move(to: pt) } else { path.addLine(to: pt) }
        }
        path.closeSubpath()
        return path
    }
}

struct MarqueePanel: ViewModifier {
    func body(content: Content) -> some View {
        content.padding(24).frame(maxWidth: .infinity)
            .foregroundStyle(MarqueeFinish.ivory)
            .background(LinearGradient(colors: [MarqueeFinish.peacock, MarqueeFinish.enamel],
                                       startPoint: .topLeading, endPoint: .bottomTrailing))
            .overlay {
                SteppedRail().stroke(MarqueeFinish.gold.opacity(0.8), lineWidth: 1)
                    .padding(6).allowsHitTesting(false).accessibilityHidden(true)
            }
    }
}

struct BillingLine: View {
    let title: String
    var body: some View {
        HStack(spacing: 10) {
            wing
            Text(title).font(.caption.weight(.semibold)).tracking(2).multilineTextAlignment(.center)
            wing.scaleEffect(x: -1, y: 1)
        }
    }
    private var wing: some View {
        VStack(alignment: .trailing, spacing: 3) {
            Rectangle().frame(width: 26, height: 1)
            Rectangle().frame(width: 17, height: 1)
        }.accessibilityHidden(true)
    }
}

struct AdmissionStyle: ButtonStyle {
    @Environment(\.isEnabled) private var enabled
    func makeBody(configuration: Configuration) -> some View {
        configuration.label.font(.headline)
            .padding(.horizontal, 18).frame(minHeight: 44)
            .foregroundStyle(MarqueeFinish.enamel)
            .background(MarqueeFinish.gold, in: SteppedRail())
            .overlay { SteppedRail().stroke(MarqueeFinish.enamel.opacity(0.45)).padding(4).allowsHitTesting(false) }
            .contentShape(Rectangle())
            .opacity(!enabled ? 0.45 : configuration.isPressed ? 0.75 : 1)
    }
}
