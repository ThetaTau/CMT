"""Certificate / letter generation + upload for award grants (AWI-8)."""

import logging

from django.core.files.base import ContentFile
from django.utils import timezone
from easy_pdf.rendering import render_to_pdf

from .models import GrantArtifact

logger = logging.getLogger(__name__)

CERTIFICATE_TEMPLATE = "awards/certificate.html"


def certificate_context(grant):
    """Merge context for the certificate template (recipient / award / cycle / date)."""
    return {
        "grant": grant,
        "award": grant.award_type,
        "award_name": grant.award_type.name,
        "recipient": grant.recipient_display,
        "recipient_kind": grant.recipient_kind,
        "cycle": grant.cycle,
        "cycle_name": grant.cycle.name,
        "effective_date": grant.effective_date,
        "granted_at": grant.granted_at,
        "reason": grant.reason,
    }


def generate_certificate(grant, created_by=None):
    """Render the certificate template to PDF and store it as a ``GrantArtifact``."""
    content = render_to_pdf(CERTIFICATE_TEMPLATE, context=certificate_context(grant))
    artifact = GrantArtifact(
        grant=grant,
        artifact_type=GrantArtifact.ArtifactType.GENERATED,
        created_by=created_by,
        generated_at=timezone.now(),
    )
    artifact.file.save(f"certificate_{grant.pk}.pdf", ContentFile(content), save=False)
    artifact.save()
    return artifact


def store_uploaded_artifact(grant, uploaded_file, created_by=None):
    """Store a manually uploaded certificate / letter as a ``GrantArtifact``."""
    artifact = GrantArtifact(
        grant=grant,
        artifact_type=GrantArtifact.ArtifactType.UPLOADED,
        created_by=created_by,
        uploaded_at=timezone.now(),
        file=uploaded_file,
    )
    artifact.save()
    return artifact


def maybe_generate_certificate(grant, created_by=None):
    """Generate a certificate when the award type is configured to auto-generate.

    Best-effort: a rendering failure is logged but never propagated, so it can
    never break the grant path. Returns the artifact or ``None``.
    """
    if not grant.award_type.auto_generate_certificate:
        return None
    try:
        return generate_certificate(grant, created_by=created_by)
    except Exception:
        logger.exception("Auto certificate generation failed for grant %s", grant.pk)
        return None
