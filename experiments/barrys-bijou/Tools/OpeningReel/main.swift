import CoreGraphics
import Foundation
import SwiftUI

// Render in 640 × 480 set coordinates; write 960 × 720 BGRA frames to ffmpeg.
let width = 960, height = 720, fps = 60
let gate = CGRect(x: 0, y: 0, width: 640, height: 480)

func clamp(_ t: Double) -> Double { min(1, max(0, t)) }
func ease(_ t: Double) -> Double { let u = clamp(t); return u * u * (3 - 2 * u) }
func between(_ a: Double, _ b: Double, _ u: Double) -> Double { a + (b - a) * u }
typealias XY = (Double, Double)

struct Ink {
    let c: CGContext
    func layer(_ draw: () -> Void) { c.saveGState(); draw(); c.restoreGState() }
    func box(_ x: Double, _ y: Double, _ w: Double, _ h: Double, _ gray: Double) {
        c.setFillColor(gray: gray, alpha: 1); c.fill(CGRect(x: x, y: y, width: w, height: h))
    }
    func oval(_ x: Double, _ y: Double, _ w: Double, _ h: Double, _ gray: Double) {
        c.setFillColor(gray: gray, alpha: 1); c.fillEllipse(in: CGRect(x: x, y: y, width: w, height: h))
    }
    func line(_ points: [XY], _ gray: Double, _ weight: Double = 1) {
        c.beginPath(); c.setStrokeColor(gray: gray, alpha: 1); c.setLineWidth(weight)
        c.addLines(between: points.map { CGPoint(x: $0.0, y: $0.1) }); c.strokePath()
    }
    func shape(_ points: [XY], _ gray: Double) {
        c.beginPath(); c.setFillColor(gray: gray, alpha: 1)
        c.addLines(between: points.map { CGPoint(x: $0.0, y: $0.1) }); c.closePath(); c.fillPath()
    }
    func image(_ image: CGImage, in r: CGRect) {
        layer {
            c.translateBy(x: r.minX, y: r.maxY); c.scaleBy(x: 1, y: -1)
            c.draw(image, in: CGRect(origin: .zero, size: r.size))
        }
    }
}

// Rasterize the type once, using the same SwiftUI lettering as the lobby, then
// letterpress it onto the sets. No machine-specific third-party font to locate.
@MainActor func plate(_ text: Text) -> CGImage {
    let renderer = ImageRenderer(content: text.fixedSize())
    renderer.scale = 2.5
    return renderer.cgImage!
}
@MainActor struct Plates {
    let sign = plate(Text(verbatim: "Bijou Theatre").font(BijouWordmark.font).foregroundStyle(.black))
    let numerals = (1...3).map { plate(Text(verbatim: "\($0)").font(.system(size: 177, weight: .medium, design: .serif)).foregroundStyle(.black)) }
    let route = plate(Text(verbatim: "CITY LINE").font(.system(size: 13, weight: .semibold, design: .serif)).tracking(2).foregroundStyle(.white))
    let title = plate(Text(verbatim: "A Bijou Presentation").font(BijouWordmark.font).foregroundStyle(.white))
    let studio = plate(Text(verbatim: "Blonien Productions").font(BijouWordmark.font).foregroundStyle(.white))
    let tickets = plate(Text(verbatim: "TICKETS").font(.system(size: 9, weight: .bold)).tracking(1.2).foregroundStyle(.black))
    let fleet = plate(Text(verbatim: "27").font(.system(size: 9, weight: .bold, design: .serif)).foregroundStyle(.white))
    let stock = plate(Text(verbatim: "BIJOU   •   SAFETY FILM    /    No. 01").font(.system(size: 9, design: .monospaced)).foregroundStyle(.black))
}

func stamp(_ ink: Ink, _ image: CGImage, center: XY, width: Double, maxHeight: Double) {
    let scale = min(width / Double(image.width), maxHeight / Double(image.height))
    let w = scale * Double(image.width), h = scale * Double(image.height)
    ink.image(image, in: CGRect(x: center.0 - w/2, y: center.1 - h/2, width: w, height: h))
}

