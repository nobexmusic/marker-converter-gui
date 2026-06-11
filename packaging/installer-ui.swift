// First-run progress window for Marker Converter.
// Usage: installer-ui <progress-file> <cancel-file>
// Protocol: launcher/setup.sh append "NN|step text" lines to the progress file;
// at 100 the window closes itself. The Cancel button creates the cancel file,
// which launcher.sh handles (stops the installation).
import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    let progressPath: String
    let cancelPath: String
    var window: NSWindow!
    let bar = NSProgressIndicator()
    let label = NSTextField(labelWithString: "Preparing…")
    var timer: Timer?

    init(progressPath: String, cancelPath: String) {
        self.progressPath = progressPath
        self.cancelPath = cancelPath
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        let w = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 440, height: 150),
            styleMask: [.titled],
            backing: .buffered, defer: false)
        w.title = "Marker Converter"
        w.center()
        w.isReleasedWhenClosed = false

        let content = w.contentView!

        let title = NSTextField(labelWithString: "First launch — installing components")
        title.font = .boldSystemFont(ofSize: 13)
        title.frame = NSRect(x: 20, y: 110, width: 400, height: 18)
        content.addSubview(title)

        label.font = .systemFont(ofSize: 11.5)
        label.textColor = .secondaryLabelColor
        label.frame = NSRect(x: 20, y: 88, width: 400, height: 16)
        label.lineBreakMode = .byTruncatingTail
        content.addSubview(label)

        bar.isIndeterminate = false
        bar.minValue = 0
        bar.maxValue = 100
        bar.doubleValue = 0
        bar.style = .bar
        bar.frame = NSRect(x: 20, y: 58, width: 400, height: 20)
        content.addSubview(bar)

        let cancel = NSButton(title: "Cancel", target: self, action: #selector(cancelInstall))
        cancel.bezelStyle = .rounded
        cancel.frame = NSRect(x: 330, y: 14, width: 92, height: 32)
        content.addSubview(cancel)

        let hint = NSTextField(labelWithString: "Downloading ~5 GB — usually 5–15 minutes")
        hint.font = .systemFont(ofSize: 10.5)
        hint.textColor = .tertiaryLabelColor
        hint.frame = NSRect(x: 20, y: 22, width: 300, height: 14)
        content.addSubview(hint)

        window = w
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        w.makeKeyAndOrderFront(nil)

        timer = Timer.scheduledTimer(withTimeInterval: 0.3, repeats: true) { [weak self] _ in
            self?.poll()
        }
    }

    func poll() {
        guard let text = try? String(contentsOfFile: progressPath, encoding: .utf8),
              let line = text.split(separator: "\n").last else { return }
        let parts = line.split(separator: "|", maxSplits: 1)
        guard let pct = Double(parts[0]) else { return }
        bar.doubleValue = pct
        if parts.count > 1 {
            label.stringValue = String(parts[1])
        }
        if pct >= 100 {
            NSApp.terminate(nil)
        }
    }

    @objc func cancelInstall() {
        FileManager.default.createFile(atPath: cancelPath, contents: nil)
        label.stringValue = "Cancelling installation…"
    }
}

let args = CommandLine.arguments
guard args.count >= 3 else {
    FileHandle.standardError.write("usage: installer-ui <progress-file> <cancel-file>\n".data(using: .utf8)!)
    exit(2)
}
let app = NSApplication.shared
let delegate = AppDelegate(progressPath: args[1], cancelPath: args[2])
app.delegate = delegate
app.run()
