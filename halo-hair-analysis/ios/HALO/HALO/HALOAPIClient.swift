import Foundation
import UIKit

struct HALOAPIClient {
    var baseURL: URL = AppConfig.apiBaseURL
    var session: URLSession = .shared

    func analyze(
        image: UIImage,
        goal: String,
        heat: String,
        aesthetic: String
    ) async throws -> AnalysisResponse {
        let endpoint = baseURL.appending(path: "analyze")
        var request = URLRequest(url: endpoint)
        request.httpMethod = "POST"

        let boundary = "Boundary-\(UUID().uuidString)"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        request.httpBody = try multipartBody(
            boundary: boundary,
            image: image,
            fields: [
                "goal": goal,
                "heat": heat,
                "aesthetic": aesthetic
            ]
        )

        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else {
            throw HALOAPIError.invalidResponse
        }

        guard (200..<300).contains(http.statusCode) else {
            let apiError = try? JSONDecoder().decode(APIErrorResponse.self, from: data)
            throw HALOAPIError.backend(apiError?.error ?? "Request failed with status \(http.statusCode)")
        }

        return try JSONDecoder().decode(AnalysisResponse.self, from: data)
    }

    private func multipartBody(
        boundary: String,
        image: UIImage,
        fields: [String: String]
    ) throws -> Data {
        guard let imageData = image.jpegData(compressionQuality: 0.9) else {
            throw HALOAPIError.imageEncodingFailed
        }

        var body = Data()

        for (name, value) in fields {
            body.appendString("--\(boundary)\r\n")
            body.appendString("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            body.appendString("\(value)\r\n")
        }

        body.appendString("--\(boundary)\r\n")
        body.appendString("Content-Disposition: form-data; name=\"image\"; filename=\"portrait.jpg\"\r\n")
        body.appendString("Content-Type: image/jpeg\r\n\r\n")
        body.append(imageData)
        body.appendString("\r\n")
        body.appendString("--\(boundary)--\r\n")

        return body
    }
}

enum HALOAPIError: LocalizedError {
    case imageEncodingFailed
    case invalidResponse
    case backend(String)

    var errorDescription: String? {
        switch self {
        case .imageEncodingFailed:
            return "Could not prepare that photo. Try another image."
        case .invalidResponse:
            return "HALO received an unexpected server response."
        case .backend(let message):
            return message
        }
    }
}

private extension Data {
    mutating func appendString(_ string: String) {
        append(Data(string.utf8))
    }
}
