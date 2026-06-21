import PhotosUI
import SwiftUI
import UIKit

struct ContentView: View {
    @StateObject var viewModel: AnalysisViewModel

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 20) {
                    photoSection
                    preferencesSection
                    analyzeButton

                    if let errorMessage = viewModel.errorMessage {
                        Text(errorMessage)
                            .font(.callout)
                            .foregroundStyle(.red)
                    }

                    if let analysis = viewModel.analysis {
                        ResultsView(analysis: analysis)
                    }
                }
                .padding(20)
            }
            .navigationTitle("HALO")
            .navigationBarTitleDisplayMode(.large)
            .task(id: viewModel.selectedItem) {
                await viewModel.loadSelectedPhoto()
            }
        }
    }

    private var photoSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            PhotosPicker(selection: $viewModel.selectedItem, matching: .images) {
                ZStack {
                    RoundedRectangle(cornerRadius: 8)
                        .fill(Color(.secondarySystemBackground))
                        .frame(height: 280)

                    if let image = viewModel.selectedImage {
                        Image(uiImage: image)
                            .resizable()
                            .scaledToFill()
                            .frame(height: 280)
                            .clipShape(RoundedRectangle(cornerRadius: 8))
                    } else {
                        VStack(spacing: 10) {
                            Image(systemName: "person.crop.rectangle")
                                .font(.system(size: 44))
                            Text("Choose Portrait")
                                .font(.headline)
                            Text("Front-facing, good light, hair fully visible.")
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
            }
            .buttonStyle(.plain)
        }
    }

    private var preferencesSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Style Notes")
                .font(.headline)

            TextField("Goal, e.g. more volume, softer shape", text: $viewModel.goal)
                .textFieldStyle(.roundedBorder)

            TextField("Heat routine", text: $viewModel.heat)
                .textFieldStyle(.roundedBorder)

            TextField("Aesthetic, e.g. polished, undone, editorial", text: $viewModel.aesthetic)
                .textFieldStyle(.roundedBorder)
        }
    }

    private var analyzeButton: some View {
        Button {
            Task { await viewModel.analyze() }
        } label: {
            HStack {
                if viewModel.isAnalyzing {
                    ProgressView()
                }
                Text(viewModel.isAnalyzing ? "Analyzing" : "Analyze Portrait")
                    .fontWeight(.semibold)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
        }
        .buttonStyle(.borderedProminent)
        .disabled(viewModel.isAnalyzing || viewModel.selectedImage == nil)
    }
}

struct ResultsView: View {
    let analysis: AnalysisResponse

    var body: some View {
        VStack(alignment: .leading, spacing: 18) {
            VStack(alignment: .leading, spacing: 6) {
                Text(analysis.styleIdentity)
                    .font(.title2.bold())
                Text("\(analysis.vibe) / \(analysis.hair.subhead)")
                    .foregroundStyle(.secondary)
            }

            infoCard("Hair", rows: [
                ("Type", analysis.hair.type),
                ("Density", analysis.hair.density),
                ("Face", analysis.hair.faceShape),
                ("Best Lengths", analysis.hair.bestLengths.joined(separator: ", "))
            ])

            infoCard("Color", rows: [
                ("Season", analysis.color.season),
                ("Undertone", analysis.color.undertone),
                ("Metals", analysis.color.metals.joined(separator: ", "))
            ])

            Text(analysis.hair.bottomLine)
                .font(.body)
                .padding()
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(Color(.secondarySystemBackground))
                .clipShape(RoundedRectangle(cornerRadius: 8))

            chips("Best Styles", analysis.hair.bestStyles)
            chips("Quick Tips", analysis.hair.quickTips)
            palette(analysis.color.bestColors)
        }
    }

    private func infoCard(_ title: String, rows: [(String, String)]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)

            ForEach(rows, id: \.0) { row in
                HStack(alignment: .top) {
                    Text(row.0)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(row.1)
                        .multilineTextAlignment(.trailing)
                }
                .font(.subheadline)
            }
        }
        .padding()
        .background(Color(.secondarySystemBackground))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    private func chips(_ title: String, _ values: [String]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(title)
                .font(.headline)
            FlowLayout(spacing: 8) {
                ForEach(values, id: \.self) { value in
                    Text(value)
                        .font(.subheadline)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 7)
                        .background(Color(.tertiarySystemBackground))
                        .clipShape(Capsule())
                }
            }
        }
    }

    private func palette(_ colors: [NamedColor]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Best Colors")
                .font(.headline)
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 92), spacing: 10)], spacing: 10) {
                ForEach(colors) { color in
                    VStack(alignment: .leading, spacing: 8) {
                        RoundedRectangle(cornerRadius: 6)
                            .fill(Color(hex: color.hex))
                            .frame(height: 44)
                        Text(color.name)
                            .font(.caption)
                    }
                }
            }
        }
    }
}

struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0
        var x: CGFloat = 0
        var y: CGFloat = 0
        var lineHeight: CGFloat = 0

        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > width, x > 0 {
                x = 0
                y += lineHeight + spacing
                lineHeight = 0
            }
            x += size.width + spacing
            lineHeight = max(lineHeight, size.height)
        }

        return CGSize(width: width, height: y + lineHeight)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX
        var y = bounds.minY
        var lineHeight: CGFloat = 0

        for view in subviews {
            let size = view.sizeThatFits(.unspecified)
            if x + size.width > bounds.maxX, x > bounds.minX {
                x = bounds.minX
                y += lineHeight + spacing
                lineHeight = 0
            }
            view.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(size))
            x += size.width + spacing
            lineHeight = max(lineHeight, size.height)
        }
    }
}

extension Color {
    init(hex: String) {
        let cleaned = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var value: UInt64 = 0
        Scanner(string: cleaned).scanHexInt64(&value)

        let red = Double((value >> 16) & 0xff) / 255
        let green = Double((value >> 8) & 0xff) / 255
        let blue = Double(value & 0xff) / 255

        self.init(red: red, green: green, blue: blue)
    }
}
