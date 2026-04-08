FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if required for some packages
# RUN apt-get update && apt-get install -y ...

COPY requirements.txt .

# Install dependencies, ensuring sse-starlette and jinja2 are included 
# which main.py depends on via fastapi.templating and sse_starlette
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir jinja2 sse-starlette

COPY . .

# Expose port that Cloud Run expects
EXPOSE 8080

# Cloud Run injects the PORT environment variable, so we use it here.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
