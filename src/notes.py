import os
import sqlite3
from enum import Enum, unique
from datetime import datetime, time
from aqt import mw
import random

from .state import get_index
from .textutils import clean_user_note_text, build_user_note_text, trimIfLongerThan
from .utils import to_tag_hierarchy, get_user_files_folder_path

@unique
class QueueSchedule(Enum):
    NOT_ADD = 1
    HEAD = 2
    FIRST_THIRD = 3
    SECOND_THIRD = 4
    END = 5
    RANDOM = 6
    RANDOM_FIRST_THIRD = 7
    RANDOM_SECOND_THIRD = 8
    RANDOM_THIRD_THIRD = 9

def create_db_file_if_not_exists():
    file_path = _get_db_path()
    if not os.path.isfile(file_path):
        conn = sqlite3.connect(file_path)

        creation_sql = """
            create table if not exists notes
            (
                id INTEGER PRIMARY KEY,
                title TEXT,
                text TEXT,
                source TEXT,
                tags TEXT,
                nid INTEGER,
                created TEXT,
                modified TEXT,
                reminder TEXT,
                lastscheduled TEXT,
                position INTEGER
            )
        """
        conn.execute(creation_sql)
    else:
        conn = sqlite3.connect(file_path)
    conn.execute("""
        create table if not exists read
        (
            page INTEGER,
            nid INTEGER,
            pagestotal INTEGER,
            created TEXT,
            FOREIGN KEY(nid) REFERENCES notes(id)
        )
    """)


    conn.commit()
    conn.close()


def create_note(title, text, source, tags, nid, reminder, queue_schedule):

    #clean the text
    text = clean_user_note_text(text)

    if source is not None:
        source = source.strip()

    if (len(text) + len(title)) == 0:
        return

    tags = " %s " % tags.strip()

    pos = None
    if queue_schedule != 1:
        list = _get_priority_list()
        if QueueSchedule(queue_schedule) == QueueSchedule.HEAD:
            pos = 0
        elif QueueSchedule(queue_schedule) == QueueSchedule.FIRST_THIRD:
            pos = int(len(list) / 3.0)
        elif QueueSchedule(queue_schedule) == QueueSchedule.SECOND_THIRD:
            pos = int(2 * len(list) / 3.0)
        elif QueueSchedule(queue_schedule) == QueueSchedule.END:
            pos = len(list)
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM:
            pos = random.randint(0, len(list))
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM_FIRST_THIRD:
            pos = random.randint(0, int(len(list) / 3.0))
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM_SECOND_THIRD:
            pos = random.randint(int(len(list) / 3.0), int(len(list) * 2 / 3.0))
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM_THIRD_THIRD:
            pos = random.randint(int(len(list) * 2 / 3.0), int(len(list) * 3 / 3.0))

    conn = _get_connection()
    if pos is not None:
        pos_list = [(ix if ix < pos else ix + 1,r[0]) for ix, r in enumerate(list)]
        conn.executemany("update notes set position = ? where id = ?", pos_list)

    id = conn.execute("""insert into notes (title, text, source, tags, nid, created, modified, reminder, lastscheduled, position)
                values (?,?,?,?,?,datetime('now', 'localtime'),""," ","", ?)""", (title, text, source, tags, nid, pos)).lastrowid
    conn.commit()
    conn.close()
    index = get_index()
    if index is not None:
        index.add_user_note((id, title, text, source, tags, nid, ""))


