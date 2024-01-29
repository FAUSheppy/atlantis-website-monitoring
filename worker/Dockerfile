FROM debian:bookworm
RUN apt update
RUN apt install nodejs npm python3 python3-pip -y
RUN python3 -m pip install symspellpy lighthouse-python-plus --break-system-packages
RUN apt install chromium -y
RUN apt install wget -y
RUN npm install -g lighthouse
RUN wget https://github.com/wolfgarbe/SymSpell/blob/master/SymSpell.FrequencyDictionary/de-100k.txt
RUN python3 -m pip install requests bs4 python-dateutil --break-system-packages
RUN mkdir /app
COPY *.py /app/
CMD sleep 1000
