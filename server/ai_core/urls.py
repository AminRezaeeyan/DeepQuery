from django.urls import path
from .views import ModelListAPIView


urlpatterns = [
    path('models/', ModelListAPIView.as_view(), name='models-list')
]