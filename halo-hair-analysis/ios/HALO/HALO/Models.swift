import Foundation

struct AnalysisResponse: Decodable {
    let styleIdentity: String
    let vibe: String
    let hair: HairProfile
    let color: ColorProfile
    let analysisId: String?

    enum CodingKeys: String, CodingKey {
        case styleIdentity = "style_identity"
        case vibe
        case hair
        case color
        case analysisId = "_analysis_id"
    }
}

struct HairProfile: Decodable {
    let type: String
    let density: String
    let color: String
    let faceShape: String
    let subhead: String
    let bestParts: [String]
    let bestLengths: [String]
    let bestStyles: [String]
    let goodOptions: [String]
    let stylesToAvoid: [String]
    let keyGoals: [String]
    let quickTips: [String]
    let bottomLine: String

    enum CodingKeys: String, CodingKey {
        case type
        case density
        case color
        case faceShape = "face_shape"
        case subhead
        case bestParts = "best_parts"
        case bestLengths = "best_lengths"
        case bestStyles = "best_styles"
        case goodOptions = "good_options"
        case stylesToAvoid = "styles_to_avoid"
        case keyGoals = "key_goals"
        case quickTips = "quick_tips"
        case bottomLine = "bottom_line"
    }
}

struct ColorProfile: Decodable {
    let season: String
    let seasonBlurb: String
    let undertone: String
    let bestColors: [NamedColor]
    let bestNeutrals: [NamedColor]
    let metals: [String]

    enum CodingKeys: String, CodingKey {
        case season
        case seasonBlurb = "season_blurb"
        case undertone
        case bestColors = "best_colors"
        case bestNeutrals = "best_neutrals"
        case metals
    }
}

struct NamedColor: Decodable, Identifiable {
    let name: String
    let hex: String

    var id: String { "\(name)-\(hex)" }
}

struct APIErrorResponse: Decodable {
    let error: String
}
