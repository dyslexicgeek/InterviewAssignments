import sys
from itertools import islice
import glob
import os.path
import collections
import time
import subprocess
import multiprocessing
import threading
import logging

# This should be a tunable N cmdline arg, based on access.log size
N = 10000;
userid_skip = set()
g_read_thr = 16
jobs = []
write_queue = multiprocessing.Queue()

def file_len(fname):
    p = subprocess.Popen(['wc', '-l', fname], stdout=subprocess.PIPE, 
                                              stderr=subprocess.PIPE)
    result, err = p.communicate()
    if p.returncode != 0:
        raise IOError(err)
    return int(result.strip().split()[0])

def Writer(dest_filename, write_queue):
    with open(dest_filename, 'a+') as dest_file:
        while True: 
            line = write_queue.get()
            if (line is None):
                dest_file.close()
                return
            #logging.debug("writing to file...")
            dest_file.write(str(line))
            dest_file.write("\n")

def countJob(number_N, user_queue, user_file_list):
    for user_fname in user_file_list:
        if os.path.exists(user_fname):
            lines = file_len(user_fname)
            if (lines > number_N):
                #logging.debug("appending to queue")
                userid = user_fname.split('.');
                user_queue.put(userid[0])
            os.remove(user_fname)

def main():
    t_start = time.time()
    tmp_count = 0
    tmp_log_count = 0
    final_ofile = "frequent_users.txt"
    of_obj = open(final_ofile,"w");
    logging.basicConfig(level=logging.DEBUG,
                        format='%(asctime)s %(levelname)s %(message)s',
                        filename='myexec.log',
                        filemode='w')

    if (len(sys.argv) != 3):
        print ("invalid arg count")
        print ("python3 takehome_koushik_threaded.py access.log <N>")
        sys.exit(0)

    if ((sys.argv[1] is None) or (sys.argv[2] is None)):
        print ("invalid args")
        print ("python3 takehome_koushik_threaded.py access.log <N>")
        sys.exit(0)

    filename = sys.argv[1];
    number_N = int(sys.argv[2]);
    if (number_N <= 0):
        print ("invalid args")
        print ("python3 takehome_koushik_threaded.py access.log <N>")
        sys.exit(0)

    with open(filename, 'r') as infile:
        try:
            while True:
            #while tmp_count < 200:
                lines_gen = list(islice(infile, N))
                if not lines_gen:
                    break
                tmplog_name = str(tmp_log_count) + ".tmp"
                tmp_f = open(tmplog_name, "w")
                tmp_f.writelines(lines_gen)
                tmp_log_count = tmp_log_count + 1
                #tmp_count = tmp_count + 50 
                tmp_f.close()
        except:
            infile.close();
            pass;

    for small_fname in glob.glob('*.tmp'):
        small_fobj = open(small_fname, "r")
        for line in small_fobj:
            if not line:
                break;
            columns = line.split(',')
            username = columns[1]
            path     = columns[2]
            user_fname = username + ".usr"
            if user_fname not in userid_skip:
                f = open(user_fname, "a+")
                if f.read().find(path) != -1:
                    #duplicate path, close and continue
                    # TODO: repeated open-close must be
                    # optimized with an in-memory KV {userid: f_obj}
                    pass
                else:
                    f.write(path)

                f.close()

        os.remove(small_fname)

    # created all the user files with unique paths. Now scroll through
    # the user files and check for threshold count and add userid to a file
    userfile_list = glob.glob('*.usr')
    userfile_listlen = len(userfile_list)
    chunk_size = int ((userfile_listlen / g_read_thr));
    
    total_len = 0
    last_start = 0
    i = 1
    while total_len < userfile_listlen:
        try:
            end = i * chunk_size
            p = multiprocessing.Process(target=countJob, args=(number_N, write_queue, userfile_list[last_start:end], ))
            jobs.append(p)
            p.start()
            total_len = total_len + (end - last_start)
            i= i + 1
            last_start = end
        except BaseException as e:
            logging.error ("Error: unable to start reader process " + str(e))

    writer_process = multiprocessing.Process(target = Writer, 
                      args=("frequent_users.txt", write_queue))
    writer_process.start()
    for p in jobs:
        p.join()
    write_queue.put(None)
    write_queue.close()
    t_end = time.time()
    logging.info ("total time seconds: %d" %(time.time() - t_start))
if __name__ == '__main__':main()
