from tornado import ioloop, web, gen, httpserver, autoreload
from sockjs.tornado import SockJSRouter, SockJSConnection
from datetime import datetime, time, timedelta
import os, pymongo, json, pytz, locale
from config import MONGO_URL, MONGO_PORT, MONGO_DB

utc = pytz.utc
pst = pytz.timezone('US/Pacific-New')
locale.setlocale(locale.LC_ALL, 'en_US.utf8')

class MainHandler(web.RequestHandler):
    @web.asynchronous
    def get(self):
        self.render("template.html", title="tamabot")

class StatsConnection(SockJSConnection):
    coll = None
    def on_open(self, info):
        mdb = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
        db = mdb[MONGO_DB]
        self.coll = db['stat']
        self.update_stats()
    def on_message(self, msg):
        self.update_stats()
    def update_stats(self):
        data = {}
        temp = self.coll.find()
        for line in temp:
            if line['field'] != 'run':
                data[line['field']] = locale.format('%d', line['count'], grouping=True)
            else:
                data[line['field']] = utc.localize(line['date']).astimezone(pst).strftime('%Y-%m-%d')
        self.send(json.dumps(data))
    def on_close(self):
        mdb.close()

class GraphConnection(SockJSConnection):
    coll = None
    def on_open(self, info):
        mdb = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
        db = mdb[MONGO_DB]
        self.coll = db['log']
        self.get_data()
    def on_message(self, msg):
        self.get_data()
    def get_data(self):
        now = datetime.now()
        data = {}
        data['dates'], data['monster_table'] = [0] * 8, [0] * 8
        data['flair_posts'], data['ignores'] = [0] * 8, [0] * 8
        data['deletes'], data['revisits'] = [0] * 8, [0] * 8

        n = 0
        for i, e in reversed(list(enumerate(data['dates']))):
            then = now - timedelta(days=n)
            data['dates'][i] = then.strftime('%m/%d')
            n = n + 1

        temp = self.coll.find({"date": {"$gte": then}}).sort('date', pymongo.ASCENDING)
        for line in temp:
            timestamp = utc.localize(line['date']).astimezone(pst).strftime('%m/%d')
            if line['type'] == 'MONSTER TABLE':
                data['monster_table'][data['dates'].index(timestamp)] = data['monster_table'][data['dates'].index(timestamp)] + 1
            elif line['type'] == 'FLAIR ID':
                data['flair_posts'][data['dates'].index(timestamp)] = data['flair_posts'][data['dates'].index(timestamp)] + 1
            elif line['type'] == 'IGNORE_POST':
                data['ignores'][data['dates'].index(timestamp)] = data['ignores'][data['dates'].index(timestamp)] + 1
            elif line['type'] == 'DEL_PM':
                data['deletes'][data['dates'].index(timestamp)] = data['deletes'][data['dates'].index(timestamp)] + 1
            elif line['type'] == 'REVISIT':
                data['revisits'][data['dates'].index(timestamp)] = data['revisits'][data['dates'].index(timestamp)] + 1
        self.send(json.dumps(data))
    def on_close(self):
        mdb.close()

