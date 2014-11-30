# -*- coding: utf-8 -*-

import praw, re, requests
from config import USERNAME, PASSWORD, SUBREDDIT
from util import check_processed_posts, check_ignored_submissions, read_queue_file, update_queue_file, log_msg, log_success, log_warning, log_error
from collections import deque
from time import sleep

user_agent = ("rPuzzlesAndDragonsBot 1.1 by /u/mrmin123")

# globals
LIMIT = 15
SLEEP = 3
SLEEP_LONG = 15
mod_list = []
padx_storage = {}
processed_monsters = deque([])
processed_submissions = deque([])
processed_comments = deque([])
processed_submissions_file = 'processed_submissions.txt'
processed_comments_file = 'processed_comments.txt'
ignored_submissions = deque([])
ignored_submissions_file = 'ignored_submissions.txt'
intro = "^This ^bot ^posts ^information ^from ^PADX ^for ^iconified ^monsters, ^as ^well ^as ^IDs ^from ^user ^flairs. ^For ^more ^information, ^read ^the ^[Github](https://github.com/mrmin123/tamabot/) ^page.\n"
signature = "\n^Processing... ^|| ^Use ^with ^[Iconify](http://tamadra.com/iconify) ^|| ^[Source/contact](https://github.com/mrmin123/tamabot/)"
signature_add = "^Parent ^commentor ^can ^[delete](/message/compose?to=tamabot&subject=tamabot%20deletion&message=%2Bdelete+___CID___) ^this ^post ^|| ^OP ^can ^tell ^Tamabot ^to ^[ignore](/message/compose?to=tamabot&subject=tamabot%20ignore&message=%2Bignore+___PID___) ^this ^thread ^and ^all ^child ^posts"
pattern_icon = re.compile('\[.*?]\((?:#m)?(?:#i)?\/?(?P<sid>s\d+)?\/?(?P<cid>c\d+)?\/(?P<id>\d+)? ?\"?([^\"]+)??\"?\)')
pattern_flair_call = ur'id (?:is )?(?:in )?(?:my )?flair'
pattern_flair_user = ur'(?<!\d)(\d{3})(?:[,. ])?(\d{3})(?:[,. ])?(\d{3})(?!\d)'
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
    pattern_name = ur'h1>(.+?)<\/h1'
    pattern_as = ur'>Active Skill:.+?skill.asp\?s=(\d+)\">[^>]+?>(.+?)<\/.+?Effects:.+?\">(.+?)<\/'
    pattern_acd = ur'>Cool Down:(?:[^>]+>){2}(.+?)<'
    pattern_ls = ur'>Leader Skill:.+?leaderskill.asp\?s=(\d+)\">[^>]+?>(.+?)<\/.+?Effects:.+?\">(.+?)<\/'
    pattern_awk_area = ur'Awoken Skills:(.+?)<\/tr>'
    pattern_awk = ur'awokenskill.asp\?s=(\d+).+?title="(.+)\n'

    def __init__(self, id):
        self.REQUESTING = True
        self.id = id
        self.awk = []
        while self.REQUESTING:
            try:
                self.html = requests.get("http://www.puzzledragonx.com/en/monster.asp?n=%s" % self.id).content
                m = re.search(self.pattern_name, self.html, re.I | re.U)
                if m:
                    self.name = m.group(1)
                else:
                    self.name = "Monster #%s" % self.id
                self.get_ls()
                self.get_as()
                self.get_acd()
                self.get_awk()
                self.status = 1
                self.REQUESTING = False
                if self.name == "Puzzle Dragon X":
                    self.status = 0
            except Exception as e:
                log_warning(e)
                self.status = 0
                sleep(SLEEP_LONG)

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

    def get_awk(self):
        """ get awoken skills """
        m = re.search(self.pattern_awk_area, self.html, re.I | re.U | re.S)
        if m:
            n = re.findall(self.pattern_awk, m.group(1), re.I | re.U)
            if n:
                for e in n:
                    self.awk.append([int(e[0]) - 1, e[1].strip()])


