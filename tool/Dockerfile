FROM python:3.12-slim
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/w/tool P4_ROOT=/w
WORKDIR /w
ENTRYPOINT ["python", "-m", "p4doip"]
