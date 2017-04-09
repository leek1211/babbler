import os
import sqlite3
from flask import Flask, request, g, redirect, url_for, abort, \
     render_template, flash
from konlpy.tag import Hannanum, Kkma, Komoran, Twitter
import jpype
import requests
import collections
import random

app = Flask(__name__) # create the application instance :)
app.config.from_object(__name__) # load config from this file , creep.py

engines = [Hannanum(), Kkma(), Twitter()]

# Load default config and override config from an environment variable
app.config.update(dict(
    DATABASE=os.path.join(app.root_path, 'creep.db'),
    SECRET_KEY='development key',
    USERNAME='admin',
    PASSWORD='default'
))

GOOGLE_SEARCH_URL='https://www.googleapis.com/customsearch/v1'
env = os.environ
GOOGLE_API_KEY = env['GOOGLE_API_KEY']
GOOGLE_ID = env['GOOGLE_ID']


def connect_db():
    """Connects to the specific database."""
    rv = sqlite3.connect(app.config['DATABASE'])
    rv.row_factory = sqlite3.Row
    return rv

def init_db():
    db = get_db()
    with app.open_resource('schema.sql', mode='r') as f:
        db.cursor().executescript(f.read())
    db.commit()

@app.cli.command('initdb')
def initdb_command():
    """Initializes the database."""
    init_db()
    print('Initialized the database.')

def get_db():
    """Opens a new database connection if there is none yet for the
    current application context.
    """
    if not hasattr(g, 'sqlite_db'):
        g.sqlite_db = connect_db()
    return g.sqlite_db

@app.teardown_appcontext
def close_db(error):
    """Closes the database again at the end of the request."""
    if hasattr(g, 'sqlite_db'):
        g.sqlite_db.close()

def resize(width, height):
    ratio = height / width
    if height > width:
        height = min(height, 400)
        width = height / ratio
    else :
        width = min(width, 400)
        height = width * ratio
    return { 'width': width, 'height': height }
 

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
    image = item['image']
    p = resize(image['width'], image['height'])
    width = p['width']
    height = p['height']

    return [image_url, height, width]

def get_keywords(nouns, freq):
    uniq = set(nouns)
    ret = []
    for x in uniq:
        if nouns.count(x) >= freq and len(x) > 1 :
            ret.append(x)
    return set(ret)

@app.route('/')
def show_entries():
    db = get_db()
    cur = db.execute('select word from entries order by created_at desc limit 40')
    entries = cur.fetchall()
    return render_template('show_entries.html', entries=entries)

@app.route('/words', methods=['POST'])
def add_word():
    jpype.attachThreadToJVM()
    body = request.get_json(force=True)
    print(body)

    nouns = []
    for e in engines:
        nouns.extend(e.nouns(body['sentence']))
    print("nouns: " + ", ".join(nouns))
    
    keywords = get_keywords(nouns, len(engines) * 0.5)
    print("keywords: " + ", ".join(keywords))

    db = get_db()
    for word in keywords:
        db.execute("insert into entries values (?, DateTime('now'))", [word])

    db.commit()
    return ", ".join(keywords)

@app.route('/images', methods=['GET'])
def get_latest_keyword():
    db = get_db()
    cur = db.execute('select * from entries order by created_at desc limit 10')
    keywords = cur.fetchall()
    row = random.choice(keywords)

    keyword = row['word']
    item = get_google_image(keyword)
    image_url = item[0]
    height = item[1]
    width = item[2]

    return render_template('show_image.html', keyword=keyword, image_url=image_url, height = height, width = width)


