import io
import xlsxwriter

class XLSXGenerator:
    def generate(self, data, report):
        """
        Генерация отчета в формате XLSX.
        """
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet()

        # ... (логика генерации таблицы с данными)
        worksheet.write('A1', 'Hello..')
        worksheet.write('B1', '...world')

        workbook.close()
        output.seek(0)
        return output
