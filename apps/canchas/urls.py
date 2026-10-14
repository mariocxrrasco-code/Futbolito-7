from django.urls import path
from rest_framework.response import Response
from rest_framework.views import APIView
from apps.canchas.models import Cancha, Complejo
from apps.canchas.serializers import CanchaSerializer, ComplejoSerializer

app_name = "canchas"


class ApiCanchasListView(APIView):
    def get(self, request):
        canchas = Cancha.objects.filter(activa=True).select_related("superficie", "complejo")
        return Response(CanchaSerializer(canchas, many=True).data)


urlpatterns = [
    path("api/canchas/", ApiCanchasListView.as_view(), name="api_canchas_list"),
]
