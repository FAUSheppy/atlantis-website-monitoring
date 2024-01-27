FROM debian:bookworm
RUN apt update
RUN apt install nodejs npm python3 python3-pip -y
RUN python3 -m pip install symspellpy lighthouse-python-plus --break-system-packages
RUN apt install chromium
RUN npm install -g lighthouse
RUN wget https://github.com/wolfgarbe/SymSpell/blob/master/SymSpell.FrequencyDictionary/de-100k.txt
CMD sleep 1000000
