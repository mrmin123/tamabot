# -*- coding: utf-8 -*-

import praw, time, re, requests
from config import USERNAME, PASSWORD, SUBREDDIT
from util import check_processed_posts, read_queue_file, update_queue_file, log_msg, log_success, log_warning, log_error
from collections import deque

user_agent = ("rPuzzlesAndDragonsBot 1.0 by /u/mrmin123")

# globals
LIMIT = 10
SLEEP = 3
SLEEP_LONG = 5
SLEEP_UBER = 1000
mod_list = []
padx_storage = {}
processed_monsters = deque([])
processed_submissions = deque([])
processed_comments = deque([])
processed_submissions_file = 'processed_submissions.txt'
processed_comments_file = 'processed_comments.txt'
signature = "\n^Processing... ^(auto-delete ^on ^comment ^score ^below ^0) ^|| ^Use ^with ^[Iconify](http://tamadra.github.io/iconify/) ^|| ^[FAQ/Source](http://google.com/)"
signature_add = "^Parent ^commentor ^can ^[delete](/message/compose?to=tamabot&subject=tamabot%20deletion&message=%2Bdelete+___ID___) ^this ^post"
pattern_icon = ur'\[(?:\\\[.+?\] )?\]\((?:#m)?\/(\d+) ?\"?([^\"]+)??\"?\)'
pattern_flair_call = ur'id (?:is )?(?:in )?(?:my )?flair'
pattern_flair_user = ur'(?<!\d)(\d{3})(?:[,. ])?(\d{3})(?:[,. ])?(\d{3})(?!\d)'
loop = 0

# read in processed queue files in case of script crash
read_queue_file(processed_submissions_file, processed_submissions)
read_queue_file(processed_comments_file, processed_comments)

class PADXData():
    """
    PADX Data class
    gets HTML of PADX page for given monster ID and parses out relevant data
    """
    pattern_name = ur'h1>(.+?)<\/h1'
    pattern_as = ur'>Active Skill:.+?skill.asp\?s=(\d+)\">[^>]+?>(.+?)<\/.+?Effects:.+?\">(.+?)<\/'
    pattern_acd = ur'>Cool Down:(?:[^>]+>){2}(.+?)<'
    pattern_ls = ur'>Leader Skill:.+?leaderskill.asp\?s=(\d+)\">[^>]+?>(.+?)<\/.+?Effects:.+?\">(.+?)<\/'

    def __init__(self, id, name):
        self.REQUESTING = True
        self.id = id
        self.name = name
        while self.REQUESTING:
            try:
                self.html = requests.get("http://www.puzzledragonx.com/en/monster.asp?n=%s" % self.id).content
                if self.name == '':
                    m = re.search(self.pattern_name, self.html, re.I | re.U)
                    if m:
                        self.name = m.group(1)
                    else:
                        self.name = "Monster ID (%s)" % self.id
                self.get_ls()
                self.get_as()
                self.get_acd()
                self.status = 1
                self.REQUESTING = False
            except Exception as e:
                log_warning(e)
                self.status = 0
                time.sleep(SLEEP_LONG)

    def get_ls(self):
        """ get leader skill id, name, and description """
        m = re.search(self.pattern_ls, self.html, re.I | re.U)
        if m:
            self.ls_id, self.ls_name, self.ls_text = m.group(1), m.group(2), m.group(3)
        else :
            self.ls_id, self.ls_name, self.ls_text = "0", "None", "None"

    def get_as(self):
        """ get active skill id, name, and description """
        m = re.search(self.pattern_as, self.html, re.I | re.U)
        if m:
            self.as_id, self.as_name, self.as_text = m.group(1), m.group(2), m.group(3)
        else :
            self.as_id, self.as_name, self.as_text = "0", "None", "None"

    def get_acd(self):
        """ get active skill cooldown """
        m = re.search(self.pattern_acd, self.html, re.I | re.U)
        if m:
            self.acd_text = m.group(1)
        else:
            self.acd_text = "None"

def table_output(padx, msg):
    """
    uses PADX data to build reddit post output; automatically creates a new post
    if the # of chars > 10000 (reddit limit); automatically apends bot signature
    """
    table_header = "||Monster Table ___MTABLE___ [hover to view]|\n:--:|:--\n"
    if len(msg) == 0:
        msg.append(table_header)
    i = len(msg) - 1
    msg_temp = "[](/%s \"%s\")|" % (padx.id, padx.name)
    msg_temp = "%s%s. **[%s](http://www.puzzledragonx.com/en/monster.asp?n=%s)**\n" % (msg_temp, padx.id, padx.name, padx.id)
    if padx.ls_id != '0':
        msg_temp = "%s |Leader: **[%s](http://www.puzzledragonx.com/en/leaderskill.asp?s=%s)**: %s\n" % (msg_temp.encode('utf-8'), padx.ls_name, padx.ls_id, padx.ls_text)
    else:
        msg_temp = "%s |Leader: **%s**\n" % (msg_temp.encode('utf-8'), padx.ls_name)
    if padx.as_id != '0':
        msg_temp = "%s |Active: **[%s](http://www.puzzledragonx.com/en/skill.asp?s=%s)**: %s (%s)\n" % (msg_temp, padx.as_name, padx.as_id, padx.as_text, padx.acd_text)
    else:
        msg_temp = "%s |Active: **%s**\n" % (msg_temp.encode('utf-8'), padx.as_name)

    if len(msg[i]) + len(msg_temp) + len(signature) > 9999:
        msg.append(table_header)
        msg[i + 1] = msg[i + 1] + msg_temp
    else:
        msg[i] = msg[i] + msg_temp
    return msg

