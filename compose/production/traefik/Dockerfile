FROM traefik:v2.2.11@sha256:ea0aa8832bfd08369166baecd40b35fc58979df8f5dc5182e4e63ee6adbe66db
RUN mkdir -p /etc/traefik/acme \
  && touch /etc/traefik/acme/acme.json \
  && chmod 600 /etc/traefik/acme/acme.json
COPY ./compose/production/traefik/traefik.yml /etc/traefik
