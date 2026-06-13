import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))


@dataclass
class DetectionConfig:
    model_path: str = os.path.join(_HERE, "models", "playing_cards.pt")
    confidence_threshold: float = 0.60
    iou_threshold: float = 0.45
    # Screen region to capture: (left, top, width, height), None = full screen
    capture_region: Optional[Tuple[int, int, int, int]] = None
    # Zone y-axis split: community cards above this ratio, hole cards below
    community_zone_ratio: float = 0.55


@dataclass
class PokerConfig:
    num_opponents: int = 1
    monte_carlo_iterations: int = 5000
    hero_stack: int = 1000
    pot_size: int = 0
    call_amount: int = 0
    position: str = 'BTN'   # UTG/HJ/CO/BTN/SB/BB


@dataclass
class UIConfig:
    overlay_opacity: float = 0.88
    overlay_width: int = 320
    overlay_height: int = 420
    overlay_x: int = 20
    overlay_y: int = 20
    refresh_interval_ms: int = 150  # Detection loop interval (P2: 500→150ms)


@dataclass
class AppConfig:
    detection: DetectionConfig = field(default_factory=DetectionConfig)
    poker: PokerConfig = field(default_factory=PokerConfig)
    ui: UIConfig = field(default_factory=UIConfig)


CONFIG = AppConfig()
