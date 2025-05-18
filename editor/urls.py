from django.contrib import admin
from django.urls import path
from .views import *
from django.views.generic import TemplateView

urlpatterns = [
    path('run_code/', run_Code, name='runcode'),
    path('', TemplateView.as_view(template_name='editor.html'), name='editor.html')
]
