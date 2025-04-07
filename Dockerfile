# Dockerfile

FROM registry.access.redhat.com/ubi8/python-311:latest

WORKDIR /app

COPY pyproject.toml .
COPY README.md .


USER root
RUN pip install uv==0.6.11 && \
    uv pip install . && \
    mkdir -p /opt/app-root/src/.cache/huggingface/ && \
    chmod -R 777 /opt/app-root/src/.cache/huggingface/

COPY src src

USER 1001
EXPOSE 8080

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