@MainActor func leader(_ g: Ink, _ p: Plates, _ t: Double) {
    g.box(-8, -8, 656, 496, 0.73)
    let n = min(2, Int(t))
    let phi = (t - Double(n)) * 2 * .pi
    let c = g.c, center = CGPoint(x: 320, y: 240)
    c.beginPath(); c.move(to: center)
    c.addArc(center: center, radius: 415, startAngle: -.pi / 2, endAngle: phi - .pi / 2, clockwise: false)
    c.closePath(); c.setFillColor(gray: 0.05, alpha: 0.13); c.fillPath()
    g.line([(-4,240),(644,240)], 0.40); g.line([(320,-4),(320,484)], 0.40)
    for r in [148.0, 160.0] {
        c.setStrokeColor(gray: 0.91, alpha: 1); c.setLineWidth(2)
        c.strokeEllipse(in: CGRect(x: 320-r, y: 240-r, width: 2*r, height: 2*r))
    }
    for i in 0..<24 {
        let a = Double(i) * .pi / 12, outer = i.isMultiple(of: 3) ? 170.0 : 166.0
        g.line([(320+162*sin(a),240-162*cos(a)), (320+outer*sin(a),240-outer*cos(a))], 0.42, 1)
    }
    stamp(g, p.numerals[2-n], center: (320,231), width: 142, maxHeight: 207)
    stamp(g, p.stock, center: (320,443), width: 211, maxHeight: 12)
}

@MainActor func streetscape(_ g: Ink, _ p: Plates, _ t: Double) {
    g.box(-32, -8, 722, 498, 0.57)
    // Carbon-arc searchlights: feather the beam edges and let the skyline
    // occlude them. The lamps swing inward, then settle apart for the credit.
    for side in [-1.0, 1.0] {
        let origin = 340 + side * 112
        let aim = 340 + side * (42 + 136 * cos((t-ReelCue.streetCut)*0.94 + side*0.18))
        for band in 0..<12 {
            let halfWidth = 38 - Double(band)*2.1
            g.layer {
                g.c.setAlpha(0.036)
                g.shape([(origin-2,158),(aim-halfWidth,-10),(aim+halfWidth,-10),(origin+2,158)], 1)
            }
        }
    }
    for i in 0..<9 {
        let x = Double(i) * 93 - 47, roof = Double([111,135,91,123][i % 4])
        let stone = 0.37 + Double(i % 3)*0.06
        g.box(x, roof, 92, 374-roof, stone); g.box(x-2, roof-5, 95, 6, 0.26)
        g.line([(x,roof+4),(x+91,roof+4)], 0.65)
        for row in 0..<3 {
            for col in 0..<3 {
                let wx = x+10+Double(col)*27, wy = roof+16+Double(row)*42
                g.box(wx, wy, 15, 26, (i+row+col).isMultiple(of: 4) ? 0.65 : 0.24)
                g.box(wx, wy+8, 15, 1.3, stone); g.box(wx-1, wy+26, 17, 2, 0.55)
            }
        }
        g.box(x+5, 288, 83, 55, 0.23); g.box(x+8, 291, 77, 48, 0.43)
        for slat in 0..<8 { g.box(x+Double(slat)*11, 275, 11, 12, slat.isMultiple(of: 2) ? 0.60 : 0.37) }
    }
    for step in 0..<4 {
        let n = Double(step), x = 205+n*21, y = 153-n*14
        g.box(x, y, 270-n*42, 371-y, 0.49+n*0.04); g.box(x, y, 270-n*42, 2, 0.78)
    }
    // Keystone, fluted end piers, and four actually open entrance bays.
    g.shape([(323,130),(322,105),(340,90),(358,105),(357,130),(340,147)], 0.41)
    g.shape([(324,106),(340,93),(340,144),(325,129)], 0.74)
    g.shape([(340,93),(356,106),(355,129),(340,144)], 0.56)
    for direction in [-1.0,1.0] {
        for rib in 0..<3 {
            let dx = Double(24+rib*15), top = Double(132+rib*7)
            g.line([(340+direction*4,183),(340+direction*dx,top)],0.47,2)
            g.line([(340+direction*6,183),(340+direction*(dx+1.5),top)],0.71,1)
        }
    }
    for x in [217.0, 224, 231, 447, 454, 461] { g.box(x, 160, 2, 209, 0.65) }
    g.box(248, 272, 183, 99, 0.24)
    for bay in 0..<4 {
        let x = 278.0+Double(bay)*38.5
        g.box(x-2, 283, 37, 81, 0.60); g.box(x, 285, 33, 77, 0.15)
        g.box(x+2, 287, 29, 10, 0.49)
        g.shape([(x,301),(x+7,304),(x+7,357),(x,362)], 0.36)
        g.box(x-1, 362, 36, 2, 0.7)
    }
    g.box(198, 287, 43, 14, 0.78); stamp(g, p.tickets, center: (219.5,294), width: 35, maxHeight: 10)
    g.box(201, 304, 37, 28, 0.23); g.box(198, 332, 43, 3, 0.70)
    g.shape([(183,252),(498,252),(488,273),(195,273)], 0.26)
    g.box(183, 193, 315, 67, 0.24); g.box(188, 198, 305, 59, 0.85)
    let rail = SteppedRail().path(in: CGRect(x: 192, y: 201, width: 297, height: 53)).cgPath
    g.c.addPath(rail); g.c.setStrokeColor(gray: 0.37, alpha: 1); g.c.setLineWidth(1.5); g.c.strokePath()
    stamp(g, p.sign, center: (340,226), width: 213, maxHeight: 48)
    for x in [204.0, 455] { g.box(x, 224, 21, 2, 0.43); g.box(x+3, 230, 15, 1, 0.43) }
    for x in [270.0, 340, 410] {
        g.oval(x-6.5, 259, 13, 13, 0.40); g.oval(x-4.5, 261, 9, 9, 0.79); g.oval(x-3, 262.5, 6, 6, 0.98)
    }
    g.box(-32, 371, 722, 37, 0.49); g.box(-32, 405, 722, 3, 0.66)
    for i in -1...13 { let x = Double(i)*59; g.line([(x,371),(x-16,405)], 0.43, 0.8) }
    g.box(-32, 408, 722, 80, 0.32)
    for y in [416.0, 430] { g.box(-32, y, 722, 2, 0.64); g.box(-32, y+2, 722, 1, 0.20) }
    g.line([(-32,280),(692,280)], 0.32, 1)
}

