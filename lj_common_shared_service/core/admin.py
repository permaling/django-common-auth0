from __future__ import unicode_literals

__author__ = 'David Baum'

import pandas as pd
from django.contrib import admin
from django.contrib.postgres import fields as django_fields

from import_export.tmp_storages import MediaStorage

from .models import LJCategoricalValue, LJCategoricalVariable, LJPhotoReport

from import_export.admin import ImportMixin, ImportExportModelAdmin
from multiupload.admin import MultiUploadAdmin

from django_json_widget.widgets import JSONEditorWidget
from nested_inline.admin import NestedModelAdmin


@admin.register(LJCategoricalVariable)
class LJCategoricalVariableAdmin(ImportExportModelAdmin):
    search_fields = ('name',)
    fields = ['name']
    list_display = ('id', 'name',)
    readonly_fields = []


@admin.register(LJCategoricalValue)
class LJCategoricalValueAdmin(ImportMixin, MultiUploadAdmin):
    tmp_storage_class = MediaStorage
    search_fields = ('value', 'categorical_variable__name',)
    fields = ['categorical_variable', 'value', 'index']
    list_display = ('id', 'categorical_variable', 'value', 'index',)
    list_filter = ('categorical_variable',)
    readonly_fields = []
    multiupload_list = True
    multiupload_form = False
    change_list_template = 'admin/core/categorical_value_change_list.html'
    multiupload_template = 'multiupload/upload.html'
    multiupload_minfilesize = 0
    multiupload_maxfilesize = 1024 * 1024 * 1024
    multiupload_acceptedformats = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel",
    )

    def process_uploaded_file(self, file, object, request):
        excel_data = pd.read_excel(file)
        excel_data = excel_data.fillna('')
        categorical_values_data = excel_data.to_dict(orient='record')

        categorical_variables_dict = dict()
        categorical_values = []

        for categorical_value_data in categorical_values_data:
            categorical_variable_name = categorical_value_data.get('categorical_variable')
            value = categorical_value_data.get('value')
            index = categorical_value_data.get('index')
            pk = categorical_value_data.get('id')

            categorical_variable = categorical_variables_dict.get(categorical_variable_name)
            if not categorical_variable:
                categorical_variable, created = LJCategoricalVariable.objects.get_or_create(
                    name=categorical_variable_name)

            categorical_value = None
            if pk:
                try:
                    categorical_value = LJCategoricalValue.objects.get(pk=pk)
                    categorical_value.categorical_variable = categorical_variable
                    categorical_value.value = value
                    categorical_value.index = index
                    categorical_value.pk = pk
                    categorical_value.save()
                except LJCategoricalValue.DoesNotExist:
                    pass
            if not categorical_value:
                categorical_value = LJCategoricalValue(
                    categorical_variable=categorical_variable,
                    value=value,
                    index=index
                )
                categorical_values.append(categorical_value)
        if categorical_values:
            LJCategoricalValue.objects.bulk_create(categorical_values)

        return {"id": -1}


@admin.register(LJPhotoReport)
class LJPhotoReportAdmin(NestedModelAdmin):
    list_per_page = 10
    search_fields = ('name',)
    fields = [
        "name", "device_type", "user", "status", "message", "output",
        'created_at', 'is_result_correct', 'uuid',
        'camera_angle_to_surface', 'camera_distance_to_surface',
    ]
    list_display = (
        "name", "device_type", "user", "status", 'is_result_correct', 'created_at', 'uuid',
        'camera_angle_to_surface', 'camera_distance_to_surface',
    )
    list_filter = ("created_at", "is_result_correct", "device_type",)
    readonly_fields = ['created_at', 'is_result_correct', 'status',
                       'message', 'output', 'uuid', ]
    formfield_overrides = {
        django_fields.JSONField: {'widget': JSONEditorWidget},
    }
