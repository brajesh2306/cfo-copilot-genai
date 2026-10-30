FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 300 --retries 10 --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple torch
RUN pip install --no-cache-dir --timeout 300 --retries 10 -r requirements.txt
COPY . .
EXPOSE 8501 8000
CMD ["streamlit", "run", "app/main.py", "--server.address=0.0.0.0", "--server.port=8501"]
