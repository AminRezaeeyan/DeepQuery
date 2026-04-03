import pytest
from users.models import User


@pytest.mark.django_db
class TestCreateUser:

    def test_create_user_success(
        self,
        api_client,
        register_url,
        valid_user_payload
    ):
        
        old_user_count = User.objects.count()

        response = api_client.post(register_url, valid_user_payload, format="json")
        

        assert response.status_code == 201
        assert User.objects.count() - old_user_count == 1

        # Verify user
        user = User.objects.get(email=valid_user_payload["email"])
        assert user.first_name == valid_user_payload["first_name"]
        assert user.last_name == valid_user_payload["last_name"]
        assert user.check_password(valid_user_payload["password"])

        # Verify tokens
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert response.data["tokens"]["token_type"] == "Bearer"


    def test_create_user_with_short_password_fails(
        self,
        api_client,
        register_url,
        invalid_user_payload
    ):
        
        old_user_count = User.objects.count()

        response = api_client.post(register_url, invalid_user_payload, format="json")

        assert response.status_code == 400
        assert User.objects.count() == old_user_count


    def test_create_user_with_existing_email_fails(
        self,
        api_client,
        register_url,
        valid_user_payload
    ):
        api_client.post(register_url, valid_user_payload, format="json")
        old_user_count = User.objects.count()

        response = api_client.post(register_url, valid_user_payload, format="json")

        assert response.status_code == 400
        assert User.objects.count() == old_user_count


@pytest.mark.django_db
class TestLoginUser:

    def test_login_success(
        self,
        api_client,
        login_url,
        valid_user_payload
    ):
        User.objects.create_user(**valid_user_payload)

        response = api_client.post(
            login_url,
            {
                "email": valid_user_payload["email"],
                "password": valid_user_payload["password"],
            },
            format="json"
        )

        assert response.status_code == 200
        assert response.data["message"] == "Logged in successfully!"
        assert "tokens" in response.data
        assert "access" in response.data["tokens"]
        assert "refresh" in response.data["tokens"]
        assert response.data["tokens"]["token_type"] == "Bearer"



    def test_login_wrong_password(
        self,
        api_client,
        login_url,
        valid_user_payload
    ):
        User.objects.create_user(**valid_user_payload)

        response = api_client.post(
            login_url,
            {
                "email": valid_user_payload["email"],
                "password": "wrongpassword",
            },
            format="json"
        )

        assert response.status_code == 400


    def test_login_user_not_found(
        self,
        api_client,
        login_url
    ):
        response = api_client.post(
            login_url,
            {
                "email": "unknown@test.com",
                "password": "password123",
            },
            format="json"
        )

        assert response.status_code == 400
