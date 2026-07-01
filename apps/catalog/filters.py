"""Lógica de filtrado para el catálogo."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from django.db.models import Q, QuerySet


class CopierFilters:
    """Conjunto de filtros aplicables al modelo Copier."""

    @staticmethod
    def by_category(queryset: QuerySet, category_slug: str | None) -> QuerySet:
        if category_slug:
            return queryset.filter(category__slug=category_slug)
        return queryset

    @staticmethod
    def by_toner_type(queryset: QuerySet, toner_type: str | None) -> QuerySet:
        valid = {"bw", "color", "both"}
        if toner_type in valid:
            return queryset.filter(toner_type=toner_type)
        return queryset

    @staticmethod
    def by_paper_size(queryset: QuerySet, paper_size: str | None) -> QuerySet:
        valid = {"a4", "a3", "both"}
        if paper_size in valid:
            return queryset.filter(paper_size=paper_size)
        return queryset

    @staticmethod
    def by_price_range(queryset, min_price, max_price, for_rental=True):
        field = "monthly_rental_price" if for_rental else "sale_price"
        try:
            if min_price:
                queryset = queryset.filter(**{f"{field}__gte": Decimal(min_price)})
            if max_price:
                queryset = queryset.filter(**{f"{field}__lte": Decimal(max_price)})
        except (InvalidOperation, ValueError):
            pass
        return queryset

    @staticmethod
    def by_speed(queryset, min_speed):
        try:
            if min_speed:
                return queryset.filter(speed_ppm__gte=int(min_speed))
        except (ValueError, TypeError):
            pass
        return queryset

    @staticmethod
    def by_search(queryset, search_query):
        if not search_query:
            return queryset
        return queryset.filter(
            Q(name__icontains=search_query)
            | Q(model_number__icontains=search_query)
            | Q(short_description__icontains=search_query)
            | Q(brand__icontains=search_query)
        )

    @classmethod
    def apply_all(cls, queryset, params, for_rental=True):
        queryset = cls.by_category(queryset, params.get("categoria"))
        queryset = cls.by_toner_type(queryset, params.get("tipo"))
        queryset = cls.by_paper_size(queryset, params.get("papel"))
        queryset = cls.by_price_range(
            queryset, params.get("precio_min"), params.get("precio_max"),
            for_rental=for_rental,
        )
        queryset = cls.by_speed(queryset, params.get("velocidad_min"))
        queryset = cls.by_search(queryset, params.get("q"))
        return queryset.distinct()