def update_position(note_id, queue_schedule):
    """
        Called after note has been marked as read.
        Will updated the positions of all notes in the queue.
        Also sets the lastscheduled timestamp for the given note.
    """
    conn = _get_connection()
    queue = conn.execute("select id from notes where position is not null and id != %s order by position asc" % note_id).fetchall()
    existing = [e[0] for e in queue]

    if queue_schedule == QueueSchedule.HEAD:
        existing.insert(0, note_id)
    elif queue_schedule == QueueSchedule.FIRST_THIRD:
        existing.insert(int(len(existing) / 3.0), note_id)
    elif queue_schedule == QueueSchedule.SECOND_THIRD:
        existing.insert(int(2 * len(existing) / 3.0), note_id)
    elif queue_schedule == QueueSchedule.END:
        existing.append(note_id)
    elif queue_schedule == QueueSchedule.RANDOM:
        existing.insert(random.randint(0, len(existing)), note_id)
    elif queue_schedule == QueueSchedule.RANDOM_FIRST_THIRD:
        existing.insert(random.randint(0, int(len(existing) / 3.0)), note_id)
    elif queue_schedule == QueueSchedule.RANDOM_SECOND_THIRD:
        existing.insert(random.randint(int(len(existing) / 3.0), int(len(existing) * 2 / 3.0)), note_id)
    elif queue_schedule == QueueSchedule.RANDOM_THIRD_THIRD:
        existing.insert(random.randint(int(len(existing) * 2 / 3.0), int(len(existing) * 3 / 3.0)), note_id)


    pos_ids = [(ix, r) for ix, r in enumerate(existing)]
    conn.executemany("update notes set position = ? where id=?", pos_ids)
    conn.execute("update notes set lastscheduled = datetime('now', 'localtime') where id=%s" % note_id)
    if queue_schedule == queue_schedule.NOT_ADD:
        conn.execute("update notes set position = NULL where id=%s" % note_id)
    conn.commit()
    conn.close()
    index = existing.index(note_id) if queue_schedule != QueueSchedule.NOT_ADD else -1
    return (index, len(existing))

def mark_page_as_read(nid, page, pages_total):
    now = datetime.today().strftime('%Y-%m-%d-%H-%M-%S')
    conn = _get_connection()
    conn.execute("insert or ignore into read (page, nid) values (%s, %s)" % (page, nid))
    conn.execute("update read set created = '%s', pagestotal = %s where page = %s and nid = %s" % (now, pages_total, page, nid))
    conn.commit()
    conn.close()


def mark_page_as_unread(nid, page):
    conn = _get_connection()
    conn.execute("delete from read where nid = %s and page = %s" % (nid, page))
    conn.commit()
    conn.close()

def get_read_pages(nid):
    conn = _get_connection()
    res = conn.execute("select page from read where nid = %s order by created asc" % nid).fetchall()
    conn.close()
    if res is None:
        return []
    return [r[0] for r in res]

def get_note_tree_data():
    """
        Fills a map with the data for the QTreeWidget in the Create dialog.
    """
    conn = _get_connection()
    last_created = conn.execute("select id, title, created from notes order by datetime(created, 'localtime') desc limit 500").fetchall()
    conn.close()
    n_map = {}
    now = datetime.now()
    seconds_since_midnight = (now - now.replace(hour=0, minute=0, second=0, microsecond=0)).total_seconds()

    for id, title, created in last_created:
        cr = datetime.strptime(created, '%Y-%m-%d %H:%M:%S')
        diff = (now - cr).total_seconds()
        if diff < seconds_since_midnight:
            if "Today" not in n_map:
                n_map["Today"] = []
            n_map["Today"].append((id, trimIfLongerThan(title, 100)))
        elif diff >= seconds_since_midnight and diff < (seconds_since_midnight + 86400):
            if "Yesterday" not in n_map:
                n_map["Yesterday"] = []
            n_map["Yesterday"].append((id, trimIfLongerThan(title, 100)))
        else:
            diff_in_days = int((diff - seconds_since_midnight) / 86400.0) + 1
            if str(diff_in_days) + " days ago" not in n_map:
                n_map[str(diff_in_days) + " days ago"] = []
            n_map[str(diff_in_days) + " days ago"].append((id, trimIfLongerThan(title, 100)))
    return n_map

def get_all_notes():
    conn = _get_connection()
    res = list(conn.execute("select * from notes"))
    conn.close()
    return res

def get_note(id):
    conn = _get_connection()
    res = conn.execute("select * from notes where id=" + str(id)).fetchone()
    conn.close()
    return res

def get_random_id_from_queue():
    conn = _get_connection()
    res = conn.execute("select id from notes where position >= 0 order by random() limit 1").fetchone()
    conn.close()
    if res is None or len(res) == 0:
        return -1
    return res[0]

def get_head_of_queue():
    conn = _get_connection()
    res = conn.execute("select id from notes where position >= 0 order by position asc limit 1").fetchone()
    conn.close()
    if res is None or len(res) == 0:
        return -1
    return res[0]

def update_note_text(id, text):
    conn = _get_connection()
    sql = """
        update notes set text=?, modified=datetime('now', 'localtime') where id=?
    """
    text = clean_user_note_text(text)
    conn.execute(sql, (text, id))
    conn.commit()
    note = conn.execute("select title, source, tags from notes where id=" + id).fetchone()
    conn.close()
    index = get_index()
    if index is not None:
        index.update_user_note((id, note[0], text, note[1], note[2], -1, ""))


