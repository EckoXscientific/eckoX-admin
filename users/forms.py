from django import forms
from django.contrib.auth.forms import AuthenticationForm


class ConnexionForm(AuthenticationForm):
    username = forms.CharField(label="Nom d’utilisateur", widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}), error_messages={"required": "Indiquez votre nom d’utilisateur."})
    password = forms.CharField(label="Mot de passe", strip=False, widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}), error_messages={"required": "Indiquez votre mot de passe."})
    error_messages = {
        "invalid_login": "Le nom d’utilisateur ou le mot de passe est incorrect.",
        "inactive": "Ce compte est désactivé.",
    }
