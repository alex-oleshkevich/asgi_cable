from django.urls import path

from users import views
from websocket.urls import websocket

urlpatterns = [
    path("", views.IndexView.as_view()),
    websocket("ws/", views.UserSocket.as_view()),
]
