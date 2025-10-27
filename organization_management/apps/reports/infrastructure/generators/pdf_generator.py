import io
from reportlab.pdfgen import canvas

class PDFGenerator:
    def generate(self, data, report):
        """
        Генерация отчета в формате PDF.
        """
        buffer = io.BytesIO()
        p = canvas.Canvas(buffer)

        # ... (логика генерации таблицы с данными)
        p.drawString(100, 100, "Hello world.")

        p.showPage()
        p.save()
        buffer.seek(0)
        return buffer