enum Car {
    static let stopX = 20.0
    static let sill = 398.0
    static let entry = CGRect(x: 225, y: sill-51, width: 29, height: 51)
    static var exit: XY { (stopX + entry.midX, sill + 5) }
    static func x(at t: Double) -> Double {
        let approach = 1 - clamp((t-ReelCue.streetCut)/(ReelCue.carStop-ReelCue.streetCut))
        let departing = max(0, t-ReelCue.departure)
        // Ramp the speed for two beats, then cruise. The tail clears the entrance
        // on the closing chord rather than accelerating through the fade.
        let ramp = 2*ReelCue.beat, u = clamp(departing/ramp)
        let speed = (480-stopX)/(ReelCue.lastChord-ReelCue.departure-ramp/2)
        let distance = speed*(ramp*(u*u*u-0.5*u*u*u*u)+max(0,departing-ramp))
        return stopX - 302 * approach * approach + distance
    }
    static func open(at t: Double) -> Double {
        ease((t-ReelCue.carStop)/(ReelCue.doorsOpen-ReelCue.carStop)) *
            (1-ease((t-ReelCue.doorsClosing)/(ReelCue.departure-ReelCue.doorsClosing)))
    }
}

@MainActor func trolley(_ g: Ink, _ p: Plates, _ t: Double) {
    let x = Car.x(at: t), door = Car.entry, open = Car.open(at: t)
    let moving = t < ReelCue.carStop || t > ReelCue.departure
    g.c.translateBy(x: x, y: moving ? 0.28*sin(x/7) : 0)
    // Two trucks on the rail, raked trolley pole on the contact wire, clerestory roof.
    g.box(15,393,244,11,0.15)
    for axle in [37.0, 64, 198, 225] {
        g.oval(axle-9,399,18,18,0.13); g.oval(axle-5.5,402.5,11,11,0.39)
        let a = x/9
        g.line([(axle-4*cos(a),408-4*sin(a)),(axle+4*cos(a),408+4*sin(a))], 0.21, 1.6)
    }
    g.line([(164,320),(112,280)], 0.23, 2.3); g.line([(108,280),(116,280)], 0.14, 2)
    g.shape([(2,333),(9,326),(33,323),(244,323),(265,328),(274,333)], 0.27)
    g.box(35,318,198,6,0.39); g.box(31,316,207,3,0.2)
    for i in 0..<11 { g.box(44+Double(i)*17,320,12,2,0.61) }
    g.shape([(3,333),(271,333),(269,391),(263,398),(9,398),(4,392)], 0.30)
    g.box(0,332,274,4,0.19); g.box(5,337,262,3,0.75)
    for i in 0..<8 {
        let wx = 10+Double(i)*26.2
        g.box(wx,344,22.5,26,0.79); g.box(wx+1.5,345,19.5,23,0.51+0.035*Double(i%3))
        let vacated = ease((t-ReelCue.doorsOpen-Double((7-i)%5)*ReelCue.beat)/0.3)
        if vacated < 1 {
            g.layer {
                g.c.clip(to: CGRect(x: wx+1.5,y: 351.5,width: 19.5,height: 16.5))
                g.c.translateBy(x: 2*vacated, y: -8*vacated); g.c.setAlpha(0.78*(1-vacated))
                g.oval(wx+7,354,6,7,0.31); g.oval(wx+4,361,13,13,0.26)
                if i.isMultiple(of: 2) { g.box(wx+6,355,10,1.5,0.25) }
            }
        }
        g.box(wx+1.5,350,19.5,1.3,0.31)
        g.line([(wx+2,366),(wx+10,355)],0.63,1)
    }
    g.box(5,372,261,2,0.76); g.box(8,393,253,2,0.60)
    g.box(70,377,90,13,0.20)
    stamp(g, p.route, center: (115,383), width: 76, maxHeight: 10)
    stamp(g, p.fleet, center: (196,383), width: 12, maxHeight: 8)
    // The rail stops at the jambs. Both folding leaves, their panes and handles
    // close inside the same opening; the threshold never travels with the leaves.
    g.box(door.minX-1.5,door.minY-2,door.width+3,door.height+2,0.69)
    g.box(door.minX,door.minY,door.width,door.height,0.13)
    let leaf = (door.width/2) * (1-0.90*open)
    for lx in [door.minX, door.maxX-leaf] {
        g.box(lx,door.minY,leaf,door.height-1,0.43)
        g.box(lx+leaf*0.12,door.minY+2,leaf*0.76,20,0.61)
        g.box(lx+leaf*0.16,door.minY+27,leaf*0.68,19,0.37)
        if leaf > 8 { g.box(lx+leaf*0.75,door.minY+25,1,6,0.73) }
    }
    g.box(door.minX-2,Car.sill,door.width+4,2,0.76)
    g.box(door.minX-3,Car.sill+3,door.width+6,2,0.46)
    g.oval(260,375,6,6,0.80)
}

