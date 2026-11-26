// Shared by the animator and the pianist. All cues are in the same 2/4 rag.
enum ReelCue {
    static let beat = 60.0 / 120
    static let streetCut = 6 * beat
    static let carStop = 10 * beat
    static let doorsOpen = 11 * beat
    static let doorsClosing = 17 * beat
    static let departure = 18 * beat
    static let title = 20 * beat
    static let lastChord = 22 * beat
    static let end = 24 * beat
}
