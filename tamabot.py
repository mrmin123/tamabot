# -*- coding: utf-8 -*-

import praw, re, requests, pymongo, sys
from config import USERNAME, PASSWORD, SUBREDDIT, MONGO_URL, MONGO_PORT, MONGO_DB
from util import check_processed_posts, read_queue_file, update_queue_file, reset_db, update_db, log_msg, log_success, log_warning, log_error
from collections import deque
from time import sleep, strftime, gmtime
from bs4 import BeautifulSoup

user_agent = ("tamabot:rPuzzlesAndDragonsMonitor:v2.3 by /u/mrmin123")

# constants
LIMIT = 15
SLEEP = 3
SLEEP_LONG = 15
MONSTER_LIMIT = 200
MSG_LEN_LIMIT = 9800

# check if debug mode (no posts, some feedback, more errors)
debug = False
if len(sys.argv) > 1:
    if sys.argv[1] == '--debug':
        debug = True

# globals
mod_list = []
padx_storage = {}
processed_monsters = deque([])
processed_submissions = deque([])
processed_comments = deque([])
processed_submissions_file = 'processed_submissions.txt'
processed_comments_file = 'processed_comments.txt'
ignored_submissions = deque([])
ignored_submissions_file = 'ignored_submissions.txt'
signature_intro = "\n^^I ^^post ^^user ^^flairs! ^^Mention ^^'/u/tamabot/' ^^to ^^call ^^me, ^^or ^^'-/u/tamabot' ^^to ^^make ^^me ^^ignore ^^your ^^post.\n"
signature = "\n&nbsp;\n\n^^Processing... ^^|| ^^[Homepage](http://minyoung.ch/tamabot/) || ^^[Github](https://github.com/mrmin123/tamabot/)"
signature_add = "^^Parent ^^commentor ^^can [^^delete ^^this ^^post](/message/compose?to=tamabot&subject=tamabot%20deletion&message=%2Bdelete+___CID___), ^^and ^^OP ^^can ^^tell ^^bot ^^to [^^ignore ^^this ^^entire ^^thread](/message/compose?to=tamabot&subject=tamabot%20ignore&message=%2Bignore+___PID___)"
pattern_icon = re.compile('\[.*?]\((?:#m)?(?:#i)?\/?(?P<sid>s\d+)?\/?(?P<cid>c\d+)?\/(?P<id>\d+)?( "[^"]+?")?\)')
pattern_padxsim = ur'puzzledragonx\.com/[^/]+/simulator.asp\?q=([\d]+)\.\d+\.\d+\.\d+\.\d+\.\d+\.\d+\.\.([\d]+)\.\d+\.\d+\.\d+\.\d+\.\d+\.\d+\.\.([\d]+)\.\d+\.\d+\.\d+\.\d+\.\d+\.\d+\.\.([\d]+)\.\d+\.\d+\.\d+\.\d+\.\d+\.\d+\.\.([\d]+)\.\d+\.\d+\.\d+\.\d+\.\d+\.\d+\.\.([\d]+)\.\d+\.\d+\.\d+\.\d+\.\d+\.\d+'
pattern_flair_call = ur'id (?:is )?(?:in )?(?:my )?(flair|flare)'

loop = 0

# read in processed queue files in case of script crash
read_queue_file(ignored_submissions_file, ignored_submissions)
read_queue_file(processed_submissions_file, processed_submissions)
read_queue_file(processed_comments_file, processed_comments)