private struct Pedestrian {
    let number: Int, age: Double, u: Double, x: Double, feet: Double
    static func onStreet(_ t: Double) -> [Self] {
        // Small groups on the eighth notes; the last passenger clears the step before the doors close.
        (0..<30).compactMap { i in
            let age = t - (ReelCue.doorsOpen + Double(i/3)*ReelCue.beat/2 + Double(i%3)*0.069)
            let travel = 1.70 + Double(i%4)*0.12
            guard age >= 0 && age < travel else { return nil }
            let u = age/travel, v = 1-u, exit = Car.exit
            let endX = 294.5 + Double((i*3)%4)*38.5
            // A step down, around the nose of the car, then upstage to a door.
            let lane = Double(i%6)
            let x = v*v*v*exit.0 + 3*v*v*u*(exit.0+28+lane) + 3*v*u*u*(endX+23+lane*2) + u*u*u*endX
            let feet = v*v*v*exit.1 + 3*v*v*u*(418+lane) + 3*v*u*u*(373+lane) + u*u*u*361
            return Self(number: i, age: age, u: u, x: x, feet: feet)
        }.sorted { $0.feet < $1.feet }
    }

    func draw(_ g: Ink) {
        let i = number, stride = sin(age*(14+Double(i%3)) + Double(i)*1.7)
        // A standing adult is about 43 units in a 51-unit opening.
        let scale = (1.22+Double(i%4)*0.045) * (1-u*0.28)
        let ink = 0.12+Double(i%5)*0.038
        g.layer {
            g.c.setAlpha(ease(age/0.08)*ease((1-u)/0.085))
            g.c.translateBy(x: x, y: feet - abs(stride)*0.65); g.c.scaleBy(x: scale, y: scale)
            for side in [-1.0,1.0] {
                let shoe = side*(2+stride*4.4)
                g.line([(side*2,-11),(side*2.6+stride*side,-5.7),(shoe,-0.7)],ink-0.025,2.7)
                g.line([(shoe-0.5,-0.7),(shoe+1.5,-0.7)],0.13,1.8)
            }
            g.shape([(-3.6,-22.8),(3.3,-23.7),(i.isMultiple(of: 3) ? 7.3 : 4.7,-8.7),(-5,-9.1)],ink)
            g.line([(2.4,-22),(4.3+stride*2,-18),(4.2+stride*3,-13.1)],ink+0.07,2)
            g.oval(-3,-30,7,8,0.51)
            if i.isMultiple(of: 3) {
                g.oval(-3.9,-31,8.5,5.1,0.21); g.line([(-4,-27.5),(4.8,-27.5)],0.19,1.5)
            } else {
                g.box(-4.6,-29.2,10.7,1.7,0.15); g.box(-2.7,-32.4,6.7,3.6,0.20)
            }
            if i.isMultiple(of: 5) { g.box(2+stride*3,-13,6.7,5.2,0.31) }
        }
    }
}

