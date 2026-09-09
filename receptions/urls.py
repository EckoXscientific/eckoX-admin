from django.urls import path
from .views import ReceptionListView, ReceptionDetailView, ReceptionCreateView, ReceptionUpdateView

app_name = "receptions"
urlpatterns = [
    path("", ReceptionListView.as_view(), name="list"),
    path("nouvelle/", ReceptionCreateView.as_view(), name="create"),
    path("<int:pk>/", ReceptionDetailView.as_view(), name="detail"),
    path("<int:pk>/modifier/", ReceptionUpdateView.as_view(), name="update"),
]