def check_posts(posts, post_type):
    """
    main function for checking submissions and replies made in subreddit; checks
    for iconified monster links and 'flair in ID' messages
    """
    for post in posts:
        # skip if post made by bot
        if str(post.author) == USERNAME:
            continue

        # check processed posts list
        if post_type == 'SUBMISSIONS':
            if str(post.id) in processed_submissions:
                continue
        elif post_type == 'COMMENTS':
            if str(post.id) in processed_comments:
                continue

        # check for Monster Icons
        if post_type == 'SUBMISSIONS':
            m = re.findall(pattern_icon, post.selftext)
        elif post_type == 'COMMENTS':
            m = re.findall(pattern_icon, post.body)
        if m:
            n, msg, listed = 0, [], []
            for e in m:
                if e[0] == '0' or e[0] in listed:
                    continue
                if e[0] not in padx_storage:
                    padx_storage[e[0]] = PADXData(e[0], e[1])
                    processed_monsters.append(e[0])
                    time.sleep(1)
                if padx_storage[e[0]].status == 1:
                    msg = table_output(padx_storage[e[0]], msg)
                    processed_monsters.remove(e[0])
                    processed_monsters.append(e[0])
                    n = n + 1
                listed.append(e[0])
            if n > 0:
                create_post(post, msg, post_type, 'MONSTER TABLE')

        # check for Flair Call
        if post_type == 'SUBMISSIONS':
            m = re.search(pattern_flair_call, post.selftext, re.I | re.U)
        elif post_type == 'COMMENTS':
            m = re.search(pattern_flair_call, post.body, re.I | re.U)
        if m:
            msg = []
            m2 = re.search(pattern_flair_user, str(post.author_flair_text), re.I | re.U)
            if m2:
                msg.append("Found %s's ID in flair: %s%s%s\n" % (str(post.author), m2.group(1), m2.group(2), m2.group(3)))
                create_post(post, msg, post_type, 'FLAIR ID')

        # update processed posts list
        if post_type == 'SUBMISSIONS':
            check_processed_posts(processed_submissions, str(post.id), LIMIT)
        elif post_type == 'COMMENTS':
            check_processed_posts(processed_comments, str(post.id), LIMIT)
    time.sleep(SLEEP_LONG)

def check_self_posts(posts):
    """
    function for checking comment score of posts made by bot; delete if score is
    less than 1 (downvoted)
    """
    try:
        for post in posts:
            if post.score < 1:
                delete_post(post, 'SCORE')
        time.sleep(SLEEP_LONG)
    except Exception as e:
        log_error(e)

def check_pm(msgs):
    """
    function for checking bot's private messages; delete if parent commentor
    (or subreddit moderator) has requested post deletion; stops bot if moderator
    has requested a halt
    """
    for msg in msgs:
        # check for delete request
        m = re.search(ur'^\+delete\s(.+?)$', msg.body.lower())
        if m:
            id = "t1_%s" % m.group(1)
            c = r.get_info(thing_id = id)
            c_parent = r.get_info(thing_id = c.parent_id)
            if msg.author.name == c_parent.author.name or msg.author.name in mod_list or msg.author.name == 'mrmin123' :
                delete_post(c, 'PM')
            else:
                log_warning("Incorrect delete request from /u/%s for %s" % (msg.author.name, m.group[1]))

        # check for moderator halt request
        if msg.author.name in mod_list or msg.author.name == 'mrmin123':
            m = re.search(ur'^\+halt$', msg.body.lower())
            if m:
                msg.mark_as_read()
                log_error("Bot halt requested by %s" % msg.author.name)
                exit()
        msg.mark_as_read()
        time.sleep(SLEEP)
    time.sleep(SLEEP_LONG)

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
                c = post.add_comment(m + signature)
                log_msg("Made a %s comment in %s" % (msg_type, post.short_link))
            elif post_type == 'COMMENTS':
                c = post.reply(m + signature)
                log_msg("Made a %s reply in %s" % (msg_type, post.permalink))
            sig_temp = signature_add.replace('___ID___', str(c.id))
            time.sleep(SLEEP)
            r.get_info(thing_id='t1_' + str(c.id)).edit(c.body.replace('^Processing...', sig_temp))
            time.sleep(SLEEP_UBER)
    except Exception as e:
        log_error(e)

def delete_post(post, type):
    """
    function for deleting own post
    """
    try:
        if type == 'SCORE':
            log_msg("Deleting post under %s due to downvote" % post.parent_id)
        if type == 'PM':
            log_msg("Deleting post under %s due to PM request" % post.parent_id)
        post.delete()
        time.sleep(SLEEP)
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
        time.sleep(SLEEP_LONG)
    except praw.errors.InvalidUserPass:
        log_error("Incorrect login information")
        exit()
    except Exception as e:
        log_error(e)
        time.sleep(SLEEP_LONG)

# get subreddit
try:
    sub = r.get_subreddit(SUBREDDIT)
except Exception as e:
    log_error(e)
    exit()

# begin primary bot loop
RUNNING = True
while RUNNING:
    # update moderators list every so often
    if (loop + 10000) % 10000 == 0:
        get_mods(SUBREDDIT)
    loop = loop + 1

    # check for -1 scores
    bot_user = r.get_redditor(USERNAME)
    check_self_posts(bot_user.get_comments(limit = None))

    # check PMs for delete or halt requests
    check_pm(r.get_unread(limit = None))

    # check submissions/self posts
    check_posts(sub.get_new(limit = LIMIT), 'SUBMISSIONS')
    update_queue_file(processed_submissions_file, processed_submissions)

    # check reply/comments
    check_posts(sub.get_comments(limit = LIMIT), 'COMMENTS')
    update_queue_file(processed_comments_file, processed_comments)

    # clean up stored PADX data
    while len(processed_monsters) > 200:
        processed_monsters.popleft()
