FROM python:3-alpine
RUN apk add --no-cache nodejs npm chromium wget git gcc g++
RUN pip install symspellpy \
                git+https://github.com/FAUSheppy/lighthouse-python-docker \
                requests \
                bs4 \
                pika \
                python-dateutil \
                --break-system-packages --no-cache-dir

RUN npm install -g lighthouse
RUN wget https://github.com/wolfgarbe/SymSpell/blob/master/SymSpell.FrequencyDictionary/de-100k.txt

COPY *.py /app/
WORKDIR /app

RUN apk del --no-cache py-pip git gcc g++ wget

ENTRYPOINT ["python"]
CMD ["runner.py"]
