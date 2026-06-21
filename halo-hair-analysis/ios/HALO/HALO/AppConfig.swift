import Foundation

enum AppConfig {
    static var apiBaseURL: URL {
        let configured = Bundle.main.object(forInfoDictionaryKey: "HALO_API_BASE_URL") as? String
        let value = configured?.trimmingCharacters(in: .whitespacesAndNewlines)

        if let value, !value.isEmpty, let url = URL(string: value) {
            return url
        }

        return URL(string: "http://127.0.0.1:8765")!
    }
}
