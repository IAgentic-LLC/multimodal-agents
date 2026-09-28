from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def make_chart(output: Path) -> None:
    image = Image.new("RGB", (640, 360), "#f6f8fc")
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=20)
    small = ImageFont.load_default(size=16)
    draw.text((34, 24), "Service error rates", fill="#14203a", font=font)
    baseline = 300
    draw.line((70, baseline, 600, baseline), fill="#8996ac", width=3)
    values = [("Vision API", 0.8, "#315dcc"), ("Search API", 3.4, "#b44750")]
    for index, (label, value, color) in enumerate(values):
        left = 150 + index * 250
        height = round(value / 4 * 210)
        draw.rectangle(
            (left, baseline - height, left + 90, baseline),
            fill=color,
        )
        draw.text((left + 20, baseline - height + 12), f"{value}%", fill="white", font=small)
        draw.text((left - 5, baseline + 14), label, fill="#14203a", font=small)
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


if __name__ == "__main__":
    make_chart(Path("fixtures/document-error-rates.png"))
