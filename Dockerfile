FROM python:3-slim

COPY . /src

RUN pip install --upgrade /src && \
    cp /usr/local/bin/aquanta_exporter /aquanta_exporter

EXPOSE 9597

ENTRYPOINT ["/aquanta_exporter"]
