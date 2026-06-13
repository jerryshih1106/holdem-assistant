# Model Weights

Place your YOLO model file here as `playing_cards.pt`.

## Quick start

```bash
python download_model.py
```

## Manual download (Roboflow)

1. Install: `pip install roboflow`
2. Set API key: `$env:ROBOFLOW_API_KEY = "your_key"`
3. Run: `python training/download_roboflow.py`
4. Train: `python training/train.py --data training/dataset/data.yaml`

## Expected class names

The model should output 52 classes in format `{rank}{suit}`:
- Ranks: `2 3 4 5 6 7 8 9 10 J Q K A`
- Suits: `c d h s`
- Examples: `Ah`, `Kd`, `10s`, `2c`
