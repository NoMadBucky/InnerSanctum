import SwiftUI

@main
struct BijouApp: App {
    @StateObject private var studio = Studio()
    @AppStorage("houseLights") private var lights = "Automatic"
    var body: some Scene {
        WindowGroup("Barry’s Bijou") {
            Theater()
                .environmentObject(studio)
                .preferredColorScheme(lights == "Working Hours" ? .light : lights == "After Hours" ? .dark : nil)
        }
        #if os(macOS)
        .defaultSize(width: 860, height: 780)
        #endif
    }
}
