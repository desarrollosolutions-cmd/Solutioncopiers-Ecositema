"""Vistas del Blog."""
from __future__ import annotations

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.urls import reverse
from django.views.generic import DetailView, ListView

from apps.core.mixins import BreadcrumbMixin, JsonLDMixin, SEOContextMixin
from .models import Category, Post, Tag


class PostListView(SEOContextMixin, BreadcrumbMixin, ListView):
    model = Post
    template_name = "blog/post_list.html"
    context_object_name = "posts"
    paginate_by = 9
    meta_title_default = "Blog — Tecnología B2B y Transformación Digital"
    meta_description_default = (
        "Artículos sobre fotocopiadoras, cableado estructurado, desarrollo "
        "de software y transformación digital para empresas en Colombia."
    )

    def get_queryset(self):
        qs = Post.published.select_related("category", "author").prefetch_related("tags")
        q = self.request.GET.get("q", "").strip()
        if q:
            qs = qs.filter(
                Q(title__icontains=q) | Q(excerpt__icontains=q) | Q(content__icontains=q)
            )
        return qs

    def get_breadcrumbs(self):
        return [("Inicio", reverse("core:home")), ("Blog", "")]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["categories"] = Category.objects.all()
        context["popular_tags"] = Tag.objects.filter(posts__status="published").distinct()[:20]
        context["search_query"] = self.request.GET.get("q", "")
        return context


class PostByTagView(PostListView):
    template_name = "blog/post_list.html"

    def dispatch(self, request, *args, **kwargs):
        self.tag = get_object_or_404(Tag, slug=kwargs.get("slug"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(tags=self.tag)

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Blog", reverse("blog:post_list")),
            (f"#{self.tag.name}", ""),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_tag"] = self.tag
        return context


class PostByCategoryView(PostListView):
    template_name = "blog/post_by_category.html"

    def dispatch(self, request, *args, **kwargs):
        self.category = get_object_or_404(Category, slug=kwargs.get("slug"))
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        return super().get_queryset().filter(category=self.category)

    def get_seo_object(self):
        return self.category

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Blog", reverse("blog:post_list")),
            (self.category.name, ""),
        ]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_category"] = self.category
        return context


class PostDetailView(SEOContextMixin, BreadcrumbMixin, JsonLDMixin, DetailView):
    model = Post
    template_name = "blog/post_detail.html"
    context_object_name = "post"

    def get_queryset(self):
        return Post.published.select_related("category", "author").prefetch_related("tags")

    def get_breadcrumbs(self):
        return [
            ("Inicio", reverse("core:home")),
            ("Blog", reverse("blog:post_list")),
            (self.object.category.name, self.object.category.get_absolute_url()),
            (self.object.title, ""),
        ]

    def extra_jsonld_data(self, context):
        return {
            "@type": "Article",
            "headline": self.object.title,
            "datePublished": self.object.published_at.isoformat() if self.object.published_at else None,
            "author": {
                "@type": "Person",
                "name": self.object.author.get_full_name() if self.object.author else "Solution Copiers",
            },
        }

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["related_posts"] = Post.published.filter(
            category=self.object.category
        ).exclude(pk=self.object.pk)[:3]
        return context
