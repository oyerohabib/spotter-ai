from rest_framework.response import Response
from rest_framework.views import APIView


class HealthView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "ok"})


class AnalyzeRoutesView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        return Response(
            {
                "detail": "Analyze endpoint scaffolded; risk engine and integrations coming next.",
            },
            status=501,
        )
