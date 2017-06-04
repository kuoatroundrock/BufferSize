import random

LOG_SEVERITY = 1
debug = False
init = True

cycle = 0

# max_cycles = 100
# DMA_PREFETCH_LEVEL = 2
# NFA_THREADS = 1
# FETCH_NUM_BYTES_PER_FLIT = 4
# NFA_TIME_TO_PROCESS_A_BYTE = 3
# HBM_LATENCY = 5

max_cycles = 500000

HBM_LATENCY = 500
DMA_PREFETCH_LEVEL = 3# number of 16-byte
FETCH_NUM_BYTES_PER_FLIT = 16
FETCH_NUM_FLITS = 64 / FETCH_NUM_BYTES_PER_FLIT
NFA_THREADS = 16
NFA_TIME_TO_PROCESS_A_BYTE = 8


# TIME_TO_PROCESS_16B = 16 * NFA_TIME_TO_PROCESS_A_BYTE

class SimBase:
    def __init__(self):
        self.id = -1

    def __init__(self, id, prefix):
        self.id = id;
        self.prefix = prefix

    def log(self, info):
        print self.prefix + str(self.id) + "::" + str(info),


class Token:
    def __init__(self):
        self.owner = -1
        self.hog_cycles = 1

    def is_idle(self):
        return (self.owner == -1)

    def get(self, id, hog_cycles=1):
        if self.owner == -1:
            self.owner = id
            self.hog_cycles = hog_cycles
            return True
        elif self.owner == id:
            return True
        else:
            return False

    def release(self):
        self.hog_cycles -= 1
        if self.hog_cycles == 0:
            self.owner = -1


class Engine(SimBase):
    def __init__(self, id, o_stat):
        #        super(Engine, self).__init__(id, "E")
        # self.state = "IDLE"
        self.id = id
        self.idle_cycles = 0
        self.start = False
        self.cnt = 0
        self.bytes = 0
        self.o_stat = o_stat

    def randinit(self):
        self.start = True
        self.bytes = random.randint(1, FETCH_NUM_BYTES_PER_FLIT)
        self.cnt = random.randint(1, NFA_TIME_TO_PROCESS_A_BYTE)

    def log(self, info):
        print "E" + str(self.id) + "::" + str(info),

    def set_bytes(self, bcnt):
        if not self.start and bcnt > 0:
            self.start = True
        self.bytes += bcnt

        if self.cnt == 0:
            self.cnt = NFA_TIME_TO_PROCESS_A_BYTE + 1  # TODO

        print "E" + str(self.id) + "::Got " + str(bcnt) + " ",

    def ready_to_get_bytes(self):
        return (self.bytes <= 1 and self.cnt <= 1)

    def is_idle(self):
        return (self.bytes <= 0)

    def get_idle_cycles(self):
        return self.idle_cycles

    def tick(self):

        if self.cnt > 0:
            self.cnt -= 1

        if self.bytes > 0:
            if self.cnt == 0:

                # print "E" + str(self.id) + "::B" + str(self.bytes) + " ",
                self.o_stat.add({"Retire" : 1})
                self.log("B" + str(self.bytes)),
                self.bytes -= 1

                if self.bytes > 0:
                    self.cnt = NFA_TIME_TO_PROCESS_A_BYTE
        elif self.start and self.bytes == 0:  # if self.bytes == 0;
            self.idle_cycles += 1
        elif not self.start:
            pass
        else:
            print "FAIL"


class Memory(SimBase):
    def __init__(self, id):
        self.id = id
        self.requests = {}

    def register(self, client):
        if client.id in self.requests.keys():
            print "FAIL"
        else:
            self.requests[client.id] = HBM_LATENCY

    def tick(self):
        for t in self.requests.keys():
            self.requests[t] -= 1
            if self.requests[t] == 0:  # timeout
                threads[t].dmi_return_data(FETCH_NUM_FLITS)


