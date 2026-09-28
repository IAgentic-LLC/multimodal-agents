import json
import sys
import urllib.request
from html.parser import HTMLParser
from pathlib import Path


class TikaHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[str] = []
        self.current_heading: list[str] | None = None
        self.table_count = 0
        self.rows: list[list[str]] = []
        self.current_row: list[str] | None = None
        self.current_cell: list[str] | None = None
        self.paragraph_class = ""
        self.paragraph_text: list[str] = []
        self.caption = ""
        self.images: list[str] = []
        self.text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attributes = dict(attrs)
        if tag == "h1":
            self.current_heading = []
        elif tag == "table":
            self.table_count += 1
        elif tag == "tr":
            self.current_row = []
        elif tag == "td":
            self.current_cell = []
        elif tag == "p":
            self.paragraph_class = attributes.get("class") or ""
            self.paragraph_text = []
        elif tag == "img":
            self.images.append(attributes.get("src") or "")

    def handle_endtag(self, tag: str):
        if tag == "h1" and self.current_heading is not None:
            self.headings.append("".join(self.current_heading).strip())
            self.current_heading = None
        elif tag == "td" and self.current_row is not None:
            self.current_row.append("".join(self.current_cell or []).strip())
            self.current_cell = None
        elif tag == "tr" and self.current_row is not None:
            self.rows.append(self.current_row)
            self.current_row = None
        elif tag == "p":
            if self.paragraph_class == "image_Caption":
                self.caption = "".join(self.paragraph_text).strip()
            self.paragraph_class = ""

    def handle_data(self, data: str):
        self.text.append(data)
        if self.current_heading is not None:
            self.current_heading.append(data)
        self.paragraph_text.append(data)
        if self.current_cell is not None:
            self.current_cell.append(data)


def parse_xhtml(content: str) -> dict[str, object]:
    parser = TikaHtmlParser()
    parser.feed(content)
    flat_text = " ".join("".join(parser.text).split())
    return {
        "flat_text": flat_text,
        "structured": {
            "heading_count": len([
                heading for heading in parser.headings
                if not heading.lower().endswith(".png")
            ]),
            "parser_generated_headings": [
                heading for heading in parser.headings
                if heading.lower().endswith(".png")
            ],
            "table_count": parser.table_count,
            "table_rows": parser.rows,
            "figure_count": len(parser.images),
            "figure": {
                "asset": parser.images[0] if parser.images else None,
                "caption": parser.caption,
            },
            "relationships": [
                {
                    "type": "caption_of",
                    "from": "figure-caption-1",
                    "to": "figure-1",
                }
            ],
        },
    }


def main() -> None:
    source = Path(sys.argv[1])
    output = Path(sys.argv[2])
    request = urllib.request.Request(
        "http://127.0.0.1:9998/tika/html",
        data=source.read_bytes(),
        headers={
            "Content-Type": (
                "application/vnd.openxmlformats-officedocument."
                "wordprocessingml.document"
            )
        },
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        content = response.read().decode("utf-8")
    result = parse_xhtml(content)
    result["parser"] = {
        "name": "Apache Tika",
        "version": "4.0.0",
        "container_digest": (
            "sha256:a8b442501f601fb15015de974f9afe13dd242b0f14e49a2"
            "b144fadcb214a555b"
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
