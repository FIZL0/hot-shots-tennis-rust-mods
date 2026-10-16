FROM python:3.12-slim
RUN pip install --no-cache-dir huggingface_hub==2.2.0 fastapi==0.115.6 uvicorn==0.34.0
RUN useradd -m -u 1000 user
USER user
WORKDIR /home/user/app
COPY --chown=user build.py app.py ./
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
