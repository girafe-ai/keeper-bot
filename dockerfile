FROM python

WORKDIR /keeper-bot

COPY keeper-bot.py ./

COPY requirements.txt ./

RUN python -m venv ./.venv
RUN . .venv/bin/activate
RUN pip install -r requirements.txt

CMD [ "python" , "keeper-bot.py"]

