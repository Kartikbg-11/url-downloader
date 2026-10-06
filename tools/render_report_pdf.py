from pathlib import Path
import sys
import pypdfium2 as pdfium

pdf_path = Path(sys.argv[1])
out_dir = Path(sys.argv[2])
out_dir.mkdir(parents=True, exist_ok=True)

pdf = pdfium.PdfDocument(pdf_path)
for index in range(len(pdf)):
    image = pdf[index].render(scale=1.35).to_pil()
    image.save(out_dir / f"page-{index + 1:03d}.png")
print(f"Rendered {len(pdf)} pages to {out_dir.resolve()}")
