from django.urls import path
from .views import ReceptionPhotoView, FacturePDFView

app_name = "documents"
urlpatterns = [path("factures-fournisseurs/<int:pk>/", FacturePDFView.as_view(), name="facture_pdf"), path("photos/<int:pk>/", ReceptionPhotoView.as_view(), name="photo")]
