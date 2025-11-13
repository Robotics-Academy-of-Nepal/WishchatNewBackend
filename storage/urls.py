from django.urls import path
from .views import upload_file, delete_file, list_documents, get_document
from .youtube import upload_youtube_channel

urlpatterns = [
    path("upload/<int:chatbot_id>/", upload_file, name="upload_file"),
    path("delete/<int:chatbot_id>/", delete_file, name="delete_all_documents"),
    path(
        "delete/<int:chatbot_id>/<int:document_id>/",
        delete_file,
        name="delete_document",
    ),
    path("list/<int:chatbot_id>/", list_documents, name="list_documents"),
    path("get/<int:chatbot_id>/<int:document_id>/", get_document, name="get_document"),
    path(
        "upload-youtube-channel/<chatbot_id>/",
        upload_youtube_channel,
        name="upload_youtube_channel",
    ),
]
