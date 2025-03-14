# syntax=docker/dockerfile:1

FROM python:3.10-slim-buster 
WORKDIR /app
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt
COPY . .

CMD ["python", "main.py"]
