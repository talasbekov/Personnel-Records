from django.contrib import admin
from django import forms
from mptt.admin import MPTTModelAdmin
from mptt.exceptions import InvalidMove
from organization_management.apps.staff_unit.models import (
    Vacancy, StaffUnit
)


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_display = ['staff_unit', 'status', 'created_at', 'updated_at']
    list_filter = ['status', 'created_at']
    search_fields = ['staff_unit__position__name', 'requirements']


class StaffUnitAdminForm(forms.ModelForm):
    """Форма с валидацией для предотвращения циклических зависимостей в дереве"""

    class Meta:
        model = StaffUnit
        fields = '__all__'

    def clean_parent(self):
        parent = self.cleaned_data.get('parent')
        instance = self.instance

        # Если это новый объект, проверка не нужна
        if not instance.pk:
            return parent

        # ВАЖНО: Проверяем, не пытаемся ли мы создать циклическую зависимость
        if parent and instance.pk:
            # Случай 1: Родитель = сам узел
            if parent.pk == instance.pk:
                raise forms.ValidationError(
                    f'Узел не может быть родителем самого себя.'
                )

            # Случай 2: Родитель является потомком текущего узла
            descendants = instance.get_descendants(include_self=False)
            if parent in descendants:
                raise forms.ValidationError(
                    f'Невозможно сделать узел потомком своего потомка. '
                    f'ID={parent.pk} является потомком ID={instance.pk}.'
                )

        return parent

    def clean(self):
        """Дополнительная валидация всей формы"""
        cleaned_data = super().clean()

        # Дополнительная проверка для безопасности
        parent = cleaned_data.get('parent')
        if parent and self.instance.pk:
            # Проверяем что parent существует и загружен
            try:
                parent.refresh_from_db()
            except Exception as e:
                raise forms.ValidationError(f'Ошибка при проверке родителя: {e}')

        return cleaned_data


@admin.register(StaffUnit)
class StaffUnitAdmin(MPTTModelAdmin):
    form = StaffUnitAdminForm
    list_display = ['division', 'id', 'position', 'employee', 'index', 'parent']
    list_filter = ['division', 'level']
    search_fields = ['division__name', 'position__name', 'employee__last_name']
    # list_editable удален для избежания конфликтов с MPTT при массовом редактировании
    # Редактирование index доступно через форму редактирования отдельного объекта

    # ВАЖНО: Сортировка по MPTT полям для правильного отображения иерархии
    # tree_id - группирует деревья, lft - порядок узлов внутри дерева (left-right traversal)
    ordering = ['tree_id', 'lft', 'index']

    # MPTTModelAdmin автоматически добавляет отступы для визуализации иерархии
    mptt_level_indent = 20  # Отступ в пикселях для каждого уровня вложенности

    def save_model(self, request, obj, form, change):
        """Безопасное сохранение с обработкой MPTT ошибок"""
        from django.contrib import messages
        import logging
        logger = logging.getLogger(__name__)

        try:
            # Логируем попытку сохранения для отладки
            if change:
                old_obj = StaffUnit.objects.get(pk=obj.pk)
                if old_obj.parent_id != obj.parent_id:
                    logger.info(
                        f"Изменение parent для ID={obj.pk}: "
                        f"{old_obj.parent_id} → {obj.parent_id}"
                    )

            super().save_model(request, obj, form, change)

        except InvalidMove as e:
            # Детальное сообщение об ошибке
            error_msg = (
                f'Ошибка при перемещении узла ID={obj.pk}: {str(e)}. '
                f'Проверьте что новый родитель (ID={obj.parent_id if obj.parent_id else "None"}) '
                f'не является потомком текущего узла.'
            )
            logger.error(error_msg)
            messages.error(request, error_msg)

            # Откатываем изменения
            if change:
                obj.refresh_from_db()

            raise forms.ValidationError(error_msg)
