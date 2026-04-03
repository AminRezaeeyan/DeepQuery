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

        user = User.objects.first()

        assert user.email == valid_user_payload["email"]
        assert user.first_name == valid_user_payload["first_name"]
        assert user.last_name == valid_user_payload["last_name"]
        assert user.check_password(valid_user_payload["password"])


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
