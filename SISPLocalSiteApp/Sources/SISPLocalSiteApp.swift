import AppKit
import SwiftUI

@main
struct SISPLocalSiteApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate

    var body: some Scene {
        WindowGroup("SISP Local Site") {
            ContentView(server: appDelegate.server)
        }
        .defaultSize(width: 430, height: 240)
        .windowResizability(.contentSize)
    }
}

@MainActor
final class AppDelegate: NSObject, NSApplicationDelegate {
    let server = SiteServer()

    func applicationDidFinishLaunching(_ notification: Notification) {
        server.start()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { true }

    func applicationWillTerminate(_ notification: Notification) {
        server.stop()
    }
}

@MainActor
final class SiteServer: ObservableObject {
    @Published private(set) var url: URL?
    @Published private(set) var status = "正在启动本地服务…"
    @Published private(set) var isRunning = false
    private var process: Process?
    private let port = 5173
    private let siteDirectory = FileManager.default.homeDirectoryForCurrentUser
        .appendingPathComponent("Library/Application Support/SISP/P1047_local_site")
        .path

    func start() {
        guard process == nil else { return }
        let task = Process()
        task.executableURL = URL(fileURLWithPath: "/usr/bin/python3")
        task.arguments = [
            "-m", "http.server", String(port), "--bind", "0.0.0.0",
            "--directory", siteDirectory
        ]
        task.standardOutput = FileHandle.nullDevice
        task.standardError = FileHandle.nullDevice
        task.terminationHandler = { [weak self] _ in
            Task { @MainActor in
                guard let self, self.process === task else { return }
                self.process = nil
                self.url = nil
                self.isRunning = false
                self.status = "本地服务已停止"
            }
        }
        do {
            try task.run()
            process = task
            isRunning = true
            let address = Self.lanAddress() ?? "localhost"
            let candidate = URL(string: "http://\(address):\(port)/person/P-1047/longitudinal-function/")!
            status = "服务运行中 · \(address):\(port)"
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { [weak self] in
                guard self?.process?.isRunning == true else { return }
                self?.url = candidate
            }
        } catch {
            status = "服务启动失败：\(error.localizedDescription)"
        }
    }

    func stop() {
        guard let process else { return }
        process.terminate()
        self.process = nil
        url = nil
        isRunning = false
        status = "本地服务已停止"
    }

    private static func lanAddress() -> String? {
        var interfaces: UnsafeMutablePointer<ifaddrs>?
        guard getifaddrs(&interfaces) == 0, let first = interfaces else { return nil }
        defer { freeifaddrs(interfaces) }
        for item in sequence(first: first, next: { $0.pointee.ifa_next }) {
            let flags = Int32(item.pointee.ifa_flags)
            guard flags & IFF_UP != 0, flags & IFF_LOOPBACK == 0,
                  item.pointee.ifa_addr.pointee.sa_family == UInt8(AF_INET) else { continue }
            var address = item.pointee.ifa_addr.pointee
            var host = [CChar](repeating: 0, count: Int(NI_MAXHOST))
            let result = getnameinfo(&address, socklen_t(address.sa_len), &host, socklen_t(host.count), nil, 0, NI_NUMERICHOST)
            if result == 0 {
                let value = String(cString: host)
                if value.hasPrefix("192.168.") || value.hasPrefix("10.") { return value }
            }
        }
        return nil
    }
}

struct ContentView: View {
    @ObservedObject var server: SiteServer

    var body: some View {
        VStack(alignment: .leading, spacing: 20) {
            Text("SISP 本地服务")
                .font(.title2.weight(.semibold))

            HStack(spacing: 9) {
                Circle()
                    .fill(server.isRunning ? .green : .secondary)
                    .frame(width: 9, height: 9)
                Text(server.status)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            HStack(spacing: 10) {
                Button("开始服务") { server.start() }
                    .disabled(server.isRunning)
                Button("停止服务") { server.stop() }
                    .disabled(!server.isRunning)
                Spacer()
                Button("在浏览器打开") {
                    if let url = server.url { NSWorkspace.shared.open(url) }
                }
                .disabled(server.url == nil)
            }

            Text("打开应用会自动启动；关闭应用会自动停止。")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(24)
    }
}
