import datetime
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator


iin_validator = RegexValidator(
    regex=r'^\d{12}$',
    message="ИИН должен состоять ровно из 12 цифр."
)


def iin_kz_validator(value: str):
    """
    Валидирует ИИН РК:
    - ровно 12 цифр
    - корректная дата рождения (YYMMDD) + соответствие коду века/пола
    - корректная контрольная цифра (12-я)
    """
    if not isinstance(value, str):
        raise ValidationError("ИИН должен быть строкой из 12 цифр.")

    if len(value) != 12 or not value.isdigit():
        raise ValidationError("ИИН должен состоять ровно из 12 цифр.")

    digits = [int(ch) for ch in value]

    # 1) Дата рождения
    yy = int(value[0:2])
    mm = int(value[2:4])
    dd = int(value[4:6])
    century_code = digits[6]  # 7-й символ

    # Определим век по коду 7-й цифры:
    # 1,2 -> 1800-1899; 3,4 -> 1900-1999; 5,6 -> 2000-2099
    if century_code in (1, 2):
        year = 1800 + yy
    elif century_code in (3, 4):
        year = 1900 + yy
    elif century_code in (5, 6):
        year = 2000 + yy
    else:
        raise ValidationError("Некорректный код века/пола в ИИН (7-я цифра).")

    # Проверка корректности даты
    try:
        datetime.date(year, mm, dd)
    except ValueError:
        raise ValidationError("Некорректная дата рождения в ИИН.")

    # 2) Контрольная цифра (12-я)
    # Схема:
    #   r1 = (sum_{i=1..11} a_i * i) % 11
    #   если r1 == 10, то
    #       r2 = (sum_{i=1..11} a_i * w_i) % 11, где w=[3,4,5,6,7,8,9,10,11,1,2]
    #       если r2 == 10 -> ИИН недействителен
    #       иначе контрольная = r2
    #   иначе контрольная = r1
    w1 = list(range(1, 12))
    s1 = sum(digits[i] * w1[i] for i in range(11))
    r1 = s1 % 11

    if r1 == 10:
        w2 = [3, 4, 5, 6, 7, 8, 9, 10, 11, 1, 2]
        s2 = sum(digits[i] * w2[i] for i in range(11))
        r2 = s2 % 11
        if r2 == 10:
            raise ValidationError("ИИН недействителен (контрольная цифра).")
        checksum = r2
    else:
        checksum = r1

    if checksum != digits[11]:
        raise ValidationError("Неверная контрольная цифра ИИН.")
