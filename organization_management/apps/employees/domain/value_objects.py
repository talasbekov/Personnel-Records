from dataclasses import dataclass
from django.db.models.fields.files import ImageFieldFile

@dataclass(frozen=True)
class FullName:
    first_name: str
    last_name: str
    middle_name: str = ""

    def __str__(self):
        if self.middle_name:
            return f"{self.last_name} {self.first_name} {self.middle_name}"
        return f"{self.last_name} {self.first_name}"

@dataclass(frozen=True)
class Photo:
    image: ImageFieldFile

    def __str__(self):
        return str(self.image)
