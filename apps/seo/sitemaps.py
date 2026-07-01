"""Sitemaps XML dinámicos."""
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.blog.models import Category as BlogCategory, Post
from apps.catalog.models import CablingService, Consumable, Copier, CopierCategory
from apps.services.models import (
    CaseStudy, DatabaseService, MobileService,
    SoftwareService, WebService,
)


class StaticSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return [
            "core:home", "core:about", "core:contact", "core:solutions_hub",
            "catalog:rental_list", "catalog:sale_list",
            "catalog:technical_service", "catalog:consumables_list",
            "catalog:structured_cabling",
            "services:software_development", "services:web_design",
            "services:mobile_apps", "services:database_services",
            "leads:wizard", "blog:post_list",
        ]

    def location(self, item):
        return reverse(item)


class CopierSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.9

    def items(self):
        return Copier.published.all()

    def lastmod(self, obj):
        return obj.updated_at


class CopierCategorySitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.85

    def items(self):
        return CopierCategory.published.all()

    def lastmod(self, obj):
        return obj.updated_at


class ConsumableSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.6

    def items(self):
        return Consumable.published.all()


class CablingSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.8

    def items(self):
        return CablingService.published.all()


class SoftwareServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.85

    def items(self):
        return SoftwareService.published.all()


class WebServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.85

    def items(self):
        return WebService.published.all()


class MobileServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.85

    def items(self):
        return MobileService.published.all()


class DatabaseServiceSitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.85

    def items(self):
        return DatabaseService.published.all()


class CaseStudySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.7

    def items(self):
        return CaseStudy.published.all()


class BlogPostSitemap(Sitemap):
    changefreq = "weekly"
    priority = 0.6

    def items(self):
        return Post.published.all()

    def lastmod(self, obj):
        return obj.updated_at


class BlogCategorySitemap(Sitemap):
    changefreq = "monthly"
    priority = 0.5

    def items(self):
        return BlogCategory.objects.all()


sitemaps_dict = {
    "static": StaticSitemap,
    "copiers": CopierSitemap,
    "copier_categories": CopierCategorySitemap,
    "consumables": ConsumableSitemap,
    "cabling": CablingSitemap,
    "software": SoftwareServiceSitemap,
    "web": WebServiceSitemap,
    "mobile": MobileServiceSitemap,
    "database": DatabaseServiceSitemap,
    "cases": CaseStudySitemap,
    "blog_posts": BlogPostSitemap,
    "blog_categories": BlogCategorySitemap,
}
