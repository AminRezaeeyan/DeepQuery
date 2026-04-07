from rest_framework.pagination import CursorPagination


class ChatCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-updated_at"


class MessageCursorPagination(CursorPagination):
    page_size = 30
    ordering = "-created_at"
