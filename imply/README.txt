problem: https://gist.github.com/gianm/cefaef37edc719036d57

CONTENTS OF THIS WRITEUP 
-------------------------

* Introduction
* Design options
* Design repurcussions/drawbacks
* Efficiency Analysis and assumptions
* Exec time
* Possible improvements
* Other design possibilities

* Introduction
This is the sample solution for the takehome programming assignment

python3 takehome_koushik_threaded.py access.log <N>

* Design options

1) Database (Memory intensive. Less CPU intensive)
We could have simply used a RDB or a KV store.
In case of a RDB, the schema needs to be known. But since
it can be an unstructured file, the schema cannot keep up.
The other option, was to use a KV store.
We would have had to parse the access.log just once and
used the userid as the Key.
The in-memory requirement will be intense if, a file
of say, 100GB is used in this case.

2) Multithreaded python solution (chosen) (CPU and syscall intensive. Lighter memory wise)
Since the rule was that the whole file cannot be read
due to memory constraints.
The approach was such
    Map type phase:
    a) break up the file in to smaller chunks (may be 10K lines each)
    b) For each of the smaller chunks of access.log,
        - parse the chunk file, and for every userid, open/create <usrid>.usr file
    c) Add the unique path id in this file. If the path already exists in file, continue 

    At this point we have user files with the count of unique paths 

    Reduce type phase:
    a) Spawn multiple countJobs() (depending on number of threads decided)
    b) Spawn a writer() process
    c) countJobs, go through their chunk of alloted .usr files and enqueue files with > N
    d) writer() eats up the queue and writes to the final output file

3) Sort smaller chunks and K-way merge of files (CPU and memory intensive)
Another possibility would have been, break the file in to smaller
chunks. Sort those chunks based on user id
Now all these chunks can be merge using a K-way merge step.
All user IDs will be eventually sorted in the final big array
(which doesnt necessarily have to be in memory - can be in a file)
Scroll through this large sorted list and we get the required info
Instead of k-way merge, may be doing a binary search for each entry
in other files *might* work. 
The efficiency will be -    K * O(n log n)  ==> sort
                         +  O(K*n)          ==> merge step
                         +  O(N)            ==> sequential traverse of sorted array

* Design repurcussions/drawbacks

There is a large number of fopen(), fseek(). fstat() and fclose() happening in strace.
(strace is too big to attach here)

strace -o calls.txt python3 takehome_koushik_threaded.py access.log 50 

This could have been avoided by using an inmemory "DICTIONARY" type
approach which could avoid the extra syscalls for open and close.
The dictionary would hold <userid>: <file_handle obj>

The underlying filesystem may or may not be very efficient
in supporting large number of tiny <.usr> files.

* Efficiency Analysis and assumptions
    Assumptions:
        O(1) - open() and close()
        O(1) - f.read().find() - since it is a small file
        O(1) - multiprocess Queue.add() and Queue.pop() 
               Since the lock contention is taken care of by
               underlying infrastructure, we tend to abuse this...
        O(K) - for process spawning. We keep the countJobs to only 16
             to avoid too many processes
        O(1) - subprocess.Popen for "wc -l"

    Efficiency:
        1) Large access.log split to smaller ==> O(Open + read 10K lines each + Close)
                                                 O(N)
        2) Smaller chunks counting ==> O(Open chunk + readLine + m *(Open .usr  +
                                       search .usr + write to .usr + close .usr) + close chunk)

        3) Reduce phase ==> O(n * (Open .usr + get line count + enqueue + close/delete .usr)) +
                            O(dequeue + write to file + close output file)
                            
* Exec time
  This is more of a CPU intensive and syscall path intesive code, less RAM intensive
  1430 secs - Intel(R) Core(TM) i5-4670 CPU @ 3.40GHz, 32GB RAM (CPUs:4) (Desktop machine)
  2924 secs - Intel(R) Core(TM) i7-4870HQ CPU @ 2.50GHz, 16GB RAM (logicalcpu: 8) (Mac laptop)
 
* Possible improvements
The reason for choosing this method was that, though it is inefficient, due to small file
creations, if we have more than one nodes, each access log chunk can be sent to a 
node and the node can do the map operation.

Or, the reduce can be spawned off to multiple nodes which can do the counting
of .usr file (multithreaded per node) and then report it to a leader node

* Other design possibilities(in memory structures)

I tried using an in memory dictionary which holds the open .usr objects and the 
corresponding f_obj. I was thinking about how to keep the size fixed
and designing the fixed hashmap replacement policy. I removed that code
in this submission though

We need to define a user type hash such as this:

class MyObject():
    def getName(self):
        return self.name

    def getValue(self):
        return self.value

    def __hash__(self):
        return hash((self.name))

    def __eq__(self, other):
        return (self.name) == (other.name)

    def __ne__(self, other):
        return not(self == other)

    def __init__(self,name, value):
        self.name = name
        self.value = value

    FIXED hashmap with replacement(found by a search):

class MyDict(collections.MutableMapping):
    def __init__(self, maxlen, *a, **k):
        self.maxlen = maxlen
        self.d = dict(*a, **k)
        while len(self) > maxlen:
            self.popitem()
    def __iter__(self):
        return iter(self.d)
    def __len__(self):
        return len(self.d)
    def __getitem__(self, k):
        return self.d[k]
    def __delitem__(self, k):
        del self.d[k]
    def __setitem__(self, k, v):
        if k not in self and len(self) == self.maxlen:
            self.popitem()
        self.d[k] = v 
