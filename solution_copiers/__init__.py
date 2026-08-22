import sys

# Patch de compatibilidad: imagekit/pilkit usa _Pickler._batch_setitems()
# con firma incorrecta en Python 3.14+ donde el argumento 'obj' es obligatorio.
if sys.version_info >= (3, 14):
    try:
        import pickle
        import imagekit.hashers as _hashers

        class _PatchedPickler(pickle._Pickler):
            def save_dict(self, obj):
                self._batch_setitems(sorted(obj.items()), obj)

        _hashers.CanonicalizingPickler = _PatchedPickler
    except Exception:
        pass
