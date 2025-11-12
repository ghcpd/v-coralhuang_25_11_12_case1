FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["bash", "-lc", "pytest -q tests/test_pagination_consistency.py && python -c \"print('Finished')\""]
