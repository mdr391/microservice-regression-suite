FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .
COPY config/ config/
USER 1000:1000
ENTRYPOINT ["regression-suite"]
CMD ["--config", "config/prod.yaml", "--no-color"]
