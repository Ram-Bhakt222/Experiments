import SwiftUI

@main
struct HALOApp: App {
    var body: some Scene {
        WindowGroup {
            ContentView(viewModel: AnalysisViewModel(api: HALOAPIClient()))
        }
    }
}
