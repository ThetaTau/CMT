ARG PYTHON_VERSION=3.12-slim-bookworm@sha256:0f5b26b9518d002b6173fd61daad821fa340635ebfec5bba471013f9ca114579



# define an alias for the specfic python version used in this file.
FROM python:${PYTHON_VERSION} as python

# Python build stage
FROM python as python-build-stage

ARG BUILD_ENVIRONMENT=production

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg2 dependencies
  libpq-dev \
  # python dependencies from github
  git\
  # Pillow dependencies
  zlib1g-dev \
  libjpeg-dev \
  # pycairo (via xhtml2pdf->svglib->rlpycairo) build dependencies
  pkg-config \
  libcairo2-dev

# Requirements are installed here to ensure they will be cached.
COPY ./requirements .

# Create Python Dependency and Sub-Dependency Wheels.
# setuptools and poetry-core are pre-built first:
#   - setuptools provides pkg_resources, required at runtime by django-betterforms
#   - poetry-core is the build backend for the git-pinned django-report-builder
# --find-links ensures pip passes the local wheel cache to isolated build
# environments it spawns for packages like the git-pinned report-builder.
RUN pip wheel --wheel-dir /usr/src/app/wheels "setuptools==80.10.2" "wheel==0.48.0" "poetry-core==2.4.1" \
  && pip wheel --wheel-dir /usr/src/app/wheels \
    --retries 5 \
    --timeout 60 \
    --find-links=/usr/src/app/wheels \
    -r ${BUILD_ENVIRONMENT}.txt


# Python 'run' stage
FROM python as python-run-stage

ARG BUILD_ENVIRONMENT=production
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED 1
ENV PYTHONDONTWRITEBYTECODE 1
ENV BUILD_ENV ${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

RUN addgroup --system django \
    && adduser --system --ingroup django django


# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg2 dependencies
  libpq-dev \
  # Translations dependencies
  gettext \
  # python-magic dependenies
  libmagic-dev \
  # cleaning up unused files
  && apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false \
  && rm -rf /var/lib/apt/lists/*

# All absolute dir copies ignore workdir instruction. All relative dir copies are wrt to the workdir instruction
# copy python dependency wheels from python-build-stage
COPY --from=python-build-stage /usr/src/app/wheels  /wheels/

# copy requirements so pip can resolve by name (more reliable than glob for
# bootstrap packages like setuptools that pip wheel may skip)
COPY ./requirements /requirements/

# use wheels to install python dependencies
RUN pip install --no-cache-dir --no-index --find-links=/wheels/ -r /requirements/${BUILD_ENVIRONMENT}.txt \
  && rm -rf /wheels/ /requirements/


COPY --chown=django:django ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint


COPY --chown=django:django ./compose/production/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start


# copy application code to WORKDIR
COPY --chown=django:django . ${APP_HOME}

# make django owner of the WORKDIR directory as well.
RUN chown django:django ${APP_HOME}

USER django

ENTRYPOINT ["/entrypoint"]