class Thread(SimBase):
    def __init__(self, id):
        # super(Thread, self).__init__(id, "T")
        # self.cycles = TIME_TO_PROCESS_16B
        self.id = id
        self.data = []
        self.fcnt = 0  # HBM delay
        self.state = "IDLE"
        self.wait_for_dmi = False

    def log(self, info):
        print "T" + str(self.id) + "::" + str(info),

    def randinit(self):
        a = random.choice([[], ["TRD", "FTH"], ["FTH"]])
        self.data.extend(a)

    def p_data(self, mode=0):
        if len(self.data):
            if mode == 0:
                print " T" + str(self.id) + "->" + str(self.data),
            elif mode == 1:
                print " T" + str(self.id) + ":" + str(len(self.data)),
        return len(self.data)

    def callback(self, engine):
        if engine.ready_to_get_bytes() and len(self.data):
            engine.set_bytes(FETCH_NUM_BYTES_PER_FLIT)
            self.data.pop(0)

    def call_back_dmi_return_data(self, flits):
        self.wait_for_dmi == False


    def dmi_request(self):
        hbm.register(self)
        self.wait_for_dmi = True

    def dmi_return_data(self, flits):
        self.wait_for_dmi = False


    def tick(self):

        if debug:
            print "T" + str(self.id) + "->" + str(self.fcnt),

        if self.state == "BEAT4":  # and token_resp.get(self.id):
            self.state = "IDLE"
            self.data.append("FTH")

        if self.state == "BEAT3":  # and token_resp.get(self.id):
            self.state = "BEAT4"
            self.data.append("TRD")

        if self.state == "BEAT2":  # and token_resp.get(self.id):
            self.state = "BEAT3"
            self.data.append("SND")

        if self.state == "FETCH":

            if self.fcnt > 0:
                self.fcnt -= 1
            if self.fcnt == 0 and token_resp.get(self.id, hog_cycles=FETCH_NUM_FLITS):
            #BUG if not self.wait_for_dmi and token_resp.get(self.id, hog_cycles=FETCH_NUM_FLITS):
                self.state = "BEAT2"
                self.data.append("FST")

        if len(self.data) <= DMA_PREFETCH_LEVEL and self.state == "IDLE" and token.get(self.id):

            self.log("DmiRead")
            self.state = "FETCH"
            self.fcnt = HBM_LATENCY
            self.dmi_request()


class Statistic(SimBase):
    def __init__(self):
        self.stat = {}

    def add(self, info_d):
        for k in info_d.keys():
            if k in self.stat.keys():
                self.stat[k] += info_d[k]
            else:
                self.stat[k] = info_d[k]

    def reset(self):
        self.stat = {}

    def print_statistic(self):

        for k in self.stat.keys():
            print "Statistic : " + str(self.stat[k]),
        if len(self.stat):
            return self.stat["Retire"]
        else:
            return 0


stat = Statistic()

threads = []
engines = []

hbm = Memory("HBM")

token = Token()
token_resp = Token()



for i in range(NFA_THREADS):
    threads.append(Thread(i))
    engines.append(Engine(i, stat))

max = -1

# random start
if init == True:
    for t in threads + engines:
        t.randinit()

stat_total_bytes = 0

while (cycle < max_cycles):

    print "Cycle " + str(cycle) + " : ",

    # preproces
    for i, t in enumerate(threads):
        t.callback(engines[i])

    hbm.tick()
    for t in threads + engines:
        t.tick()

    token.release()
    token_resp.release()

    # import pdb;pdb.set_trace()
    sum = 0
    for t in threads:
        sum += t.p_data(mode=LOG_SEVERITY)

    if sum > max:
        max = sum;


    stat_total_bytes += stat.print_statistic()
    stat.reset()

    print ""

    cycle += 1

idles = 0
for e in engines:
    idles += e.get_idle_cycles()

print "Idle Cycles : " + str(idles)
print "Maximum : " + str(max)
print "Bytes per cycle : " + str(stat_total_bytes / max_cycles)
