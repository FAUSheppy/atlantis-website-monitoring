FROM python:3-alpine

RUN apk add --no-cache curl

RUN pip install --no-cache-dir -U pip
RUN pip install --no-cache-dir --break-system-packages waitress

COPY req.txt .
RUN pip install --no-cache-dir -r req.txt
RUN apk del py-pip --no-cache

WORKDIR /app
COPY ./ .

ENTRYPOINT ["waitress-serve"] 
CMD ["--host", "0.0.0.0", "--port", "5000", "--call", "app:createApp"]
