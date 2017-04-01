import os
import sqlite3
from flask import Flask, request, g, redirect, url_for, abort, \
     render_template, flash
from konlpy.tag import Hannanum, Kkma, Komoran, Twitter
import jpype

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
app.config.from_envvar('creep_SETTINGS', silent=True)

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

@app.route('/')
def show_entries():
    db = get_db()
    cur = db.execute('select word, count(word) count from entries group by word order by count(word), created_at desc ')
    entries = cur.fetchall()
    return render_template('show_entries.html', entries=entries)

def get_keywords(nouns, freq):
    uniq = set(nouns)
    ret = []
    for x in uniq:
        if nouns.count(x) >= freq and len(x) > 1 :
            ret.append(x)
    return set(ret)

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



