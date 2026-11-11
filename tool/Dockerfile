FROM python:3.12-slim
RUN pip install --no-cache-dir pytest==8.3.4 pyyaml==6.0.2
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/w/tool P4_ROOT=/w
WORKDIR /w
ENTRYPOINT ["python", "-m", "p4doip"]
