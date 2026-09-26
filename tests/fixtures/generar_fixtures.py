"""Genera los fixtures de una página de tests/test_text_layer.py.

Son sintéticos: rótulos contables genéricos, sin cifras ni datos de ningún club.
- pagina_texto.pdf: una página con capa de texto, como un PDF generado por software.
- pagina_imagen.pdf: la misma página convertida en imagen, como un escaneo, sin capa de texto.

Uso: .venv/bin/python tests/fixtures/generar_fixtures.py
"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
LINES = [
    "Fixture sintetico para tests: rotulos genericos, sin cifras de ningun club.",
    "Consolidated profit and loss account",
    "Turnover",
    "Operating expenses",
    "Staff costs",
    "Wages and salaries",
    "Social security costs",
    "Amortisation of player registrations",
    "Profit on disposal of player registrations",
    "Interest payable and similar charges",
    "Consolidated balance sheet",
    "Cash at bank and in hand",
    "Borrowings",
]


def text_pdf(lines: list[str]) -> bytes:
    """PDF mínimo de una página A4 con el texto en Helvetica."""
    text = " T* ".join(f"({line}) Tj" for line in lines)
    stream = f"BT /F1 11 Tf 14 TL 50 790 Td {text} ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length %d >>\nstream\n%s\nendstream" % (len(stream), stream),
    ]
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n%s\nendobj\n" % (number, body)
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (
        len(objects) + 1,
        xref,
    )
    return bytes(out)


def image_pdf(lines: list[str], path: Path) -> None:
    """La misma página dibujada como imagen: el texto son píxeles, no caracteres."""
    image = Image.new("L", (595, 842), 255)
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=11)
    for row, line in enumerate(lines):
        draw.text((50, 52 + 14 * row), line, fill=0, font=font)
    image.save(path, "PDF", resolution=72)


if __name__ == "__main__":
    (HERE / "pagina_texto.pdf").write_bytes(text_pdf(LINES))
    image_pdf(LINES, HERE / "pagina_imagen.pdf")
