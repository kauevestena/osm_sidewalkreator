FROM qgis/qgis:latest

# Install system packages and Python dependencies needed for tests
RUN apt-get update -qq \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/*

# Pre-install Python requirements so containers run tests immediately
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm /tmp/requirements.txt
