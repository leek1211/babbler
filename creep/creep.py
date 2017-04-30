import os
from flask import Flask, request, g, redirect, url_for, abort, \
     render_template, flash
from flask_mysqldb import MySQL
from konlpy.tag import Hannanum, Kkma, Komoran, Twitter
import jpype
import requests
import collections
import random
import calendar
import time
import datetime

app = Flask(__name__) # create the application instance :)
app.config.from_object(__name__) # load config from this file , creep.py
mysql = MySQL(app)

engines = [Hannanum(), Kkma(), Twitter()]

for e in engines:
    print(e.nouns("사전 초기화"))

# Load default config and override config from an environment variable
app.config.update(dict(
    SECRET_KEY='development key',
    MYSQL_HOST='127.0.0.1',
    MYSQL_USER='root',
    MYSQL_PASSWORD='123456',
    MYSQL_DB='creep',
    MYSQL_CURSORCLASS='DictCursor',
    MYSQL_PORT=3306
))

GOOGLE_SEARCH_URL='https://www.googleapis.com/customsearch/v1'
env = os.environ
GOOGLE_API_KEY = env['GOOGLE_API_KEY']
GOOGLE_ID = env['GOOGLE_ID']

"""

Flask Commands

"""
@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    db = mysql.connection
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().execute(f.read())
    print('Initialized the database.')

"""

Helper Functions

"""

def get_time_before_hours(time, hours):
    return time - hours * 60 * 60

def get_current_time():
    return calendar.timegm(time.gmtime())

def get_google_image(word):
    print("sending request to Google Image API...")
    params = dict (
        searchType = 'image',
        key = GOOGLE_API_KEY,
        cx = GOOGLE_ID,
        q = word 
    )
    response= requests.get(url = GOOGLE_SEARCH_URL, params=params)
    items = response.json()['items']

    idx = 0
    for i in range(0, 10):
        lk =  items[i]['link']
        try:
            rsp = requests.get(url=lk)
            rsp.raise_for_status()
        except requests.exceptions.HTTPError as err:
            continue
        idx = i
        break
    item = items[idx]
    image_url = item['link']

    return image_url

def get_keywords(nouns, freq):
    uniq = set(nouns)
    ret = []
    for x in uniq:
        if nouns.count(x) >= freq and len(x) > 1 :
            ret.append(x)
    return set(ret)

"""
ROUTES
Creep Routes

GET /: Index page

POST /words : add words

GET /images : show images

"""
@app.route('/')
def show_entries():
    cur = mysql.connection.cursor()
    cur.execute('select * from keywords order by created_at desc limit 40')
    keywords = cur.fetchall()

    for k in keywords:
        k['created_at'] = datetime.datetime.fromtimestamp(k['created_at'])

    return render_template('show_entries.html', entries=keywords)

@app.route('/words', methods=['POST'])
def add_word():
    jpype.attachThreadToJVM()
    body = request.get_json(force=True)
    print(body)

    nouns = []
    for e in engines:
        nouns.extend(e.nouns(body['sentence']))
    
    keywords = get_keywords(nouns, len(engines) * 0.5)
    if len(keywords) == 0:
        return ""
    current = get_current_time()
    day_before = get_time_before_hours(current, 24)

    # Query for the google searched words within last 24 hours
    db = mysql.connection
    cur = db.cursor()
    sql='SELECT * FROM keywords WHERE url IS NOT NULL AND created_at > %s AND word IN (%s)'
    in_p=', '.join(list(map(lambda x: '%s', keywords)))
    sql =  sql % ('%s', in_p)
    params = []
    params.append(day_before)
    params.extend(keywords)
    cur.execute(sql, params)
    existing_keywords = cur.fetchall()

    # For the words already googled, use those urls.
    existing_url = {}
    for k in existing_keywords:
        existing_url[k['word']] = k['url']

    for word in keywords:
        cur.execute("insert into keywords values (%s, %s, %s)", (word, existing_url.get(word), current))
    db.commit()

    return ", ".join(keywords)

@app.route('/images', methods=['GET'])
def get_latest_keyword():
    db = mysql.connection
    cur = db.cursor()

    # Query the keywords only for the last 30 minutes.
    now = get_current_time()
    hour_before = get_time_before_hours(now, 0.5)
    cur.execute('select * from keywords where created_at > %s', [hour_before])
    keywords = cur.fetchall()
    if len(keywords) == 0:
        cur.execute('select * from keywords order by created_at desc limit 100')
        keywords = cur.fetchall()

    row = random.choice(keywords)

    word = row['word']
    created_at = row['created_at']
    day_before = get_time_before_hours(created_at, 24)
    image_url = row['url']

    if image_url is None:
        image_url = get_google_image(word)
        cur.execute('UPDATE keywords SET url = %s WHERE url IS NULL AND word = %s AND created_at > %s', (image_url, word, day_before))
        db.commit()

    return render_template('show_image.html', keyword=word, image_url=image_url)


