from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated
from .models import LLMProvider
from .serializers import ModelSerializer


class ModelListAPIView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ModelSerializer

    def get_queryset(self):
        return (
            LLMProvider.objects
            .filter(task_configs__task_type="chat")
            .prefetch_related("task_configs")
            .distinct()
        )