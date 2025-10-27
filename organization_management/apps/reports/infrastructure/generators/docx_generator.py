import io
from docx import Document
from docx.shared import Inches

class DOCXGenerator:
    def generate(self, data, report):
        """
        Генерация отчета в формате DOCX.
        """
        document = Document()
        document.add_heading(report.report_type, 0)

        p = document.add_paragraph('A plain paragraph having some ')
        p.add_run('bold').bold = True
        p.add_run(' and some ')
        p.add_run('italic').italic = True

        document.add_heading('Heading, level 1', level=1)
        document.add_paragraph('Intense quote', style='Intense Quote')

        document.add_paragraph(
            'first item in unordered list', style='List Bullet'
        )
        document.add_paragraph(
            'first item in ordered list', style='List Number'
        )

        # ... (логика генерации таблицы с данными)

        buffer = io.BytesIO()
        document.save(buffer)
        buffer.seek(0)
        return buffer