class PADXData():
    """
    PADX Data class
    gets HTML of PADX page for given monster ID and parses out relevant data
    """
    def __init__(self, id):
        self.REQUESTING = True
        self.id = id
        self.generated = 0
        while self.REQUESTING:
            try:
                self.html = requests.get("http://www.puzzledragonx.com/en/monster.asp?n=%s" % self.id).content
                self.parsed_html = BeautifulSoup(self.html, from_encoding="utf-8")
                self.name = self.parsed_html.body.find('h1').text
                self.get_data()
                self.generated = int(strftime("%Y%m%d", gmtime()))
                self.status = 1
                self.REQUESTING = False
                self.html = None
                self.parsed_html = None
                if self.name == "Puzzle Dragon X":
                    self.status = 0
            except Exception as e:
                log_warning(e)
                self.status = 0
                sleep(SLEEP_LONG)

    def get_data(self):
        """ get leader and active skill data """
        self.type = []
        self.type_formatted = []
        self.ls_id, self.ls_name, self.ls_text = "0", "None", "None"
        self.as_id, self.as_name, self.as_text = "0", "None", "None"
        self.acd_text = ""
        self.awk = []
        tds = self.parsed_html.body.find_all('td', class_='ptitle')
        for td in tds:
            if td.text == 'Type:':
                td_next = td.find_next_sibling()
                self.type = td_next.text.split(" / ")
                self.type_formatted = self.type
                for a, t in enumerate(self.type_formatted):
                    tempa = t.split()
                    for b, temp in enumerate(tempa):
                        tempa[b] = "^" + temp
                    self.type_formatted[a] = " ".join(tempa)
                    if a < len(self.type_formatted) - 1:
                        self.type_formatted[a] = self.type_formatted[a] + " ^/"

        tds = self.parsed_html.body.find_all('td', class_='title')
        for td in tds:
            if td.text == 'Leader Skill:':
                td_next = td.find_next_sibling()
                self.ls_name = td_next.text
                if td_next.a is not None:
                    m = re.search(ur'leaderskill\.asp\?s=(\d+)', td_next.a.get('href'))
                    if m:
                        self.ls_id = m.group(1)
                    self.ls_text = td.parent.find_next_sibling().find('td', class_='value-end').text
            elif td.text == 'Active Skill:':
                td_next = td.find_next_sibling()
                self.as_name = td_next.text
                if td_next.a is not None:
                    m = re.search(ur'skill\.asp\?s=(\d+)', td_next.a.get('href'))
                    if m:
                        self.as_id = m.group(1)
                    self.as_text = td.parent.find_next_sibling().find('td', class_='value-end').text
            elif td.text == 'Cool Down:':
                td_next = td.find_next_sibling()
                self.acd_text = td_next.text
            elif td.text == 'Awoken Skills:':
                td_next = td.find_next_sibling()
                td_next_as = td_next.find_all('a')
                for td_next_a in td_next_as:
                    m = re.search(ur'awokenskill\.asp\?s=(\d+)', td_next_a.get('href'))
                    if m:
                        self.awk.append(int(m.group(1)) - 1)

def process_monsters(i, n, listed, msg):
    """
    checks monster ID i against stored/previously generated PADXData entries;
    reloads data from PADX if a day old
    """
    if i == 0 or i in listed:
        return (n, listed, msg)
    if i not in padx_storage:
        padx_storage[i] = PADXData(i)
        processed_monsters.append(i)
        sleep(1)
    if padx_storage[i].status == 1:
        if int(strftime("%Y%m%d", gmtime())) - padx_storage[i].generated > 0:
            padx_storage[i] = PADXData(i)
        msg = table_output(padx_storage[i], msg)
        processed_monsters.remove(i)
        processed_monsters.append(i)
        n = n + 1
    listed.append(i)
    return (n, listed, msg)

def table_output(padx, msg):
    """
    uses PADX data to build reddit post output; automatically creates a new
    post if the # of chars > 10000 (reddit limit); automatically apends bot
    signature
    """
    table_header = "%s###### &#009;\n#### &#009;\n##### &#009;\n|||Expanded Monster Information ___MTABLE___ [hover to view]|\n:--:|--:|:--\n" % signature_intro
    if len(msg) == 0:
        msg.append(table_header)
    i = len(msg) - 1
    sid = int(padx.id) / 200
    cid = int(padx.id) % 200
    msg_temp = "[](#I/S%02d/C%03d/%s \"%s\")|" % (sid, cid, padx.id, padx.name)
    msg_temp = "%s#%s|**[%s](http://www.puzzledragonx.com/en/monster.asp?n=%s)**\n" % (msg_temp, padx.id, padx.name, padx.id)
    if len(padx.type_formatted) > 0:
        msg_temp = "%s%s" % (msg_temp, padx.type_formatted[0])
    else:
        msg_temp = "%s " % msg_temp
    if padx.ls_id != '0':
        msg_temp = "%s|Leader|**[%s](http://www.puzzledragonx.com/en/leaderskill.asp?s=%s)**: %s\n" % (msg_temp, padx.ls_name, padx.ls_id, padx.ls_text)
    else:
        msg_temp = "%s|Leader|**%s**\n" % (msg_temp, padx.ls_name)
    if len(padx.type_formatted) > 1:
        msg_temp = "%s%s" % (msg_temp, padx.type_formatted[1])
    else:
        msg_temp = "%s " % msg_temp
    if padx.as_id != '0':
        msg_temp = "%s |Active|**[%s](http://www.puzzledragonx.com/en/skill.asp?s=%s)**: %s (%s)\n" % (msg_temp, padx.as_name, padx.as_id, padx.as_text, padx.acd_text)
    else:
        msg_temp = "%s |Active|**%s**\n" % (msg_temp, padx.as_name)
    if len(padx.awk) != 0:
        awk_temp = ""
        for a in padx.awk:
            awk_temp = "%s[](#I/misc/C%03d/) " % (awk_temp, a)
        msg_temp = "%s |Awoken|%s\n" % (msg_temp, awk_temp)
    else:
        msg_temp = "%s |Awoken|None\n" % (msg_temp)

    if len(msg[i]) + len(msg_temp) + len(signature) + len(signature_add) > MSG_LEN_LIMIT:
        log_msg("message long... splitting")
        update_db(log_coll, stat_coll, 'SPLIT', '', '')
        msg.append(table_header)
        msg[i + 1] = msg[i + 1] + msg_temp
    else:
        msg[i] = msg[i] + msg_temp
    return msg

