import AppKit
import Foundation
import Vision

let args = CommandLine.arguments
var batch = false, imagePath: String?, level: VNRequestTextRecognitionLevel = .accurate
var langs = ["de-DE", "en-US"], correct = true, minHeight: Float?
var i = 1
while i < args.count {
    let a = args[i]
    if a == "--batch" { batch = true; i += 1 }
    else if a == "--level", i + 1 < args.count { level = (args[i + 1] == "fast") ? .fast : .accurate; i += 2 }
    else if a == "--lang", i + 1 < args.count { langs = args[i + 1].split(separator: ",").map(String.init); i += 2 }
    else if a == "--correct", i + 1 < args.count { correct = (args[i + 1] != "0"); i += 2 }
    else if a == "--min-height", i + 1 < args.count { if let v = Float(args[i + 1]), v >= 0 { minHeight = v }; i += 2 }
    else if imagePath == nil && !a.hasPrefix("-") { imagePath = a; i += 1 }
    else { i += 1 }
}

guard batch || imagePath != nil else {
    fputs("Usage: vision_ocr (<png> | --batch) [--level accurate|fast] [--lang de-DE,en-US] [--correct 1|0] [--min-height <float>]\n", stderr)
    exit(1)
}

func recognize(_ path: String) -> (text: String, ms: Double, error: String?) {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else {
        return ("", 0.0, "Failed to load image")
    }
    let req = VNRecognizeTextRequest()
    req.recognitionLevel = level
    req.recognitionLanguages = langs
    req.usesLanguageCorrection = correct
    if let mh = minHeight { req.minimumTextHeight = mh }
    let t0 = DispatchTime.now().uptimeNanoseconds
    do {
        try VNImageRequestHandler(cgImage: cg, options: [:]).perform([req])
    } catch {
        return ("", 0.0, error.localizedDescription)
    }
    let ms = Double(DispatchTime.now().uptimeNanoseconds - t0) / 1_000_000.0
    let text = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }.joined(separator: "\n")
    return (text, ms, nil)
}

if batch {
    while let line = readLine(strippingNewline: true) {
        let path = line.trimmingCharacters(in: .whitespacesAndNewlines)
        if path.isEmpty { continue }
        let res = recognize(path)
        let msNum = NSDecimalNumber(string: String(format: "%.1f", res.ms))
        var obj: [String: Any] = ["path": path, "text": res.text, "ms": msNum]
        if let err = res.error { obj["error"] = err }
        if let data = try? JSONSerialization.data(withJSONObject: obj, options: [.sortedKeys, .withoutEscapingSlashes]),
           let json = String(data: data, encoding: .utf8) {
            print(json)
            fflush(stdout)
        }
    }
} else if let path = imagePath {
    let res = recognize(path)
    if let err = res.error { fputs("\(err)\n", stderr); exit(1) }
    print(res.text)
}
