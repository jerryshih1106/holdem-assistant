"""Map YOLO class labels to treys-compatible card strings and card zone assignment."""

from typing import List, Optional, Tuple

# Roboflow "Playing Cards" dataset class names → treys notation
# YOLO label format: "Ah", "2c", "10d", etc.
# treys format:      "Ah", "2c", "Td", etc.  (10 → T)

_RANK_MAP = {
    "2": "2", "3": "3", "4": "4", "5": "5", "6": "6",
    "7": "7", "8": "8", "9": "9", "10": "T",
    "J": "J", "Q": "Q", "K": "K", "A": "A",
}

_SUIT_MAP = {
    "c": "c", "d": "d", "h": "h", "s": "s",
    "C": "c", "D": "d", "H": "h", "S": "s",
}


def label_to_treys(label: str) -> Optional[str]:
    """Convert a YOLO class label to a treys card string, e.g. '10h' → 'Th'."""
    label = label.strip()
    if len(label) < 2:
        return None
    suit = label[-1]
    rank = label[:-1]
    r = _RANK_MAP.get(rank)
    s = _SUIT_MAP.get(suit)
    if r is None or s is None:
        return None
    return r + s


# --- Zone classification ---

class Detection:
    """Single YOLO detection result."""
    def __init__(self, label: str, confidence: float, bbox: Tuple[float, float, float, float]):
        """
        Args:
            label: YOLO class name
            confidence: detection score 0-1
            bbox: (x_center, y_center, width, height) normalized 0-1
        """
        self.label = label
        self.confidence = confidence
        self.bbox = bbox
        self.card = label_to_treys(label)

    @property
    def y_center(self) -> float:
        return self.bbox[1]

    @property
    def x_center(self) -> float:
        return self.bbox[0]


def classify_zones(
    detections: List[Detection],
    community_ratio: float = 0.55,
    frame_height: Optional[int] = None,
) -> Tuple[List[str], List[str]]:
    """
    Split detections into community cards (top area) and hole cards (bottom area).

    Args:
        detections: all card detections
        community_ratio: y-axis threshold (normalized). Cards above → community.
        frame_height: actual frame height in px (only used for absolute coords)

    Returns:
        (hole_cards, community_cards) as treys card strings
    """
    hole, community = [], []
    for det in detections:
        if det.card is None:
            continue
        if det.y_center < community_ratio:
            community.append(det.card)
        else:
            hole.append(det.card)

    # Deduplicate (keep highest confidence if duplicates exist)
    hole = _deduplicate(hole)
    community = _deduplicate(community)

    # Hole cards: max 2; community cards: max 5
    hole = hole[:2]
    community = community[:5]

    return hole, community


def _deduplicate(cards: List[str]) -> List[str]:
    seen = set()
    result = []
    for c in cards:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result
