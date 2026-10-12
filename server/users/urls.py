from django.urls import path
from .views import GoogleAuthView, RegisterView, LoginView, ThrottledTokenRefreshView


urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path("google/", GoogleAuthView.as_view(), name="google-auth"),
    path("token/refresh/", ThrottledTokenRefreshView.as_view(), name="token-refresh"),
]