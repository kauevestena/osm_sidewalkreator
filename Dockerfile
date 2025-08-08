FROM qgis/qgis:latest

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

ENTRYPOINT ["bash", "-lc", "pytest"]