def flair_fix_repl(match):
    return '%s,%s,%s' % (match.group(1), match.group(2), match.group(3))

def check_posts(posts, post_type, forced):
    """
    main function for checking submissions and replies made in subreddit;
    checks for iconified monster links and 'flair in ID' messages
    """
    for post in posts:
        called = False
        # skip if post made by bot
        if str(post.author) == USERNAME:
            continue

        # check processed posts and ignore lists
        if forced is False:
            if post_type == 'SUBMISSIONS':
                if str(post.id) in processed_submissions:
                    continue
                if str(post.id) in ignored_submissions:
                    continue
            elif post_type == 'COMMENTS':
                if str(post.id) in processed_comments:
                    continue
                if str(post.link_id)[3:] in ignored_submissions:
                    continue

        if post_type == 'SUBMISSIONS':
            temp_text = post.selftext.encode('utf-8')
        elif post_type == 'COMMENTS':
            temp_text = post.body.encode('utf-8')

        # check callouts
        if temp_text.find('-/u/tamabot') > -1:
            log_msg('Found negative callout')
            pass
        elif temp_text.find('/u/tamabot') > -1:
            log_msg('Found callout request!')
            called = True

        # check for Monster Icons - disabled
        # if called is True or forced is True:
        #     n, temp_id, msg, listed = 0, 0, [], []
        #     for m in pattern_icon.finditer(temp_text):
        #         e = m.groupdict()
        #         if e['id'] is not None:
        #             temp_id = int(e['id'])
        #         elif e['sid'] is not None and e['cid'] is not None:
        #             temp_id = (int(e['sid'][1:]) * 50) + int(e['cid'][1:]) + 1
        #         n, listed, msg = process_monsters(temp_id, n, listed, msg)

        #     # check for PADX Team
        #     m = re.findall(pattern_padxsim, temp_text, re.I | re.U)
        #     if m:
        #         for e in m:
        #             for i in e:
        #                 temp_id = int(i)
        #                 n, listed, msg = process_monsters(temp_id, n, listed, msg)

        #     # create Monster Table
        #     if n > 0:
        #         create_post(post, msg, post_type, 'MONSTER TABLE')

        # check for Flair Call
        m = re.search(pattern_flair_call, temp_text, re.I | re.U)
        if m or called is True or forced is True:
            msg = []
            if post.author_flair_text is not None:
                msg.append("Found %s's flair: **%s**\n" % (str(post.author), post.author_flair_text))
                create_post(post, msg, post_type, 'FLAIR ID')

        # update processed posts list
        if post_type == 'SUBMISSIONS':
            check_processed_posts(processed_submissions, str(post.id), LIMIT)
        elif post_type == 'COMMENTS':
            check_processed_posts(processed_comments, str(post.id), LIMIT)
    sleep(SLEEP_LONG)

def check_self_posts(posts):
    """
    function for checking comment score of posts made by bot; delete if score
    is less than 1 (downvoted)
    """
    try:
        for post in posts:
            if post.score < 1:
                delete_post(post, 'SCORE', '', '')
        sleep(SLEEP_LONG)
    except Exception as e:
        log_error(e)

