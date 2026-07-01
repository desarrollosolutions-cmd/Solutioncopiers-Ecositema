"""Formularios del módulo Leads."""
from __future__ import annotations

import re
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

from .models import Lead, Quote


def validate_colombian_phone(value):
    cleaned = re.sub(r"[^\d+]", "", value)
    if not re.match(r"^(\+57)?[3]\d{9}$|^\+57[1-8]\d{7,9}$", cleaned):
        raise ValidationError(
            _("Ingresa un teléfono colombiano válido (celular o fijo).")
        )


class InterestAreaForm(forms.Form):
    interest_area = forms.ChoiceField(
        label=_("¿Qué necesitas?"),
        choices=Quote.InterestArea.choices,
        widget=forms.RadioSelect,
    )


class RentalDetailsForm(forms.Form):
    copier_id = forms.IntegerField(required=False)
    quantity = forms.IntegerField(min_value=1, max_value=50, initial=1)
    monthly_pages = forms.IntegerField(min_value=100, max_value=500000, initial=2000)
    needs_color = forms.BooleanField(required=False)


class CablingDetailsForm(forms.Form):
    logical_points = forms.IntegerField(min_value=0, max_value=500, initial=10)
    electrical_points = forms.IntegerField(min_value=0, max_value=500, initial=0)
    office_size_m2 = forms.IntegerField(min_value=10, required=False)
    needs_certification = forms.BooleanField(required=False)


class SoftwareDetailsForm(forms.Form):
    COMPLEXITY_CHOICES = [
        ("low", _("Básico")),
        ("medium", _("Medio")),
        ("high", _("Alto")),
        ("enterprise", _("Enterprise")),
    ]
    complexity = forms.ChoiceField(choices=COMPLEXITY_CHOICES, widget=forms.RadioSelect)
    project_description = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 5}), max_length=2000,
    )
    desired_timeline = forms.CharField(max_length=100, required=False)


class ContactDetailsForm(forms.ModelForm):
    gdpr_consent = forms.BooleanField(required=True)

    class Meta:
        model = Lead
        fields = [
            "full_name", "email", "phone", "company_name",
            "company_size", "job_title", "city", "gdpr_consent",
        ]

    def clean_phone(self):
        phone = self.cleaned_data["phone"]
        validate_colombian_phone(phone)
        return phone


class ContactForm(forms.Form):
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=30, validators=[validate_colombian_phone])
    company_name = forms.CharField(max_length=200, required=False)
    subject = forms.CharField(max_length=200)
    message = forms.CharField(widget=forms.Textarea(attrs={"rows": 5}), max_length=2000)
    gdpr_consent = forms.BooleanField(required=True)