def update_note(id, title, text, source, tags, reminder, queue_schedule):

    text = clean_user_note_text(text)
    tags = " %s " % tags.strip()
    conn = _get_connection()
    sql = """
        update notes set title=?, text=?, source=?, tags=?, modified=datetime('now', 'localtime') where id=?
    """

    pos = None
    orig_prio_list = _get_priority_list()
    note_had_position = False
    list = []
    for li in orig_prio_list:
        if li[0] == id:
            note_had_position = True
        else:
            list.append(li)
    if queue_schedule != 1:
        if QueueSchedule(queue_schedule) == QueueSchedule.HEAD:
            pos = 0
        elif QueueSchedule(queue_schedule) == QueueSchedule.FIRST_THIRD:
            pos = int(len(list) / 3.0)
        elif QueueSchedule(queue_schedule) == QueueSchedule.SECOND_THIRD:
            pos = int(2 * len(list) / 3.0)
        elif QueueSchedule(queue_schedule) == QueueSchedule.END:
            pos = len(list)
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM:
            pos = random.randint(0, len(list))
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM_FIRST_THIRD:
            pos = random.randint(0, int(len(list) / 3.0))
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM_SECOND_THIRD:
            pos = random.randint(int(len(list) / 3.0), int(len(list) * 2 / 3.0))
        elif QueueSchedule(queue_schedule) == QueueSchedule.RANDOM_THIRD_THIRD:
            pos = random.randint(int(len(list) * 2 / 3.0), int(len(list) * 3 / 3.0))
        sql = """
            update notes set title=?, text=?, source=?, tags=?, position=%s, modified=datetime('now', 'localtime') where id=?
        """ % pos
    else:
        if note_had_position:
            sql = "update notes set title=?, text=?, source=?, tags=?, modified=datetime('now', 'localtime') where id=?"
        else:
            sql = "update notes set title=?, text=?, source=?, tags=?, position=null, modified=datetime('now', 'localtime') where id=?"

    conn.execute(sql, (title, text, source, tags, id))

    if pos is not None:
        list.insert(pos, (id,))
        pos_list = [(ix,r[0]) for ix, r in enumerate(list)]
        conn.executemany("update notes set position = ? where id = ?", pos_list)
    conn.commit()
    conn.close()
    index = get_index()
    if index is not None:
        index.update_user_note((id, title, text, source, tags, -1, ""))

def get_all_tags():
    """
        Returns a set containing all tags (str) that appear in the user's notes.
    """
    conn = _get_connection()
    all_tags = conn.execute("select tags from notes where tags is not null").fetchall()
    conn.close()
    tag_set = set()
    for tag_str in all_tags:
        for t in tag_str[0].split():
            if len(t) > 0:
                if t not in tag_set:
                    tag_set.add(t)
    return tag_set

def find_by_tag(tag_str):
    index = get_index()
    pinned = []
    if index is not None:
        pinned = index.pinned

    query = "where "
    for t in tag_str.split(" "):
        if len(t) > 0:
            t = t.replace("'", "''")
            if len(query) > 6:
                query += " or "
            query += "lower(tags) like '% " + t + " %' or lower(tags) like '% " + t + "::%' or lower(tags) like '%::" + t + " %' or lower(tags) like '% " + t + "::%' or lower(tags) like '" + t + " %' or lower(tags) like '%::" + t + "::%'"
    conn = _get_connection()

    res = conn.execute("select * from notes %s" %(query)).fetchall()
    output_list = _to_output_list(res, pinned)
    return output_list

def find_by_text(text):
    index = get_index()
    index.search(text, [])


def delete_note(id):
    update_position(id, QueueSchedule.NOT_ADD)
    conn = _get_connection()
    conn.execute("delete from read where nid =%s" % id)
    sql = """
        delete from notes where id=%s
    """ % id
    conn.execute(sql)
    conn.commit()
    conn.close()

def get_read_today_count():
    now = datetime.today().strftime('%Y-%m-%d')
    conn = _get_connection()
    c = conn.execute("select count(*) from read where created like '%s %'" % now).fetchone()
    conn.close()
    return c

def get_queue_count():
    conn = _get_connection()
    c = conn.execute("select count(*) from notes where position is not null and position >= 0").fetchone()
    conn.close()
    return c

