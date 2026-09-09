from django.urls import path
from .views import ReceptionPhotoView

app_name = "documents"
urlpatterns = [path("photos/<int:pk>/", ReceptionPhotoView.as_view(), name="photo")]
