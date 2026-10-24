from django.urls import path

from .views import HealthView, PlaceSuggestView, PlanRoutesView, ScoreRoutesView

urlpatterns = [
    path("health/", HealthView.as_view(), name="health"),
    path("places/suggest/", PlaceSuggestView.as_view(), name="place-suggest"),
    path("routes/plan/", PlanRoutesView.as_view(), name="plan-routes"),
    path("routes/score/", ScoreRoutesView.as_view(), name="score-routes"),
]
