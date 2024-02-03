FROM python:3-alpine
RUN pip install requests

COPY *.py /app/
WORKDIR /app

ENTRYPOINT ["python"]
CMD ["scheduler.py"]
