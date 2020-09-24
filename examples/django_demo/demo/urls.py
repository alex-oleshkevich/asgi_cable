from django.urls import path

from asgi_cable.contrib.django import websocket
from . import views

urlpatterns = [
    path('', views.IndexView.as_view()),
    websocket('ws/', views.ws_handler),
    websocket('channels/', views.RoomSocket()),
]
