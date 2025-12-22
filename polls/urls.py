from django.contrib import admin
from . import views
from django.urls import include, path

urlpatterns = [
    # path("index/", views.index, name="index"),
    path("chart/", views.apigee_dynamic_chart_view, name="apigee_dynamic_chart_view"),
]