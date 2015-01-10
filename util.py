import datetime, time, pymongo

def check_processed_posts(processed_list, id, limit):
    """
    checks and maintains list of processed submissions and replies
    """
    if id not in processed_list:
        processed_list.append(id)
        if len(processed_list) > (limit * 3):
            processed_list.popleft()

def read_queue_file(file, queue):
    """
    read in list of processed submissions and replies on start of script
    (in case of script crash)
    """
    try:
        with open(file) as input:
            for line in input:
                queue.append(line.strip())
    except IOError as e:
        log_error(e)
    except Exception as e:
        log_error(e)
        exit()

def update_queue_file(file, queue):
    """
    update text file with list of processed submissions or replies so bot
    does not reprocess them on re-initialization
    """
    try:
        f = open(file, 'w')
        for id in queue:
            f.write(id + '\n')
        f.close()
    except Exception as e:
        log_error(e)

def reset_db(stat_coll):
    try:
        stat_coll.update({ 'field': 'post_monster' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_flair' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_split' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_revisit' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_revisit_bad' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'ignore_post' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'ignore_pm' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'ignore_bad' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'del_score' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'del_pm' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'del_bad' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'unignore' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'halt' }, { '$inc': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_monster_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_flair_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_split_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_revisit_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'post_revisit_bad_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'ignore_post_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'ignore_pm_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'ignore_bad_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'del_score_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'del_pm_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'del_bad_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'unignore_run' }, { '$set': { 'count': 0 } }, True)
        stat_coll.update({ 'field': 'run' }, { '$set': { 'date': datetime.datetime.utcnow() } }, True)
    except Exception as e:
        log_error(e)

def update_db(log_coll, stat_coll, log_type, url, user):
    """
    update the db logs and stats
    """
    try:
        if log_type == 'MONSTER TABLE':
            stat_coll.update({ 'field': 'post_monster' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'post_monster_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'FLAIR ID':
            stat_coll.update({ 'field': 'post_flair' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'post_flair_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'SPLIT':
            stat_coll.update({ 'field': 'post_split' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'post_split_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'REVISIT':
            stat_coll.update({ 'field': 'post_revisit' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'post_revisit_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'REVISIT_BAD':
            stat_coll.update({ 'field': 'post_revisit_bad' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'post_revisit_bad_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'IGNORE_PM':
            stat_coll.update({ 'field': 'ignore_pm' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'ignore_pm_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'IGNORE_POST':
            stat_coll.update({ 'field': 'ignore_post' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'ignore_post_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'IGNORE_BAD':
            stat_coll.update({ 'field': 'ignore_bad' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'ignore_bad_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'DEL_SCORE':
            stat_coll.update({ 'field': 'del_score' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'del_score_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'DEL_PM':
            stat_coll.update({ 'field': 'del_pm' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'del_pm_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'DEL_BAD':
            stat_coll.update({ 'field': 'del_bad' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'del_bad_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'UNIGNORE':
            stat_coll.update({ 'field': 'unignore' }, { '$inc': { 'count': 1 } }, True)
            stat_coll.update({ 'field': 'unignore_run' }, { '$inc': { 'count': 1 } }, True)
        elif log_type == 'HALT':
            stat_coll.update({ 'field': 'halt' }, { '$inc': { 'count': 1 } }, True)
        log_coll.insert({'type': log_type, 'url': url, 'user': user, 'date': datetime.datetime.utcnow()})
    except Exception as e:
        log_error(e)


# log colors
class color:
    MSG = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    END = '\033[0m'

def format(msg):
    now = time.strftime("%Y-%m-%d %H:%M:%S")
    return "[%s] %s" % (now, msg)

def log_msg(msg):
    print "%s%s%s" % (color.MSG, format(msg), color.END)

def log_success(msg):
    print "%s%s%s" % (color.SUCCESS, format(msg), color.END)

def log_warning(msg):
    print "%s%s%s" % (color.WARNING, format(msg), color.END)

def log_error(msg):
    print "%s%s%s" % (color.ERROR, format(msg), color.END)
