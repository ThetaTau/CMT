"""Contact-sync provider adapters.

Each provider exposes a subclass of :class:`~thetatauCMT.contact_sync.providers.base.ContactProvider`
that knows how to (1) render OAuth authorize URLs, (2) exchange an authorization
code for tokens, (3) refresh access tokens, and (4) push a batch of
:class:`~thetatauCMT.contact_sync.officers.OfficerContact` records into the
provider's contacts store.

Providers that do not have a writeable OAuth API (e.g. Apple iCloud) are handled
via the vCard download path in :mod:`thetatauCMT.contact_sync.views` instead of
being registered here.
"""

from .base import PROVIDERS, ContactProvider, get_provider, provider_is_configured
from .google import GoogleContactsProvider
from .microsoft import MicrosoftContactsProvider

__all__ = [
    "PROVIDERS",
    "ContactProvider",
    "GoogleContactsProvider",
    "MicrosoftContactsProvider",
    "get_provider",
    "provider_is_configured",
]
