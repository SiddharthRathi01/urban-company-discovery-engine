"""Guards for the public site. The official golden set and the Urban Company analysis are permanent and read-only; endpoints that store, change or delete
files are switched off unless PUBLIC_MODE=0 (development)."""
from . import settings
from .responses import ApiError


def writes_allowed():
    if settings.PUBLIC_MODE:
        raise ApiError(403, "disabled_on_public_site", "This action is switched off on the public site: the official files are permanent and visitors' files are never stored. "
                                                       "Use the temporary analysis instead.")
