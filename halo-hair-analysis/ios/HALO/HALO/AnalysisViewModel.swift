import PhotosUI
import SwiftUI
import UIKit

@MainActor
final class AnalysisViewModel: ObservableObject {
    @Published var selectedItem: PhotosPickerItem?
    @Published var selectedImage: UIImage?
    @Published var goal = ""
    @Published var heat = "Low heat, mostly air dry"
    @Published var aesthetic = ""
    @Published var analysis: AnalysisResponse?
    @Published var isAnalyzing = false
    @Published var errorMessage: String?

    private let api: HALOAPIClient

    init(api: HALOAPIClient) {
        self.api = api
    }

    func loadSelectedPhoto() async {
        guard let selectedItem else { return }

        do {
            guard let data = try await selectedItem.loadTransferable(type: Data.self),
                  let image = UIImage(data: data) else {
                errorMessage = "That photo could not be opened."
                return
            }

            selectedImage = image
            analysis = nil
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    func analyze() async {
        guard let selectedImage else {
            errorMessage = "Choose a portrait first."
            return
        }

        isAnalyzing = true
        errorMessage = nil

        do {
            analysis = try await api.analyze(
                image: selectedImage,
                goal: goal,
                heat: heat,
                aesthetic: aesthetic
            )
        } catch {
            errorMessage = error.localizedDescription
        }

        isAnalyzing = false
    }
}
