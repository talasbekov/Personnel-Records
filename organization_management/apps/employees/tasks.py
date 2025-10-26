from celery import shared_task

@shared_task
def copy_statuses_task():
    # TODO: Implement this task
    pass

@shared_task
def check_status_updates_task():
    # TODO: Implement this task
    pass

@shared_task
def reset_default_statuses_task():
    # TODO: Implement this task
    pass

@shared_task
def export_employees_to_csv_task(employee_ids):
    # TODO: Implement this task
    pass

@shared_task
def export_employees_to_xlsx_task(employee_ids):
    # TODO: Implement this task
    pass
