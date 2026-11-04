"""One-time label file (D139): a zip with the label PDF, printer CSVs and a warning note.

The file is built in memory from the raw tokens of one generation and streamed once. Nothing in
it is stored, and nothing raw is logged.

- QR content: {PUBLIC_BASE_URL}/p/{token}, error correction level M.
- Under each QR: the token in groups of 4, then "Type the code at {host}/check".
- Every page footer names the base URL the labels were made with (D129).
- CSV columns: batch, carton_ref, token, verification_url. Units and cartons are separate files
  so a printer never mixes a carton label with a pack label.
"""

import csv
import io
import zipfile
from dataclasses import dataclass
from urllib.parse import urlsplit

import segno
from fpdf import FPDF

from app.services.identity import grouped

MIN_QR_MM = 15
DEFAULT_QR_MM = 20
ERROR_CORRECTION = "m"
QUIET_ZONE = 4  # modules of white around each code, as the QR standard asks
CSV_COLUMNS = ["batch", "carton_ref", "token", "verification_url"]

WARNING_NOTE = (
    "FOODLENS LABEL FILE - KEEP IT SECURE\n\n"
    "This file holds every raw code for these packs and cartons. FoodLens stores only a\n"
    "fingerprint of each code and cannot download this file again.\n\n"
    "- Send it only to your label printer.\n"
    "- Delete every copy after printing.\n"
    "- If the file is lost or leaked before release, void the unreleased packs in FoodLens\n"
    "  and generate new codes.\n\n"
    "DEMO DATA - NOT AN OFFICIAL REGULATOR SERVICE.\n"
)
SIZE_WARNING = (
    f"QR codes smaller than {MIN_QR_MM} mm may not scan reliably on every phone. "
    f"Use {MIN_QR_MM} mm or more."
)

PAGE_W, PAGE_H, MARGIN, FOOTER_H = 210.0, 297.0, 10.0, 8.0


@dataclass(frozen=True)
class Label:
    token: str
    carton_ref: str | None
    is_carton: bool = False


def verification_url(base_url: str, token: str) -> str:
    return f"{base_url.rstrip('/')}/p/{token}"


def make_qr(base_url: str, token: str) -> segno.QRCode:
    return segno.make(verification_url(base_url, token), error=ERROR_CORRECTION, boost_error=False)


def printed_lines(token: str) -> tuple[str, str]:
    """The grouped code on two lines so it fits under a small QR: 4 groups, then the rest."""
    text = grouped(token)
    return text[:19], text[20:]


def size_warning(qr_size_mm: float) -> str | None:
    return SIZE_WARNING if qr_size_mm < MIN_QR_MM else None


def _csv(batch_number: str, base_url: str, labels: list[Label]) -> bytes:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for label in labels:
        url = verification_url(base_url, label.token)
        writer.writerow([batch_number, label.carton_ref or "", label.token, url])
    return out.getvalue().encode("utf-8")


class _LabelPdf(FPDF):
    def __init__(self, footer_text: str) -> None:
        super().__init__(format="A4", unit="mm")
        self.footer_text = footer_text
        self.set_auto_page_break(False)
        # Uncompressed, so the printed text can be checked in tests; labels are small anyway.
        self.compress = False

    def footer(self) -> None:
        self.set_y(-MARGIN - 2)
        self.set_font("Helvetica", size=7)
        self.cell(0, 4, f"{self.footer_text} - page {self.page_no()}", align="C")


def _pdf(
    product_name: str, batch_number: str, base_url: str, qr_mm: float, labels: list[Label]
) -> bytes:
    host = urlsplit(base_url).netloc or base_url
    pdf = _LabelPdf(
        f"FoodLens demo labels - {product_name} - batch {batch_number} - made for {base_url}"
    )
    # qr_mm is the code itself; a 4-module quiet zone is added around it so cut labels scan.
    # Every code of one file has the same version (same URL length), so one size fits all.
    modules = make_qr(base_url, labels[0].token).symbol_size(border=0)[0] if labels else 25
    image_mm = qr_mm * (modules + 2 * QUIET_ZONE) / modules
    cell_w = max(image_mm + 4, 48.0)
    cell_h = image_mm + 20
    columns = max(1, int((PAGE_W - 2 * MARGIN) // cell_w))
    rows = max(1, int((PAGE_H - 2 * MARGIN - FOOTER_H) // cell_h))
    per_page = columns * rows

    for index, label in enumerate(labels):
        if index % per_page == 0:
            pdf.add_page()
        slot = index % per_page
        x = MARGIN + (slot % columns) * cell_w
        y = MARGIN + (slot // columns) * cell_h

        pdf.set_font("Helvetica", style="B", size=7)
        pdf.set_xy(x, y)
        heading = f"CARTON {label.carton_ref}" if label.is_carton else (label.carton_ref or "")
        pdf.cell(cell_w, 3, heading, align="C")

        image = io.BytesIO()
        make_qr(base_url, label.token).save(image, kind="png", scale=2, border=QUIET_ZONE)
        image.seek(0)
        pdf.image(image, x=x + (cell_w - image_mm) / 2, y=y + 3, w=image_mm, h=image_mm)

        pdf.set_font("Courier", style="B", size=8)
        for line, text in enumerate(printed_lines(label.token)):
            pdf.set_xy(x, y + 3 + image_mm + 4 * line)
            pdf.cell(cell_w, 4, text, align="C")
        pdf.set_xy(x, y + 11 + image_mm)
        pdf.set_font("Helvetica", size=6)
        pdf.cell(cell_w, 3, f"Type the code at {host}/check", align="C")
    return bytes(pdf.output())


def build_zip(
    *,
    product_name: str,
    batch_number: str,
    base_url: str,
    qr_size_mm: float,
    cartons: list[Label],
    units: list[Label],
) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("READ-ME-FIRST.txt", WARNING_NOTE)
        archive.writestr(
            "labels.pdf", _pdf(product_name, batch_number, base_url, qr_size_mm, cartons + units)
        )
        archive.writestr("units.csv", _csv(batch_number, base_url, units))
        if cartons:
            archive.writestr("cartons.csv", _csv(batch_number, base_url, cartons))
    return buffer.getvalue()
