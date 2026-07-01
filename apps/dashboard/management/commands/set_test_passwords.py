from django.core.management.base import BaseCommand
from django.contrib.auth.models import User


class Command(BaseCommand):
    help = "Establece contraseña de prueba para usuarios de campo"

    def handle(self, *args, **options):
        for username in ["daniel", "mateito", "pichingo"]:
            try:
                u = User.objects.get(username=username)
                u.set_password("test1234")
                u.save()
                self.stdout.write(self.style.SUCCESS(f"  {username} OK - pass: test1234"))
            except User.DoesNotExist:
                self.stdout.write(f"  {username} no existe, omitido")
