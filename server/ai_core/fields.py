import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.db import models

PREFIX = "enc:"


def _fernet():
    key = settings.FIELD_ENCRYPTION_KEY
    if not key:
        # Fall back to a key derived from SECRET_KEY so the app runs without
        # extra setup. Changing SECRET_KEY then makes stored secrets unreadable.
        key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


class EncryptedTextField(models.TextField):
    """Stores the value encrypted with Fernet; reads it back as plain text."""

    def from_db_value(self, value, expression, connection):
        if not value or not value.startswith(PREFIX):
            return value  # empty, or written before encryption was added
        try:
            return _fernet().decrypt(value[len(PREFIX):].encode()).decode()
        except InvalidToken:
            raise ValueError("Can't decrypt a stored secret: FIELD_ENCRYPTION_KEY (or SECRET_KEY) changed.")

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if not value or value.startswith(PREFIX):
            return value
        return PREFIX + _fernet().encrypt(value.encode()).decode()
