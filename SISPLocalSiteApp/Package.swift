// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SISPLocalSite",
    platforms: [.macOS(.v15)],
    products: [.executable(name: "SISPLocalSite", targets: ["SISPLocalSite"])],
    targets: [.executableTarget(name: "SISPLocalSite", path: "Sources")]
)
