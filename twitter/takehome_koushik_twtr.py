import sys
import glob
import os.path
import collections
import time
import urllib, os
import subprocess
import multiprocessing
import logging
from multiprocessing import Queue
import urllib.request
import json
from collections import OrderedDict
import itertools
from itertools import groupby
import operator

server_list_threshold = 10000
split_servers = False;
g_thrs = 16
jobs = []

url_list = multiprocessing.Queue()
json_resp_q = multiprocessing.Queue()

def _servers_to_urls(servers_fname):
    queue_depth = 0;
    with open(servers_fname, "r") as ins:
        try:
            for line in ins:
                server_name = str(line).splitlines()[0]
                url = "http://"+server_name+".twitter.com/status"
                #url = "http://md5.jsontest.com/?text=example_text"
                #logging.info ("url-->" + url)
                url_list.put(url)
                queue_depth = queue_depth+1

            i = 0
            url_list.put(None)
            ins.close()
            return queue_depth
        except BaseException as e:
                #Dont die just because one server append failed. Add to log though...
                logging.error ("Server: %s enqueue. error: %s " %(server_name, str(e)))

def consume_urls(url_list, chunk_size):
    i = 0
    result = []
    save_as  = "opfile_" + str(os.getpid()) +".raw"
    save_obj = open(save_as, "w")
    while i < chunk_size and not url_list.empty():
        url = url_list.get()
        if (url is None):
            return
        i = i + 1
        try:
            req = urllib.request.Request(url)
            response = urllib.request.urlopen(req)
            the_page = response.read()
            encoding = response.info().get_content_charset('utf-8')
            data = json.loads(the_page.decode(encoding))
            result.append(data)
        except BaseException as e:
            logging.error ("Error: unable to consume urls " + str(e))

    json.dump(result, save_obj)
    save_obj.close()

# Since there will be only 16 files, no need to multithread this function
# You also dont want to deal with file locking between threads
def _merge_response_json(merge_f):
    result = []

    for small_fname in glob.glob('*.raw'):
        st = os.stat(small_fname)
        # Incase one of the process failed, skip its empty .raw file
        if (st.st_size == 0):
            os.remove(small_fname)
            continue
        with open(small_fname, "r") as json_data:
            result.append(json.load(json_data))
            os.remove(small_fname)
    with open(merge_f, "w") as outfile:
        json.dump(result, outfile)

def sort_summary_json(merge_file, f_downstream):
    #with open("responses1.txt") as json_data:
    with open(merge_file) as json_data:
        responses = json.load(json_data)
        sorted_list = sorted(responses, key=lambda k: ((k["Application"]), -int(k["Success_Count"]), (k["Version"]) ))
        grouped_list = groupby(sorted_list, key=operator.itemgetter("Application"))
        _human_readable(grouped_list)

        grouped_list = groupby(sorted_list, key=operator.itemgetter("Application"))
        _dumpto_file(grouped_list, f_downstream)

def _human_readable(grouped_list):
    for application, group in grouped_list:
        count = 0;
        for content in group:
            count=count+1
        print ('Application: %s \tsuccessful calls: %s' %(application,count))

def _dumpto_file(grouped_list, f_downstream):
    downstream_obj = open(f_downstream, 'w')
    apps_dict = dict()
    for application, group in grouped_list:
        if application not in apps_dict:
            apps_dict[application] = []
        for content in group:
            apps_dict[application].append(content)

    json.dump(apps_dict, downstream_obj, sort_keys=True)
    downstream_obj.close()

def main():
    overall_st = time.time()
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s',
                        filename='exec.log',
                        filemode='w')
    if (len(sys.argv) != 3):
        print ("invalid arg count")
        print ("python3 takehome_koushik_twtr.py servers.txt <responses.txt>")
        sys.exit(0)

    if ((sys.argv[1] is None) or (sys.argv[2] is None)):
        print ("invalid args")
        print ("python3 takehome_koushik_threaded.py access.log <N>")
        sys.exit(0)

    in_file = sys.argv[1];
    out_file = sys.argv[2];

    try:
        in_obj = open(in_file,"r");
        out_obj = open(out_file,"w")
    except BaseException as e:
        logging.error ("Error: unable to open files" + str(e))
        sys.exit(0)

    queue_len = _servers_to_urls(in_file)
    if (queue_len is None):
        raise Exception('Something went wrong! Check exec.log')
    #print (queue_len)
    chunk_size = queue_len / g_thrs
    extra_jobs = queue_len % g_thrs
    total_len = 0
    last_start = 0
    i = 1
    start_idx = 0
    t_start = time.time()
    job_count = 0
    while total_len < queue_len:
        try:
            end_idx = i * chunk_size
            p = multiprocessing.Process(target=consume_urls, args=(url_list, chunk_size, ))
            jobs.append(p)
            p.start()
            job_count= job_count+1
            total_len = total_len + (end_idx - last_start)
            i = i + 1
            last_start = end_idx

        except BaseException as e:
            logging.error ("Error: unable to start reader process " + str(e))

    if extra_jobs > 0:
        #print ("Adding another thread for job ", extra_jobs)
        end_idx = last_start + extra_jobs
        try:
            p = multiprocessing.Process(target=consume_urls, args=(url_list, extra_jobs, ))
            jobs.append(p)
            p.start()
            job_count= job_count+1
        except BaseException as e:
            logging.error ("Error: unable to start reader process " + str(e))

    for p in jobs:
        p.join()
    # This part will throw error if all servers are fictitious and we
    # dont have anything to sort or merge
    # TypeError: list indices must be integers or slices, not str
    logging.info("total fetch: %d secs" %(time.time() - t_start))
    merge_f = "merged.json"
    t_start - time.time()
    _merge_response_json(merge_f)
    logging.info("merge: %d secs" %(time.time() - t_start))
    t_start - time.time()
    sort_summary_json(merge_f, out_file)
    logging.info("sort and summary:%d secs" %(time.time() - t_start))
    # We dont really need to preserve the merged json 
    #os.remove(merge_f)
    logging.info("overall: %d secs" %(time.time() - overall_st))

if __name__ == '__main__':main()
