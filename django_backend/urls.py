from django.urls import path
from . import views

urlpatterns = [
    path('create-event/', views.create_event, name='create-event'),
    # You can add more paths here later, like:
    # path('list-events/', views.list_events, name='list-events'),
]