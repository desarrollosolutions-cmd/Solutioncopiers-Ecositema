"""Configuración de la app Core."""
from django.apps import AppConfig
from django.db.models.signals import pre_save


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    verbose_name = "Núcleo"

    def ready(self):
        from .signals import generate_slug_on_save, set_published_at_on_publish
        from .models import SluggableModel, PublishableModel

        for concrete in self._get_concrete_subclasses(SluggableModel):
            pre_save.connect(generate_slug_on_save, sender=concrete)

        for concrete in self._get_concrete_subclasses(PublishableModel):
            pre_save.connect(set_published_at_on_publish, sender=concrete)

    @staticmethod
    def _get_concrete_subclasses(abstract_model):
        result = []
        for subclass in abstract_model.__subclasses__():
            if subclass._meta.abstract:
                result.extend(CoreConfig._get_concrete_subclasses(subclass))
            else:
                result.append(subclass)
        return result
