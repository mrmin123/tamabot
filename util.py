import time

def check_processed_posts(processed_list, id, limit):
    """
    checks and maintains list of processed submissions and replies
    """
    if id not in processed_list:
        processed_list.append(id)
        if len(processed_list) > limit:
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