def table_output(padx, msg):
    """
    uses PADX data to build reddit post output; automatically creates a new post
    if the # of chars > 10000 (reddit limit); automatically apends bot signature
    """
    table_header = "%s###### &#009;\n#### &#009;\n##### &#009;\n|||Expanded Monster Information ___MTABLE___ [hover to view]|\n:--:|--:|:--\n" % intro
    if len(msg) == 0:
        msg.append(table_header)
    i = len(msg) - 1
    sid = int(padx.id) / 50
    cid = int(padx.id) % 50
    msg_temp = "[](#i/s%02d/c%02s/%s \"%s\")|" % (sid, cid, padx.id, padx.name.decode('utf-8'))
    msg_temp = "%s#%s|**[%s](http://www.puzzledragonx.com/en/monster.asp?n=%s)**\n" % (msg_temp, padx.id, padx.name.decode('utf-8'), padx.id)
    if padx.ls_id != '0':
        msg_temp = "%s |Leader|**[%s](http://www.puzzledragonx.com/en/leaderskill.asp?s=%s)**: %s\n" % (msg_temp, padx.ls_name.decode('utf-8'), padx.ls_id, padx.ls_text.decode('utf-8'))
    else:
        msg_temp = "%s |Leader|**%s**\n" % (msg_temp, padx.ls_name)
    if padx.as_id != '0':
        msg_temp = "%s |Active|**[%s](http://www.puzzledragonx.com/en/skill.asp?s=%s)**: %s (%s)\n" % (msg_temp, padx.as_name.decode('utf-8'), padx.as_id, padx.as_text.decode('utf-8'), padx.acd_text)
    else:
        msg_temp = "%s |Active|**%s**\n" % (msg_temp, padx.as_name)
    if len(padx.awk) != 0:
        awk_temp = ""
        for a in padx.awk:
            awk_temp = "%s[](#i/awoken/c%02d/ '%s') " % (awk_temp, a[0], a[1])
        msg_temp = "%s |Awoken|%s\n" % (msg_temp, awk_temp)
    else:
        msg_temp = "%s |Awoken|None\n" % (msg_temp)

    if len(msg[i]) + len(msg_temp) + len(signature) > 9700:
        log_msg("message long... splitting")
        msg.append(table_header)
        msg[i + 1] = msg[i + 1] + msg_temp
    else:
        msg[i] = msg[i] + msg_temp
    return msg

def check_posts(posts, post_type, forced):
    """
    main function for checking submissions and replies made in subreddit; checks
    for iconified monster links and 'flair in ID' messages
    """
    for post in posts:
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

        # check for Monster Icons
        n, temp_id, msg, listed = 0, 0, [], []
        if post_type == 'SUBMISSIONS':
            temp_text = post.selftext
        elif post_type == 'COMMENTS':
            temp_text = post.body
        for m in pattern_icon.finditer(temp_text):
            e = m.groupdict()
            if e['id'] is not None:
                temp_id = int(e['id'])
            elif e['sid'] is not None and e['cid'] is not None:
                temp_id = (int(e['sid'][1:]) * 50) + int(e['cid'][1:]) + 1
            if temp_id == 0 or temp_id in listed:
                continue
            if temp_id not in padx_storage:
                padx_storage[temp_id] = PADXData(temp_id)
                processed_monsters.append(temp_id)
                sleep(1)
            if padx_storage[temp_id].status == 1:
                msg = table_output(padx_storage[temp_id], msg)
                processed_monsters.remove(temp_id)
                processed_monsters.append(temp_id)
                n = n + 1
            listed.append(temp_id)
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
                msg.append("%s\nFound %s's ID in flair: %s,%s,%s\n" % (intro, str(post.author), m2.group(1), m2.group(2), m2.group(3)))
                create_post(post, msg, post_type, 'FLAIR ID')

        # update processed posts list
        if post_type == 'SUBMISSIONS':
            check_processed_posts(processed_submissions, str(post.id), LIMIT)
        elif post_type == 'COMMENTS':
            check_processed_posts(processed_comments, str(post.id), LIMIT)
    sleep(SLEEP_LONG)

