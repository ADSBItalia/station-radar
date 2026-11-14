FROM python:3.11-alpine

LABEL maintainer="ADSBItalia Team <info@adsbitalia.it>"
LABEL description="ADSBItalia Station Edition - Modern Avionics Radar & Web Settings Panel"

WORKDIR /app

# Create necessary directories
RUN mkdir -p /app/server /app/web /app/config

# Copy application files
COPY server/ /app/server/
COPY web/ /app/web/

# Expose default port
EXPOSE 8088

# Set environment
ENV PORT=8088
ENV PYTHONUNBUFFERED=1

# Volume for persistent station configuration
VOLUME ["/app/config", "/app/web/images"]

CMD ["python3", "/app/server/server.py"]
