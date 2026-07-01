"""Mixins reutilizables para Class-Based Views."""
from __future__ import annotations

import json
from typing import Any

from django.conf import settings
from django.urls import reverse
from django.utils.safestring import mark_safe


def _safe_json_script(data: Any) -> str:
    """
    Serializa a JSON seguro para embeber en <script type="application/ld+json">.
    Escapa </  para prevenir que una cadena </script> cierre prematuramente la etiqueta.
    """
    serialized = json.dumps(data, ensure_ascii=False, indent=None)
    return serialized.replace("</", "<\\/").replace("<!--", "<\\!--")


class SEOContextMixin:
    """Inyecta metadatos SEO al contexto del template."""

    meta_title_default: str = ""
    meta_description_default: str = ""
    meta_keywords_default: str = ""
    og_image_default: str = ""
    schema_type_default: str = "WebPage"
    noindex_default: bool = False

    def get_seo_object(self):
        return getattr(self, "object", None)

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        seo_obj = self.get_seo_object()
        request = self.request

        if seo_obj and hasattr(seo_obj, "get_meta_title"):
            meta_title = seo_obj.get_meta_title()
            meta_description = seo_obj.get_meta_description()
            meta_keywords = getattr(seo_obj, "meta_keywords", "") or self.meta_keywords_default
            schema_type = getattr(seo_obj, "schema_type", self.schema_type_default)
            noindex = getattr(seo_obj, "noindex", self.noindex_default)
            canonical = seo_obj.get_canonical_url(request=request)
        else:
            meta_title = self.meta_title_default or "Solution Copiers"
            meta_description = self.meta_description_default
            meta_keywords = self.meta_keywords_default
            schema_type = self.schema_type_default
            noindex = self.noindex_default
            canonical = request.build_absolute_uri(request.path)

        og_image_url = ""
        if seo_obj and getattr(seo_obj, "og_image", None):
            try:
                og_image_url = request.build_absolute_uri(seo_obj.og_image.url)
            except (ValueError, AttributeError):
                og_image_url = ""
        elif self.og_image_default:
            og_image_url = self.og_image_default

        context["seo"] = {
            "meta_title": meta_title,
            "meta_description": meta_description,
            "meta_keywords": meta_keywords,
            "canonical_url": canonical,
            "og_image": og_image_url,
            "og_type": self._get_og_type(schema_type),
            "schema_type": schema_type,
            "noindex": noindex,
            "site_name": "Solution Copiers",
        }
        return context

    @staticmethod
    def _get_og_type(schema_type: str) -> str:
        mapping = {
            "Product": "product",
            "Article": "article",
            "Service": "website",
            "Organization": "website",
            "WebPage": "website",
            "FAQPage": "website",
        }
        return mapping.get(schema_type, "website")


class JsonLDMixin:
    """Genera el JSON-LD structured data."""

    def get_jsonld_data(self, context: dict) -> dict:
        seo = context.get("seo", {})
        schema_type = seo.get("schema_type", "WebPage")

        base = {
            "@context": "https://schema.org",
            "@type": schema_type,
            "name": seo.get("meta_title"),
            "description": seo.get("meta_description"),
            "url": seo.get("canonical_url"),
        }

        if seo.get("og_image"):
            base["image"] = seo["og_image"]

        custom = self.extra_jsonld_data(context)
        if custom:
            base.update(custom)

        return base

    def extra_jsonld_data(self, context: dict) -> dict:
        return {}

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        jsonld = self.get_jsonld_data(context)
        if jsonld:
            context["jsonld_script"] = mark_safe(_safe_json_script(jsonld))
        return context


class BreadcrumbMixin:
    """Genera breadcrumbs con schema.org BreadcrumbList."""

    def get_breadcrumbs(self) -> list:
        return [("Inicio", reverse("core:home"))]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        breadcrumbs = self.get_breadcrumbs()
        context["breadcrumbs"] = breadcrumbs

        request = self.request
        items = []
        for position, (label, url) in enumerate(breadcrumbs, start=1):
            item = {
                "@type": "ListItem",
                "position": position,
                "name": label,
            }
            if url:
                item["item"] = request.build_absolute_uri(url)
            items.append(item)

        context["breadcrumb_jsonld"] = mark_safe(
            _safe_json_script({
                "@context": "https://schema.org",
                "@type": "BreadcrumbList",
                "itemListElement": items,
            })
        )
        return context