def check_self_posts(posts):
    """
    function for checking comment score of posts made by bot; delete if score is
    less than 1 (downvoted)
    """
    try:
        for post in posts:
            if post.score < 1:
                delete_post(post, 'SCORE')
        sleep(SLEEP_LONG)
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
            if c_parent.author is None:
                delete_post(c, 'PM')
            else:
                if msg.author.name == c_parent.author.name or msg.author.name in mod_list or msg.author.name == 'mrmin123':
                    if "Please request this post to be deleted to un-ignore." in c.body:
                        log_msg("Un-ignoring posts under %s by %s's request" % (c.parent_id, msg.author.name))
                        try:
                            ignored_submissions.remove(str(c.parent_id)[3:])
                        except Exception as e:
                            log_error(e)
                    delete_post(c, 'PM')
                else:
                    log_warning("Incorrect delete request from %s for %s" % (msg.author.name, m.group(1)))

        # check for ignore request
        m = re.search(ur'^\+ignore\s(.+?)$', msg.body.lower())
        if m:
            id = "t3_%s" % m.group(1)
            c = r.get_info(thing_id = id)
            if c_parent.author is not None and (msg.author.name == c.author.name or msg.author.name in mod_list or msg.author.name == 'mrmin123'):
                check_ignored_submissions(ignored_submissions, m.group(1))
                log_msg("Ignoring posts under %s by %s's request" % (m.group(1), msg.author.name))
                temp_msg = "%s\nI am ignoring any new posts in this thread by OP/moderator's request! Please request this post to be deleted to un-ignore.\n" % intro
                create_post(c, [temp_msg], 'SUBMISSIONS', 'IGNORE')
            else:
                log_warning("Incorrect ignore request from %s for %s" % (msg.author.name, m.group(1)))

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
                log_msg("Revisiting %s under %s's request" % (m.group(1), msg.author.name))
                check_posts([c], temp_type, True)
            else:
                log_msg("Incorrect revisit request for %s by %s" % (m.group(1), msg.author.name))

        # check for moderator halt request
        if msg.author.name in mod_list or msg.author.name == 'mrmin123':
            m = re.search(ur'^\+halt$', msg.body.lower())
            if m:
                msg.mark_as_read()
                log_error("Bot halt requested by %s" % msg.author.name)
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
                c = post.add_comment(m + signature)
                log_msg("Made a %s comment in %s" % (msg_type, post.short_link))
            elif post_type == 'COMMENTS':
                c = post.reply(m + signature)
                log_msg("Made a %s reply in %s" % (msg_type, post.permalink))
            sig_temp = signature_add.replace('___CID___', str(c.id))
            sig_temp = sig_temp.replace('___PID___', str(c.link_id)[3:])
            sleep(SLEEP)
            m_tmp = c.body.replace('^Processing...', sig_temp)
            m_tmp = m_tmp.replace('&amp;#', '&#')
            r.get_info(thing_id='t1_' + str(c.id)).edit(m_tmp)
            sleep(SLEEP_LONG)

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
        update_queue_file(ignored_submissions_file, ignored_submissions)

        # check submissions/self posts
        check_posts(sub.get_new(limit = LIMIT), 'SUBMISSIONS', False)
        update_queue_file(processed_submissions_file, processed_submissions)

        # check reply/comments
        check_posts(sub.get_comments(limit = LIMIT), 'COMMENTS', False)
        update_queue_file(processed_comments_file, processed_comments)

        # clean up stored PADX data
        while len(processed_monsters) > 200:
            processed_monsters.popleft()
    except requests.exceptions.HTTPError:
        log_error("HTTP Error: Gateway timeout/Origin Down")
        sleep(SLEEP_LONG)
    except Exception as e:
        log_error(e)
