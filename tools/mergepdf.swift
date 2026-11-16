// Merge PDFs with PDFKit (macOS, no dependencies).
//   swiftc -O -o mergepdf mergepdf.swift
//   ./mergepdf out.pdf 01.pdf 02.pdf ...
import Foundation
import PDFKit

let args = Array(CommandLine.arguments.dropFirst())
guard args.count >= 2 else { print("usage: mergepdf out.pdf in1.pdf in2.pdf ..."); exit(1) }
let out = PDFDocument()
for p in args.dropFirst() {
    guard let d = PDFDocument(url: URL(fileURLWithPath: p)) else { print("skip \(p)"); continue }
    for i in 0..<d.pageCount { out.insert(d.page(at: i)!, at: out.pageCount) }
}
out.write(to: URL(fileURLWithPath: args[0]))
print("wrote \(args[0]) pages=\(out.pageCount)")
