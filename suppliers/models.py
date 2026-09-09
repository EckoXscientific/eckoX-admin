from django.db import models
from users.models import TrackedModel


class Fournisseur(TrackedModel):
    nom = models.CharField(max_length=255)

    def __str__(self):
        return self.nom