def check_pm(msgs):
    """
    function for checking bot's private messages; delete if parent commentor
    (or subreddit moderator) has requested post deletion; stops bot if
    moderator has requested a halt
    """
    for msg in msgs:
        # check for delete request
        m = re.search(ur'^\+delete\s(.+?)$', msg.body.lower())
        if m:
            id = "t1_%s" % m.group(1)
            c = r.get_info(thing_id = id)
            if c is not None:
                c_parent = r.get_info(thing_id = c.parent_id)
                if c_parent.author is None:
                    delete_post(c, 'PM', '', msg.author.name)
                else:
                    if msg.author.name == c_parent.author.name or msg.author.name in mod_list or msg.author.name == 'mrmin123':
                        if "Please request this post to be deleted to un-ignore." in c.body:
                            log_msg("Un-ignoring posts under %s by %s's request" % (c_parent.permalink, msg.author.name))
                            update_db(log_coll, stat_coll, 'UNIGNORE', c_parent.permalink, msg.author.name)
                            try:
                                ignored_submissions.remove(str(c.parent_id)[3:])
                            except Exception as e:
                                log_error(e)
                        delete_post(c, 'PM', c_parent.permalink, msg.author.name)
                    else:
                        log_warning("Incorrect delete request from %s for %s" % (msg.author.name, c.permalink))
                        update_db(log_coll, stat_coll, 'DEL_BAD', c.permalink, msg.author.name)

        # check for ignore request
        m = re.search(ur'^\+ignore\s(.+?)$', msg.body.lower())
        if m:
            id = "t3_%s" % m.group(1)
            c = r.get_info(thing_id = id)
            if c.author is not None and (msg.author.name == c.author.name or msg.author.name in mod_list or msg.author.name == 'mrmin123'):
                if m.group(1) not in ignored_submissions:
                    ignored_submissions.append(m.group(1))
                    log_msg("Ignoring posts under %s by %s's request" % (c.short_link, msg.author.name))
                    update_db(log_coll, stat_coll, 'IGNORE_PM', c.short_link, msg.author.name)
                    temp_msg = "%s\nI am ignoring any new posts in this thread by OP/moderator's request! Please request this post to be deleted to un-ignore.\n" % signature_intro
                    create_post(c, [temp_msg], 'SUBMISSIONS', 'IGNORE_POST')
            else:
                if type(c) is praw.objects.Submission:
                    tempLink = c.short_link
                elif type(c) is praw.objects.Comment:
                    tempLink = c.permalink
                else:
                    tempLink = m.group(1)
                log_warning("Incorrect ignore request from %s for %s" % (msg.author.name, tempLink))
                update_db(log_coll, stat_coll, 'IGNORE_BAD', tempLink, msg.author.name)

        # check for revisit
        m = re.search(ur'^\+visit\s(.+?)$', msg.body.lower())
        if m:
            temp_type = 'SUBMISSIONS'
            id = "t3_%s" % m.group(1)
            c = r.get_info(thing_id = id)
            if c is None:
                temp_type = 'COMMENTS'
                id = id = "t1_%s" % m.group(1)
                c = r.get_info(thing_id = id)
            if c is not None and c.subreddit.display_name.lower() == SUBREDDIT.lower() and (msg.author.name == c.author.name or msg.author.name in mod_list or msg.author.name == 'mrmin123'):
                log_msg("Revisiting %s under %s's request" % (c.permalink, msg.author.name))
                update_db(log_coll, stat_coll, 'REVISIT', c.permalink, msg.author.name)
                check_posts([c], temp_type, True)
            else:
                if type(c) is praw.objects.Submission:
                    tempLink = c.short_link
                elif type(c) is praw.objects.Comment:
                    tempLink = c.permalink
                else:
                    tempLink = m.group(1)
                log_msg("Incorrect revisit request for %s by %s" % (tempLink, msg.author.name))
                update_db(log_coll, stat_coll, 'REVISIT_BAD', tempLink, msg.author.name)

        # check for moderator halt request
        if msg.author.name in mod_list or msg.author.name == 'mrmin123':
            m = re.search(ur'^\+halt$', msg.body.lower())
            if m:
                msg.mark_as_read()
                log_error("Bot halt requested by %s" % msg.author.name)
                update_db(log_coll, stat_coll, 'HALT', '', msg.author.name)
                exit()
        msg.mark_as_read()
        sleep(SLEEP)
    sleep(SLEEP_LONG)

