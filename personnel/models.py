from django.db import models

class Employee(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    hire_date = models.DateField()
    job_title = models.CharField(max_length=100)
    department = models.CharField(max_length=100) # Consider ForeignKey to a Department model later
    # Add more fields as needed, e.g., salary, manager, etc.

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

# Example of a related model (optional for now)
# class Department(models.Model):
#     name = models.CharField(max_length=100, unique=True)
#     description = models.TextField(blank=True, null=True)
#
#     def __str__(self):
#         return self.name
