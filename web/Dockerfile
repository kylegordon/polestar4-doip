FROM python:3.12-slim
RUN pip install --no-cache-dir pyyaml==6.0.2
ENV PYTHONUNBUFFERED=1 \
    P4_WEB_W=/w \
    P4_WEB_OUT=/srv \
    P4_WEB_HOST=0.0.0.0 \
    P4_WEB_PORT=8088
COPY gen.py server.py live.html start.sh /web/
CMD ["/bin/sh", "/web/start.sh"]
