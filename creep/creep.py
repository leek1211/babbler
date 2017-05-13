import os
from flask import Flask, request, g, redirect, url_for, abort, \
     render_template, flash, jsonify
from flask_mysqldb import MySQL
from konlpy.tag import Hannanum, Kkma, Komoran, Twitter
import jpype
import requests
import collections
import random
import calendar
import time
import datetime
from translate import Translator


free_translator = Translator(to_lang="en", from_lang="ko")

app = Flask(__name__) # create the application instance :)
app.config.from_object(__name__) # load config from this file , creep.py
mysql = MySQL(app)

engines = [Hannanum(), Twitter()]

# Load default config and override config from an environment variable
app.config.update(dict(
    SECRET_KEY='development key',
    MYSQL_HOST='127.0.0.1',
    MYSQL_USER='root',
    MYSQL_PASSWORD='123456',
    MYSQL_DB='creep',
    MYSQL_CURSORCLASS='DictCursor',
    MYSQL_PORT=3306,
    JSON_AS_ASCII=False
))

env = os.environ

GIPHY_API_KEY='dc6zaTOxFJmzC'
GIPHY_SEARCH_URL='http://api.giphy.com/v1/gifs/search'
GIPHY_TRENDING_URL='http://api.giphy.com/v1/gifs/trending'


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

def translate_to_english(korean_text):
    db = mysql.connection
    cur = db.cursor()
    cur.execute('SELECT * FROM dictionary WHERE korean = %s and english is NOT NULL', [korean_text])
    entries = cur.fetchall()

    if len(entries) == 0:
        try:
            english_text = free_translator.translate(korean_text)
            print("translated " + korean_text + " to " + english_text)
            cur.execute("INSERT into dictionary values (%s, %s)", (korean_text, english_text))
            db.commit()
            return english_text
        except Exception as e:
            print("secondary translation failed {0}".format(e))
            return ""
    else:
        return entries[0]['english']


def get_time_before_hours(time, hours):
    return time - hours * 60 * 60

def get_current_time():
    return calendar.timegm(time.gmtime())


def random_select_in_giphy_items(items):
    if len(items) == 0:
        return None
    return random.choice(items)['images']['original']['url']

def get_giphy_trending_image():
    print("seding request to Giphy Trending API")
    
    params = dict (
        api_key = GIPHY_API_KEY
    )
    response= requests.get(url = GIPHY_TRENDING_URL, params=params)
    items = response.json()['data']
    return random_select_in_giphy_items(items)

def get_giphy_image(word, isKorean = True):
    print("sending request to Giphy Search API for the word " + word + " ...")
    params = dict (
        api_key = GIPHY_API_KEY,
        q = word 
    )
    if isKorean:
        params['lang'] = 'ko'
    
    response= requests.get(url = GIPHY_SEARCH_URL, params=params)
    items = response.json()['data']
    if len(items) == 0:
        return None

    return random_select_in_giphy_items(items)

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
    interval_sec = 10
    after = request.args.get('after')
    if after is None:
        after = get_current_time()
    after = float(after)

    after = after - interval_sec
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM keywords WHERE created_at >= %s ORDER BY created_at DESC', [after])
    keywords = cur.fetchall()

    for k in keywords:
        k['created_at'] = datetime.datetime.fromtimestamp(k['created_at'])

    return render_template('show_entries.html', entries=keywords, intervalSec = interval_sec)

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

    db = mysql.connection
    cur = db.cursor()
    for word in keywords:
        cur.execute("INSERT into keywords values (%s, NULL, %s)", (word, current))
    db.commit()

    return ", ".join(keywords)

@app.route('/images', methods=['GET'])
def render_image_page():
    seq = request.args.get('seq')
    if seq is None:
        return render_template('show_image.html')
    else:
        return render_template('show_image' + seq + '.html')

@app.route('/image_info', methods=['GET'])
def get_latest_keyword():
    db = mysql.connection
    cur = db.cursor()

    now = get_current_time()
    # Query the keywords within the last 2 minutes.
    most_recent = get_time_before_hours(now, 0.0333333)
    cur.execute('SELECT * FROM keywords WHERE created_at > %s', [most_recent])
    keywords = cur.fetchall()

    # If there is none, query the keywords for the last one hour.
    if len(keywords) == 0:
        hour_before = get_time_before_hours(now, 1)
        cur.execute('SELECT * FROM keywords WHERE created_at > %s', [hour_before])
        keywords = cur.fetchall()

    if len(keywords) == 0:
        cur.execute('SELECT * FROM keywords ORDER BY created_at DESC LIMIT 100')
        keywords = cur.fetchall()

    row = random.choice(keywords)

    word = row['word']
    created_at = row['created_at']
    image_url = row['url']
    
    if image_url is None:
        image_url = get_giphy_image(word)
    if image_url is None:
        word = translate_to_english(word)
        image_url = get_giphy_image(word, False)
    if image_url is None:
        word = "NOT FOUND " + row['word']
        cur.execute('DELETE FROM keywords WHERE word = %s', [row['word']])
        db.commit()
        image_url = get_giphy_trending_image()
    
    # cur.execute('UPDATE keywords SET url = %s WHERE url IS NULL AND word = %s AND created_at = %s', (image_url, word, created_at))
    # db.commit()

    time_string = time.strftime('%Y-%m-%d %H-%M', time.localtime(created_at))
    result = dict (
        keyword=word,
        image_url=image_url,
        created_at=time_string
    )
    return jsonify(result)