// Deterministic print stock: make a small bank of grain plates once, not a new
// full-frame noise buffer on every exposure. Camera and actors still move at 60 fps.
private struct Stock {
    private let vignette = CGGradient(colorSpace: CGColorSpaceCreateDeviceGray(),
                                      colorComponents: [0,0, 0,0.035, 0,0.42],
                                      locations: [0,0.6,1], count: 3)!
    private var seed: UInt32 = 0xB1700
    private mutating func randomByte() -> UInt8 {
        seed = seed &* 1664525 &+ 1013904223
        return UInt8(truncatingIfNeeded: seed >> 24)
    }
    var grains: [CGImage] = []
    init() {
        for _ in 0..<8 {
            let side = 128
            let samples = (0..<(side*side)).map { _ in UInt8((Int(randomByte())+Int(randomByte()))/2) }
            let data = CGDataProvider(data: Data(samples) as CFData)!
            grains.append(CGImage(width: side, height: side, bitsPerComponent: 8, bitsPerPixel: 8, bytesPerRow: side,
                                  space: CGColorSpaceCreateDeviceGray(), bitmapInfo: [],
                                  provider: data, decode: nil, shouldInterpolate: false, intent: .defaultIntent)!)
        }
    }
    private func hash(_ n: Int) -> UInt32 {
        var v = UInt32(truncatingIfNeeded: n) &* 0x9e3779b9
        v ^= v >> 16; v = v &* 0x85ebca6b; return v ^ (v >> 13)
    }
    func expose(_ g: Ink, at t: Double) {
        let n = Int(t*24), h = hash(n)
        let offset = CGPoint(x: -Double(h & 63), y: -Double((h >> 8) & 63))
        g.layer {
            g.c.setAlpha(0.15); g.c.setBlendMode(.softLight); g.c.interpolationQuality = .none
            g.c.draw(grains[n % grains.count], in: CGRect(origin: offset, size: CGSize(width: 87,height: 87)), byTiling: true)
        }
        // Dust has a life of one or two print exposures. A gate hair and
        // emulsion tracks persist across frames, unlike the moving image.
        for i in 0..<8 {
            let a = hash((n/2)*47+i*181)
            let x = Double(a % 640), y = Double((a >> 10) % 480)
            let s = 0.7 + Double((a >> 23) & 7)/7
            g.layer {
                g.c.setAlpha(i.isMultiple(of: 2) ? 0.34 : 0.48)
                g.oval(x,y,s*1.6,s,i.isMultiple(of: 3) ? 0.9 : 0.12)
            }
        }
        for (start,end,x) in [(0.3,2.3,483.0),(3.2,4.65,69),(6.35,8.4,526),(9.15,10.65,109)] where t > start && t < end {
            let drift = 0.65*sin(t*4.3), top = Double(h % 17)
            g.layer {
                g.c.setAlpha(0.23*ease((t-start)/0.16)*ease((end-t)/0.19))
                g.line([(x+drift,top),(x+1.3+drift,176),(x-0.5+drift,337),(x+drift,476)],0.95,0.85)
                g.line([(x+2+drift,24),(x+2.6+drift,172)],0.10,0.55)
            }
        }
        if t > 4.4 && t < 7.2 {
            let a = ease((t-4.4)/0.12)*ease((7.2-t)/0.15)
            g.layer {
                let c = g.c; c.setAlpha(0.48*a); c.setLineWidth(1.1); c.setStrokeColor(gray: 0.12, alpha: 1)
                c.beginPath(); c.move(to: CGPoint(x: -2,y: 125))
                c.addQuadCurve(to: CGPoint(x: 13,y: 148), control: CGPoint(x: 25,y: 128))
                c.addQuadCurve(to: CGPoint(x: 9,y: 138.5+0.6*sin(t*4)), control: CGPoint(x: 7,y: 150)); c.strokePath()
            }
        }
        if n == Int(ReelCue.streetCut*24) { // One diagonal cement splice on the cut, not a whole-frame flash.
            g.layer {
                g.c.setAlpha(0.36)
                g.line([(-4,104),(644,89)],0.13,2.5); g.line([(-4,107),(644,92)],0.77,1.4)
            }
        }
        if (10.00..<10.16).contains(t) {
            g.layer {
                g.c.setStrokeColor(gray: 0.2, alpha: 0.67); g.c.setLineWidth(2.5)
                g.c.strokeEllipse(in: CGRect(x: 568,y: 36,width: 16,height: 13))
            }
        }
        g.layer {
            g.c.setAlpha(0.016 + 0.012*sin(2 * .pi * 0.8*t) + Double(h & 3)*0.0012)
            g.box(0,0,640,480,1)
        }
        g.c.drawRadialGradient(vignette,startCenter: CGPoint(x: 320,y: 235),startRadius: 0,
                               endCenter: CGPoint(x: 320,y: 235),endRadius: 423,options: [.drawsAfterEndLocation])
    }
}

