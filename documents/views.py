from PIL import Image, UnidentifiedImageError
from django.contrib.auth.mixins import LoginRequiredMixin, PermissionRequiredMixin
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from django.views import View
from .models import Document


class ReceptionPhotoView(LoginRequiredMixin, PermissionRequiredMixin, View):
    login_url = "login"
    permission_required = ("documents.view_document", "receptions.view_reception")

    def get(self, request, pk):
        document = get_object_or_404(Document, pk=pk, categorie="Photo du colis", reception__isnull=False)
        stream = None
        try:
            stream = document.fichier.open("rb")
            image = Image.open(stream)
            content_type = Image.MIME.get(image.format, "application/octet-stream")
            image.verify()
            stream.seek(0)
        except (OSError, ValueError, UnidentifiedImageError):
            if stream:
                stream.close()
            raise Http404("Photo indisponible")
        response = FileResponse(stream, content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response
