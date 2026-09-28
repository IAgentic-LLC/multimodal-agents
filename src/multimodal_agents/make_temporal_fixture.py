"""Create retained frames that differ only by object position."""

from pathlib import Path

from PIL import Image, ImageDraw


def main() -> None:
    destination = Path("runs/gate-7")
    destination.mkdir(parents=True, exist_ok=True)
    positions = ((64, "frame-001.png"), (448, "frame-002.png"))
    for left, name in positions:
        image = Image.new("RGB", (640, 360), "#f3f6fb")
        draw = ImageDraw.Draw(image)
        draw.rectangle((left, 108, left + 128, 252), fill="#e52b20")
        image.save(destination / name)


if __name__ == "__main__":
    main()
