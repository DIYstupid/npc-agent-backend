FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

ARG INSTALL_ML=true

WORKDIR /app

COPY requirements.txt /app/requirements.txt
COPY requirements-ml.txt /app/requirements-ml.txt
RUN pip install -r /app/requirements.txt \
    && if [ "$INSTALL_ML" = "true" ]; then pip install -r /app/requirements-ml.txt; fi

COPY app /app/app
COPY scripts /app/scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
