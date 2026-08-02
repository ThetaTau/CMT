from dj_anonymizer.register_models import register_skip

from thetatauCMT.guides.models import Feature, FeatureArea, RoleGuide, RoleGuideStep, UserAcknowledgement

# FeatureArea, Feature, RoleGuide and RoleGuideStep are the catalog / role-guide
# content, seeded from guides/fixtures/feature_registry.json -- editorial copy
# with no personal data, and staging is where it gets reviewed.
# UserAcknowledgement records that someone dismissed a What's New entry; it
# references the member only through a foreign key (anonymized via the User
# model) and holds no identity fields of its own.
register_skip(
    [
        FeatureArea,
        Feature,
        RoleGuide,
        RoleGuideStep,
        UserAcknowledgement,
    ]
)