def create_post(post, msg, post_type, msg_type):
    """
    function for posting to subreddit; separate post for long monster table
    posts; self-edits signature for easy delete request PM link
    """
    try:
        for i, m in enumerate(msg):
            if len(msg) > 1:
                m = m.replace('___MTABLE___', "(%s of %s)" % (i + 1, len(msg)))
            else:
                m = m.replace('___MTABLE___', "")
            if post_type == 'SUBMISSIONS':
                if debug:
                    print m + signature
                else:
                    c = post.add_comment(m + signature_intro + signature)
                    log_msg("Made a %s comment in %s" % (msg_type, post.short_link))
                    update_db(log_coll, stat_coll, msg_type, post.short_link, '')
            elif post_type == 'COMMENTS':
                if debug:
                    print m + signature
                else:
                    c = post.reply(m + signature)
                    log_msg("Made a %s reply to %s" % (msg_type, post.permalink))
                    update_db(log_coll, stat_coll, msg_type, post.permalink, '')
            sig_temp = signature_add.replace('___CID___', str(c.id))
            sig_temp = sig_temp.replace('___PID___', str(c.link_id)[3:])
            if not debug:
                sleep(SLEEP)
                m_tmp = c.body.replace('^^Processing...', sig_temp)
                m_tmp = m_tmp.replace('&amp;#', '&#')
                r.get_info(thing_id='t1_' + str(c.id)).edit(m_tmp)
            sleep(SLEEP_LONG)
    except Exception as e:
        log_error(e)

def delete_post(post, type, parent_url, user):
    """
    function for deleting own post
    """
    try:
        if type == 'SCORE':
            log_msg("Deleting post under %s due to downvote" % parent_url)
            update_db(log_coll, stat_coll, 'DEL_SCORE', parent_url, user)
        if type == 'PM':
            log_msg("Deleting post under %s due to PM request from %s" % (parent_url, user))
            update_db(log_coll, stat_coll, 'DEL_PM', parent_url, user)
        post.delete()
        sleep(SLEEP)
    except Exception as e:
        log_error(e)

def get_mods(sub):
    """
    function for grabbing mod list of subreddit (only works when one
    subreddit is specified)
    """
    mod_list = []
    try:
        mods = r.get_moderators(sub).children
        for mod in mods:
            mod_list.append(str(mod))
        if debug:
            print "mods: %s" % ', '.join(mod_list)
    except Exception as e:
        log_error(e)

r = praw.Reddit(user_agent = user_agent)

# log in
LOGGING_IN = True
while LOGGING_IN:
    try:
        r.login(USERNAME, PASSWORD)
        log_success("Login Successful")
        LOGGING_IN = False
        sleep(SLEEP)
    except praw.errors.InvalidUserPass:
        log_error("Incorrect login information")
        exit()
    except Exception as e:
        log_error(e)
        sleep(SLEEP_LONG)

# get subreddit
try:
    sub = r.get_subreddit(SUBREDDIT)
except Exception as e:
    log_error(e)
    exit()

try:
    mdb = pymongo.MongoClient(MONGO_URL, MONGO_PORT)
    db = mdb[MONGO_DB]
    log_coll = db['log']
    stat_coll = db['stat']
    reset_db(stat_coll)
except Exception as e:
    log_error(e)
    exit()

# begin primary bot loop
RUNNING = True
while RUNNING:
    try:
        # update moderators list every so often
        if (loop + 10000) % 10000 == 0:
            get_mods(SUBREDDIT)
        loop = loop + 1

        # check for -1 scores
        #bot_user = r.get_redditor(USERNAME)
        #check_self_posts(bot_user.get_comments(limit = None))

        # check PMs for delete or halt requests
        check_pm(r.get_unread(limit = None))
        if not debug:
            update_queue_file(ignored_submissions_file, ignored_submissions)

        # check submissions/self posts
        check_posts(sub.get_new(limit = LIMIT), 'SUBMISSIONS', False)
        if not debug:
            update_queue_file(processed_submissions_file, processed_submissions)

        # check reply/comments
        check_posts(sub.get_comments(limit = LIMIT), 'COMMENTS', False)
        if not debug:
            update_queue_file(processed_comments_file, processed_comments)

        # clean up stored PADX data
        while len(processed_monsters) > MONSTER_LIMIT:
            remove_id = processed_monsters.popleft()
            del padx_storage[remove_id]
    except requests.exceptions.HTTPError:
        log_error("HTTP Error: Gateway timeout/Origin Down")
        sleep(SLEEP_LONG)
    except Exception as e:
        log_error(e)
