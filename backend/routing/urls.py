from django.urls import path

from .views import AnalyzeRoutesView, HealthView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("routes/analyze/", AnalyzeRoutesView.as_view(), name="analyze-routes"),
]
