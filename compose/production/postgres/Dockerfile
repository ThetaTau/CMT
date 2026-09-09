FROM postgres:12.6@sha256:26ce5e265fbbf120b4a89a9b26770bad757a7dfa4f329038d93770edbe5aae00

COPY ./compose/production/postgres/maintenance /usr/local/bin/maintenance
RUN chmod +x /usr/local/bin/maintenance/*
RUN mv /usr/local/bin/maintenance/* /usr/local/bin \
    && rmdir /usr/local/bin/maintenance
