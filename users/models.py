from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class TrackedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_created")
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="%(app_label)s_%(class)s_updated")

    class Meta:
        abstract = True

    def save(self, *args, user=None, **kwargs):
        # Callers supply the acting user; no request-global user state.
        if user is not None:
            if self._state.adding:
                self.created_by = user
            self.updated_by = user
        if not self._state.adding:
            original = type(self).objects.get(pk=self.pk)
            if self.created_by_id != original.created_by_id or self.created_at != original.created_at:
                raise ValidationError("L'auteur et la date de création ne peuvent pas être modifiés.")
        if kwargs.get("update_fields") is not None:
            kwargs["update_fields"] = set(kwargs["update_fields"]) | {"updated_at", "updated_by"}
        self.full_clean()
        return super().save(*args, **kwargs)
