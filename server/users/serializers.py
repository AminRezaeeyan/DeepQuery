from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.conf import settings
from google.oauth2 import id_token
from google.auth.transport import requests
from .models import User

class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        candidate = User(email=data["email"], first_name=data.get("first_name", ""), last_name=data.get("last_name", ""))
        try:
            validate_password(data["password"], user=candidate)
        except DjangoValidationError as e:
            raise serializers.ValidationError({"password": list(e.messages)})
        return data

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)
    
    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value
    

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')
        user = authenticate(username=email, password=password)

        if user is None:
            raise serializers.ValidationError("Wrong email or password")
        
        data['user'] = user
        return data
    

class GoogleAuthSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, data):
        token = data["token"]

        try:
            idinfo = id_token.verify_oauth2_token(
                token,
                requests.Request(),
                settings.GOOGLE_CLIENT_ID
            )
        except Exception:
            raise serializers.ValidationError("Invalid Google token.")

        # Only trust the address if Google has verified it; otherwise anyone
        # could sign into an existing account by claiming its email.
        if idinfo.get("email_verified") is not True:
            raise serializers.ValidationError("Your Google email address isn't verified.")

        email = idinfo["email"]

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "first_name": idinfo.get("given_name", ""),
                "last_name": idinfo.get("family_name", ""),
            },
        )

        data['user'] = user
        return data