from django import forms
from apps.catalog.models import Consumable, Copier, CopierCategory
from apps.blog.models import Post
from apps.core.models import SiteSettings


class ConsumableForm(forms.ModelForm):
    class Meta:
        model = Consumable
        fields = [
            "name", "short_description", "consumable_type", "brand", "part_number",
            "price", "price_business", "price_wholesale", "price_on_request",
            "in_stock", "yield_pages", "description", "status", "is_featured",
            "main_image", "main_image_alt",
        ]
        widgets = {
            "name":              forms.TextInput(attrs={"class": "da-input"}),
            "short_description": forms.TextInput(attrs={"class": "da-input"}),
            "consumable_type":   forms.Select(attrs={"class": "da-input"}),
            "brand":             forms.TextInput(attrs={"class": "da-input"}),
            "part_number":       forms.TextInput(attrs={"class": "da-input"}),
            "price":             forms.NumberInput(attrs={"class": "da-input", "step": "1"}),
            "price_business":    forms.NumberInput(attrs={"class": "da-input", "step": "1"}),
            "price_wholesale":   forms.NumberInput(attrs={"class": "da-input", "step": "1"}),
            "yield_pages":       forms.NumberInput(attrs={"class": "da-input"}),
            "description":       forms.Textarea(attrs={"class": "da-input", "rows": 3}),
            "status":            forms.Select(attrs={"class": "da-input"}),
            "main_image_alt":    forms.TextInput(attrs={"class": "da-input"}),
        }


class CopierForm(forms.ModelForm):
    class Meta:
        model = Copier
        fields = [
            "name", "brand", "model_number", "category",
            "short_description", "description",
            "toner_type", "paper_size", "speed_ppm", "monthly_duty_cycle",
            "has_scanner", "has_duplex", "has_network", "has_wifi",
            "available_for_rental", "available_for_sale",
            "monthly_rental_price", "sale_price",
            "pages_included_monthly", "extra_page_cost",
            "status", "is_featured", "main_image", "main_image_alt",
        ]
        widgets = {
            "name":                  forms.TextInput(attrs={"class": "da-input"}),
            "brand":                 forms.TextInput(attrs={"class": "da-input"}),
            "model_number":          forms.TextInput(attrs={"class": "da-input"}),
            "category":              forms.Select(attrs={"class": "da-input"}),
            "short_description":     forms.TextInput(attrs={"class": "da-input"}),
            "description":           forms.Textarea(attrs={"class": "da-input", "rows": 3}),
            "toner_type":            forms.Select(attrs={"class": "da-input"}),
            "paper_size":            forms.Select(attrs={"class": "da-input"}),
            "speed_ppm":             forms.NumberInput(attrs={"class": "da-input"}),
            "monthly_duty_cycle":    forms.NumberInput(attrs={"class": "da-input"}),
            "monthly_rental_price":  forms.NumberInput(attrs={"class": "da-input", "step": "1"}),
            "sale_price":            forms.NumberInput(attrs={"class": "da-input", "step": "1"}),
            "pages_included_monthly":forms.NumberInput(attrs={"class": "da-input"}),
            "extra_page_cost":       forms.NumberInput(attrs={"class": "da-input", "step": "0.01"}),
            "status":                forms.Select(attrs={"class": "da-input"}),
            "main_image_alt":        forms.TextInput(attrs={"class": "da-input"}),
        }


class BlogPostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["title", "excerpt", "content", "category", "status", "is_featured", "main_image"]
        widgets = {
            "title":    forms.TextInput(attrs={"class": "da-input"}),
            "excerpt":  forms.Textarea(attrs={"class": "da-input", "rows": 2}),
            "content":  forms.Textarea(attrs={"class": "da-input", "rows": 12}),
            "category": forms.Select(attrs={"class": "da-input"}),
            "status":   forms.Select(attrs={"class": "da-input"}),
        }


class SiteSettingsForm(forms.ModelForm):
    class Meta:
        model = SiteSettings
        fields = [
            "site_name", "tagline", "address", "city",
            "phone_primary", "phone_whatsapp", "email_contact",
            "instagram_url", "facebook_url",
        ]
        widgets = {f: forms.TextInput(attrs={"class": "da-input"})
                   for f in ["site_name", "tagline", "address", "city",
                              "phone_primary", "phone_whatsapp", "email_contact",
                              "instagram_url", "facebook_url"]}