@MainActor func render(_ output: FileHandle) throws {
    var pixels = Data(count: width*height*4)
    let stock = Stock(), plates = Plates()
    let numFrames = Int(ReelCue.end*Double(fps))
    for frame in 0..<numFrames {
        autoreleasepool {
            pixels.withUnsafeMutableBytes { bytes in
                let ctx = CGContext(data: bytes.baseAddress, width: width, height: height, bitsPerComponent: 8,
                                    bytesPerRow: width*4, space: CGColorSpace(name: CGColorSpace.sRGB)!,
                                    bitmapInfo: CGBitmapInfo.byteOrder32Little.rawValue | CGImageAlphaInfo.noneSkipFirst.rawValue)!
                ctx.translateBy(x: 0,y: CGFloat(height)); ctx.scaleBy(x: CGFloat(width)/640,y: -CGFloat(height)/480)
                let g = Ink(c: ctx), t = Double(frame)/Double(fps)
                g.box(0,0,640,480,0.045)
                ctx.addPath(CGPath(roundedRect: gate,cornerWidth: 12,cornerHeight: 12,transform: nil)); ctx.clip()
                ctx.setLineCap(.round); ctx.setLineJoin(.round)
                g.layer {
                    ctx.translateBy(x: 0.34*sin(2.1*t)+0.14*sin(4.7*t), y: 0.21*cos(3.2*t))
                    if t < ReelCue.streetCut { leader(g,plates,t) }
                    else {
                        let pan = -17*ease((t-ReelCue.streetCut)/(ReelCue.lastChord-ReelCue.streetCut))
                        g.layer {
                            ctx.translateBy(x: pan, y: 0)
                            streetscape(g,plates,t)
                            let people = Pedestrian.onStreet(t)
                            // The car crosses the sightline only once it has left the stop.
                            if t > ReelCue.departure { for person in people { person.draw(g) } }
                            g.layer { trolley(g,plates,t) }
                            if t <= ReelCue.departure { for person in people { person.draw(g) } }
                        }
                        if t >= ReelCue.departure + ReelCue.beat {
                            g.layer {
                                ctx.setAlpha(ease((t-ReelCue.departure-ReelCue.beat)/ReelCue.beat))
                                for x in [157.0,415] { g.line([(x,449),(x+68,449)],0.68); g.line([(x+10,453),(x+59,453)],0.48) }
                                stamp(g,plates.studio,center: (320,445),width: 183,maxHeight: 28)
                                stamp(g,plates.title,center: (320,465),width: 125,maxHeight: 17)
                            }
                        }
                    }
                }
                stock.expose(g,at: t)
                let fade = ReelCue.lastChord + ReelCue.beat/2
                if t > fade {
                    ctx.setFillColor(gray: 0.045,alpha: ease((t-fade)/(ReelCue.end-fade)))
                    ctx.fill(gate)
                }
            }
        }
        try output.write(contentsOf: pixels)
    }
}

@main enum MakePrint {
    @MainActor static func main() throws {
        if CommandLine.arguments.count == 2 {
            try renderPiano(to: URL(fileURLWithPath: CommandLine.arguments[1]))
        } else {
            try render(.standardOutput)
        }
    }
}
