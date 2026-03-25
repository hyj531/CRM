from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        # Workaround for Django 4.2 + Python 3.14 where BaseContext.__copy__
        # may return a super() proxy without 'dicts', causing admin render errors.
        from django.template import context as ctx

        def _safe_copy(self):
            cls = self.__class__
            duplicate = cls.__new__(cls)
            if hasattr(self, "__dict__"):
                duplicate.__dict__.update(self.__dict__)
            duplicate.dicts = self.dicts[:]
            return duplicate

        if getattr(ctx.BaseContext.__copy__, '_patched', False) is False:
            ctx.BaseContext.__copy__ = _safe_copy
            ctx.BaseContext.__copy__._patched = True
