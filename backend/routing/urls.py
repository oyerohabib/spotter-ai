from django.urls import path

from .views import AnalyzeRoutesView, HealthView, PlaceSuggestView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("places/suggest/", PlaceSuggestView.as_view(), name="place-suggest"),
    path("routes/analyze/", AnalyzeRoutesView.as_view(), name="analyze-routes"),
]
