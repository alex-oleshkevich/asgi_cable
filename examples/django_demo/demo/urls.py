from django.urls import path

from asgi_cable.channels import InMemoryBackend
from asgi_cable.contrib.django import websocket
from . import views

backend = InMemoryBackend()

urlpatterns = [
    path('', views.IndexView.as_view()),
    websocket('ws/', views.ws_handler),
    websocket('channels/', views.RoomSocket(backend)),
]
