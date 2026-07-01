"""Context processors del módulo SEO."""
from .models import DesignTokens


def design_tokens(request):
    tokens = DesignTokens.load()
    return {
        "design_tokens": tokens,
        "design_tokens_css": tokens.to_css_variables(),
    }
