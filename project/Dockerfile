FROM python:3.11-slim

WORKDIR /app

COPY . /app

RUN pip install --no-cache-dir -r project/requirements.txt

CMD ["pytest", "-q"]