def get_recently_used_tags():
    """
        Returns a [str] of max 10 tags, ordered by their usage desc.
    """
    counts = _get_recently_used_tags_counts(20)
    ordered = [i[0] for i in list(sorted(counts.items(), key=lambda item: item[1], reverse = True))][:10]
    return ordered

def get_recently_used_tags_with_counts():
    """
        Returns a {str, int} of max 10 tags, ordered by their usage desc.
    """
    counts = _get_recently_used_tags_counts(10)
    ordered = dict(sorted(counts.items(), key=lambda item: item[1], reverse = True))
    return ordered

def _get_recently_used_tags_counts(limit):
    conn = _get_connection()
    res = conn.execute("select tags from notes where tags is not null order by id desc limit %s" % limit).fetchall()
    conn.close()
    if res is None or len(res) == 0:
        return dict()
    counts = dict()
    for r in res:
        spl = r[0].split()
        for tag in spl:
            if tag in counts:
                counts[tag] += 1
            else:
                counts[tag] = 1

    return counts

def _get_priority_list(nid_to_exclude = None):
    conn = _get_connection()
    if nid_to_exclude is not None:
        sql = """
            select * from notes where position >= 0 and id != %s order by position asc
        """ % nid_to_exclude
    else:
        sql = """
            select * from notes where position >= 0 order by position asc
        """
    res = conn.execute(sql).fetchall()
    conn.close()
    return list(res)


def get_priority_list():
    """
        Returns all notes that have a position set.
        Result is in the form that Output.printSearchResults wants.
    """
    conn = _get_connection()
    sql = """
       select * from notes where position >= 0 order by position asc
    """
    res = conn.execute(sql).fetchall()
    conn.close()
    output_list = _to_output_list(res, [])
    return output_list

def get_newest(limit, pinned):
    """
        Returns newest user notes ordered by created date desc.
        Result is in the form that Output.printSearchResults wants.
    """
    conn = _get_connection()
    sql = """
       select * from notes order by datetime(created) desc limit %s
    """ % limit
    res = conn.execute(sql).fetchall()
    conn.close()
    output_list = _to_output_list(res, pinned)
    return output_list

def get_random(limit, pinned):
    conn = _get_connection()
    res = conn.execute("select * from notes order by random() limit %s" % limit).fetchall()
    conn.close()
    output_list = _to_output_list(res, pinned)
    return output_list

def get_queue_in_random_order():
    conn = _get_connection()
    res = conn.execute("select * from notes where position is not null order by random()").fetchall()
    conn.close()
    output_list = _to_output_list(res, [])
    return output_list

def set_priority_list(ids):
    ulist = list()
    for ix,id in enumerate(ids):
        ulist.append((ix, id))
    conn = _get_connection()
    conn.executemany('update notes set position = ? where id = ?', ulist)
    conn.commit()
    conn.close

def _get_db_path():
    file_path = mw.addonManager.getConfig(__name__)["addonNoteDBFolderPath"]
    if file_path is None or len(file_path) == 0:
        file_path = get_user_files_folder_path()
    file_path += "siac-notes.db"
    return file_path

def _get_connection():
    file_path = _get_db_path()
    return sqlite3.connect(file_path)

def get_all_tags_as_hierarchy(include_anki_tags):
    tags = None
    if include_anki_tags:
        tags = mw.col.tags.all()
        user_note_tags = get_all_tags()
        tags.extend(user_note_tags)
    else:
        tags = get_all_tags()
    return to_tag_hierarchy(tags)


def get_all_pdf_notes():
    conn = _get_connection()
    res = conn.execute("select * from notes where lower(source) like '%.pdf'").fetchall()
    conn.close()
    output_list = _to_output_list(res, [])
    return output_list


def get_pdf_info(nids):
    sql = "select nid, pagestotal, count(*) from read where nid in (%s) group by nid" % (",".join([str(n) for n in nids]))
    conn = _get_connection()
    res = conn.execute(sql).fetchall()
    conn.close()
    ilist = []
    for r in res:
        ilist.append([r[0], r[2], r[1]])
    return ilist


def _to_output_list(db_list, pinned):
    output_list = list()
    for (id, title, text, source, tags, nid, created, modified, reminder, _, position) in db_list:
        if not str(id) in pinned:
            output_list.append((build_user_note_text(title, text, source), tags, -1, id, 1, "-1", "", position))
    return output_list