class LogsConnection(SockJSConnection):
    coll = None
    def on_open(self, info):
        mdb = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
        db = mdb[MONGO_DB]
        self.coll = db['log']
        self.update_log()
    def on_message(self, msg):
        self.update_log()
    def update_log(self):
        raw_log = []
        raw_log = self.coll.find({}, limit=25).sort('date', pymongo.DESCENDING)
        data = []
        for line in raw_log:
            timestamp = utc.localize(line['date']).astimezone(pst).strftime('%Y-%m-%d %H:%M:%S')
            message = ""
            if line['type'] == 'MONSTER TABLE':
                message = "<span class='ts'>%s :::</span><span>made a monster table post under <a href='%s'>%s</a></span>" % (timestamp, line['url'], line['url'])
            elif line['type'] == 'FLAIR ID':
                message = "<span class='ts'>%s :::</span><span>made a flair id post under <a href='%s'>%s</a></span>" % (timestamp, line['url'], line['url'])
            elif line['type'] == 'SPLIT':
                message = "<span class='ts'>%s :::</span><span>message too long... splitting!</span>" % (timestamp)
            elif line['type'] == 'REVISIT':
                message = "<span class='ts'>%s :::</span><span>(re)visiting <a href='%s'>%s</a> under <a href='http://reddit.com/u/%s'>%s</a>'s request</span>" % (timestamp, line['url'], line['url'], line['user'], line['user'])
            elif line['type'] == 'REVISIT_BAD':
                message = "<span class='ts'>%s :::</span><span>bad revisit request for <a href='%s'>%s</a> by <a href='http://reddit.com/u/%s'>%s</a></span>" % (timestamp, line['url'], line['url'], line['user'], line['user'])
            elif line['type'] == 'IGNORE_PM':
                message = "<span class='ts'>%s :::</span><span>ignoring posts under <a href='%s'>%s</a> by <a href='http://reddit.com/u/%s'>%s</a>'s request</span>" % (timestamp, line['url'], line['url'], line['user'], line['user'])
            elif line['type'] == 'IGNORE_POST':
                message = "<span class='ts'>%s :::</span><span>made an ignore post under <a href='%s'>%s</a></span>" % (timestamp, line['url'], line['url'])
            elif line['type'] == 'DEL_PM':
                message = "<span class='ts'>%s :::</span><span>deleting post under <a href='%s'>%s</a> by <a href='http://reddit.com/u/%s'>%s</a>'s request</span>" % (timestamp, line['url'], line['url'], line['user'], line['user'])
            elif line['type'] == 'DEL_BAD':
                message = "<span class='ts'>%s :::</span><span>bad delete request for <a href='%s'>%s</a> by <a href='http://reddit.com/u/%s'>%s</a></span>" % (timestamp, line['url'], line['url'], line['user'], line['user'])
            elif line['type'] == 'UNIGNORE':
                message = "<span class='ts'>%s :::</span><span>unignoring <a href='%s'>%s</a> by <a href='http://reddit.com/u/%s'>%s</a>'s request</span>" % (timestamp, line['url'], line['url'], line['user'], line['user'])
            elif line['type'] == 'HALT':
                message = "<span class='ts'>%s :::</span><span>bot halt requested by <a href='http://reddit.com/u/%s'>%s</a></span>" % (timestamp, line['user'], line['user'])
            data.append([str(line['_id']), "<div class='log_line'>%s</div>" % (message)])
        self.send(json.dumps(data))
    def on_close(self):
        mdb.close()


StatsRouter = SockJSRouter(StatsConnection, '/tamabot/stats')
GraphRouter = SockJSRouter(GraphConnection, '/tamabot/graph')
LogsRouter = SockJSRouter(LogsConnection, '/tamabot/logs')

settings = {
    "static_path": os.path.join(os.path.dirname(__file__), "static")
}

app = web.Application([
    (r'/tamabot/', MainHandler),
    (r'/tamabot/(pure\.css)', web.StaticFileHandler, dict(path=settings['static_path'])),
    (r'/tamabot/(style\.css)', web.StaticFileHandler, dict(path=settings['static_path'])),
    (r'/tamabot/(tamabot\.png)', web.StaticFileHandler, dict(path=settings['static_path'])),
    (r'/tamabot/(tamabot2\.png)', web.StaticFileHandler, dict(path=settings['static_path'])),
] + StatsRouter.urls + GraphRouter.urls + LogsRouter.urls, **settings)

server = httpserver.HTTPServer(app)
server.listen(8008)

for dir, _, files in os.walk('tamabot/static'):
    [autoreload.watch(dir + '/' + f) for f in files if not f.startswith('.')]
ioloop.IOLoop.instance().start()
