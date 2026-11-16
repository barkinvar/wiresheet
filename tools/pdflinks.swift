// Add URL link annotations to a PDF with PDFKit (macOS, no dependencies).
//   swiftc -O -o pdflinks pdflinks.swift
//   ./pdflinks file.pdf links.json
// links.json: [{"url": "...", "x1": 0, "y1": 0, "x2": 0, "y2": 0}, ...]  in PDF points, origin bottom-left,
// optional "page" (0-based, default 0).
import Foundation
import PDFKit

let args = Array(CommandLine.arguments.dropFirst())
guard args.count == 2 else { print("usage: pdflinks file.pdf links.json"); exit(1) }
guard let doc = PDFDocument(url: URL(fileURLWithPath: args[0])) else { print("cannot open \(args[0])"); exit(1) }
guard let data = FileManager.default.contents(atPath: args[1]),
      let items = try? JSONSerialization.jsonObject(with: data) as? [[String: Any]] else { print("cannot read \(args[1])"); exit(1) }
var n = 0
for it in items {
    guard let url = it["url"] as? String, let u = URL(string: url),
          let x1 = it["x1"] as? Double, let y1 = it["y1"] as? Double,
          let x2 = it["x2"] as? Double, let y2 = it["y2"] as? Double else { continue }
    let pi = (it["page"] as? Int) ?? 0
    guard let page = doc.page(at: pi) else { continue }
    let a = PDFAnnotation(bounds: CGRect(x: x1, y: y1, width: x2 - x1, height: y2 - y1), forType: .link, withProperties: nil)
    a.url = u
    page.addAnnotation(a)
    n += 1
}
doc.write(to: URL(fileURLWithPath: args[0]))
print("\(args[0]): \(n) links")
