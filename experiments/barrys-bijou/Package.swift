// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "BijouCore",
    platforms: [.macOS("27.0"), .iOS("27.0")],
    targets: [
        .target(name: "BijouCore", path: "Bijou/Core"),
        .testTarget(name: "BijouCoreTests", dependencies: ["BijouCore"], path: "Tests")
    ],
    swiftLanguageModes: [.v5]
)
