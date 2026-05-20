ARG PYTHON_VERSION=3.13-slim

# define an alias for the specfic python version used in this file.
FROM python:${PYTHON_VERSION} AS python

# Python build stage
FROM python AS python-build-stage

ARG BUILD_ENVIRONMENT=local

# Install apt packages
RUN apt-get update && apt-get install --no-install-recommends -y \
  # dependencies for building Python packages
  build-essential \
  # psycopg2 dependencies
  libpq-dev \
  # python dependencies from github
  git \
  # Pillow dependencies
  zlib1g-dev \
  libjpeg-dev \
  libpangocairo-1.0-0 \
  # Weasyprint dependencies
  libpango-1.0-0 \
  libpangoft2-1.0-0 \
  gir1.2-harfbuzz-0.0 \
  # pycairo (via xhtml2pdf->svglib->rlpycairo) build dependencies
  pkg-config \
  libcairo2-dev
#  libharfbuzz-subset0

# Requirements are installed here to ensure they will be cached.
COPY ./requirements .

# Create Python Dependency and Sub-Dependency Wheels.
# Build-backend packages are pre-built first so pip can find them when it
# creates isolated build environments for git-pinned packages:
#   - setuptools: provides pkg_resources (runtime req of django-betterforms)
#   - wheel:      build backend used by django-allauth-2fa (git dep)
#   - poetry-core: build backend used by django-report-builder (git dep)
# --find-links is passed to the main wheel run so pip propagates it into
# those isolated environments.
RUN pip wheel --wheel-dir /usr/src/app/wheels setuptools wheel poetry-core \
  && pip wheel --wheel-dir /usr/src/app/wheels \
    --retries 5 \
    --timeout 60 \
    --find-links=/usr/src/app/wheels \
    -r ${BUILD_ENVIRONMENT}.txt


# Python 'run' stage
FROM python AS python-run-stage

ARG BUILD_ENVIRONMENT=local
ARG APP_HOME=/app

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV BUILD_ENV=${BUILD_ENVIRONMENT}

WORKDIR ${APP_HOME}

# Install required system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
  # psycopg2 dependencies
  libpq-dev \
  git \
  # SSH client for development
  openssh-client \
  # Translations dependencies
  gettext \
  # python-magic dependenies
  libmagic-dev \
  # Weasyprint dependencies
  libpango-1.0-0 \
  libpangoft2-1.0-0 \
  gir1.2-harfbuzz-0.0 \
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


COPY ./compose/production/django/entrypoint /entrypoint
RUN sed -i 's/\r$//g' /entrypoint
RUN chmod +x /entrypoint

COPY ./compose/local/django/start /start
RUN sed -i 's/\r$//g' /start
RUN chmod +x /start



# copy application code to WORKDIR
COPY . ${APP_HOME}

ENTRYPOINT ["/entrypoint"]
