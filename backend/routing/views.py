from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from .clients import mapbox
from .services import AnalyzeError, analyze_routes


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class PlaceSuggestView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        q = str(request.query_params.get("q") or "").strip()
        if len(q) < 2:
            return Response(
                {
                    "detail": "Type at least 2 characters to search for a place.",
                    "field": "q",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            results = mapbox.suggest_places(q, limit=5)
        except mapbox.MapboxError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response({"results": results})


class AnalyzeRoutesView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        try:
            result = analyze_routes(request.data if isinstance(request.data, dict) else {})
        except AnalyzeError as exc:
            body: dict = {"detail": str(exc)}
            if exc.field:
                body["field"] = exc.field
            return Response(body, status=exc.status)
        except Exception:  # pragma: no cover - unexpected
            return Response(
                {"detail": "Something went wrong. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(result)
