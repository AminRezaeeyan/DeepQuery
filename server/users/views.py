from rest_framework.views import APIView, Response, status
from rest_framework.permissions import AllowAny
from .serializers import LoginSerializer, RegisterSerializer

class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        return Response(
            data={
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "first_name": getattr(user, "first_name", ""),
                    "last_name": getattr(user, "last_name", ""),
                },
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        return Response(
            data={'message': 'Logged in successfully!'},
            status=status.HTTP_200_OK
        )
        
