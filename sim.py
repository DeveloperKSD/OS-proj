"""OS algorithm labs: scheduling, page replacement, disk scheduling, Banker's, dining philosophers, race condition."""
import threading
import time


# ---------- Unit 2: CPU scheduling (average waiting time; all processes arrive at t=0) ----------
def sched_waits(bursts):
    b = [x for x in bursts if x > 0]
    if len(b) < 2:
        return {}

    def fcfs(seq):
        t, total = 0.0, 0.0
        for x in seq:
            total += t
            t += x
        return total / len(seq)

    q = max(b) / 20
    rem, t, fin = list(b), 0.0, [0.0] * len(b)
    while any(r > 0 for r in rem):
        for i, r in enumerate(rem):
            if r > 0:
                run = min(q, r)
                t += run
                rem[i] -= run
                if rem[i] <= 1e-12:
                    rem[i], fin[i] = 0, t
    rr = sum(f - x for f, x in zip(fin, b)) / len(b)
    return {"FCFS": fcfs(b), "SJF": fcfs(sorted(b)), "RoundRobin": rr}


# ---------- Unit 5: page replacement ----------
def _fifo(refs, f):
    mem, faults = [], 0
    for r in refs:
        if r not in mem:
            faults += 1
            if len(mem) == f:
                mem.pop(0)
            mem.append(r)
    return faults


def _lru(refs, f):
    mem, faults = [], 0
    for r in refs:
        if r in mem:
            mem.remove(r)
        else:
            faults += 1
            if len(mem) == f:
                mem.pop(0)
        mem.append(r)
    return faults


def _optimal(refs, f):
    mem, faults = [], 0
    for i, r in enumerate(refs):
        if r in mem:
            continue
        faults += 1
        if len(mem) < f:
            mem.append(r)
            continue

        def nxt(p):
            try:
                return refs.index(p, i + 1)
            except ValueError:
                return float("inf")

        mem[mem.index(max(mem, key=nxt))] = r
    return faults


def _clock(refs, f):
    mem, bit, hand, faults = [None] * f, [0] * f, 0, 0
    for r in refs:
        if r in mem:
            bit[mem.index(r)] = 1
            continue
        faults += 1
        while mem[hand] is not None and bit[hand] == 1:
            bit[hand] = 0
            hand = (hand + 1) % f
        mem[hand], bit[hand] = r, 1
        hand = (hand + 1) % f
    return faults


def page_all(refs, frames):
    if not refs or frames < 1:
        raise ValueError("Enter a reference string and at least 1 frame")
    out = {}
    for name, fn in (("FIFO", _fifo), ("LRU", _lru), ("Optimal", _optimal), ("Clock", _clock)):
        faults = fn(refs, frames)
        out[name] = {"faults": faults, "hit_ratio": round(100 * (len(refs) - faults) / len(refs), 1)}
    return out


# ---------- Unit 6: disk scheduling ----------
def disk_all(reqs, head, size=200):
    if not reqs:
        raise ValueError("Enter at least one request")

    def total(order):
        pos, t = head, 0
        for x in order:
            t += abs(x - pos)
            pos = x
        return t

    left, pos, sstf = list(reqs), head, []
    while left:
        n = min(left, key=lambda x: abs(x - pos))
        sstf.append(n)
        left.remove(n)
        pos = n
    up = sorted(r for r in reqs if r >= head)
    down = sorted((r for r in reqs if r < head), reverse=True)
    orders = {
        "FCFS": list(reqs),
        "SSTF": sstf,
        "SCAN": up + [size - 1] + down,
        "C-SCAN": up + [size - 1, 0] + sorted(r for r in reqs if r < head),
        "LOOK": up + down,
    }
    return {k: {"movement": total(v), "order": v} for k, v in orders.items()}


# ---------- Unit 4: Banker's algorithm ----------
def banker(avail, mx, alloc):
    n, m = len(mx), len(avail)
    if n == 0 or len(alloc) != n or any(len(r) != m for r in mx + alloc):
        raise ValueError("Matrix sizes do not match the number of resources")
    need = [[mx[i][j] - alloc[i][j] for j in range(m)] for i in range(n)]
    if any(v < 0 for r in need for v in r):
        raise ValueError("Allocation is larger than maximum demand")
    work, done, seq = list(avail), [False] * n, []
    while len(seq) < n:
        for i in range(n):
            if not done[i] and all(need[i][j] <= work[j] for j in range(m)):
                work = [work[j] + alloc[i][j] for j in range(m)]
                done[i] = True
                seq.append(i)
                break
        else:
            break
    safe = len(seq) == n
    names = [f"P{i}" for i in seq]
    msg = ("Safe state: no deadlock risk. Safe sequence " + " -> ".join(names)) if safe else \
          "Unsafe state: deadlock is possible. Do not grant this request."
    return {"safe": safe, "sequence": names, "need": need, "message": msg}


# ---------- Unit 4: dining philosophers with deadlock detection ----------
def _cycle(edges):
    for s in edges:
        seen, x = [], s
        while x in edges and x not in seen:
            seen.append(x)
            x = edges[x]
        if x in seen:
            return seen[seen.index(x):] + [x]
    return None


def dining(n=5, strategy="naive"):
    n = max(2, min(8, n))
    owner, held, ate, log = [None] * n, [[] for _ in range(n)], [False] * n, []
    need = [[i, (i + 1) % n] if strategy == "naive" else sorted([i, (i + 1) % n]) for i in range(n)]
    for rnd in range(1, 40):
        acts = []
        for i in range(n):
            if ate[i]:
                continue
            f = need[i][len(held[i])]
            if owner[f] is None:
                owner[f] = i
                held[i].append(f)
                acts.append(f"P{i} takes fork {f}")
                if len(held[i]) == 2:
                    acts.append(f"P{i} eats and puts both forks down")
                    for k in held[i]:
                        owner[k] = None
                    held[i], ate[i] = [], True
        if all(ate):
            log.append(f"Round {rnd}: " + "; ".join(acts))
            return {"deadlock": False, "log": log,
                    "message": f"No deadlock: all {n} philosophers ate." +
                               (" Ordered fork pickup removes circular wait." if strategy != "naive" else "")}
        if not acts:
            edges = {i: owner[need[i][len(held[i])]] for i in range(n) if not ate[i]}
            cyc = _cycle(edges)
            log.append(f"Round {rnd}: nobody can proceed")
            path = " -> ".join(f"P{x}" for x in cyc) if cyc else "circular wait"
            return {"deadlock": True, "log": log, "message": f"Deadlock detected: circular wait {path}"}
        log.append(f"Round {rnd}: " + "; ".join(acts))
    return {"deadlock": False, "log": log, "message": "Stopped after 40 rounds"}


# ---------- Unit 3: race condition demo ----------
def race(threads=4, iters=5000):
    threads, iters = max(1, min(8, threads)), max(100, min(20000, iters))

    def run(use_lock):
        c, lock = [0], threading.Lock()

        def work():
            for _ in range(iters):
                if use_lock:
                    with lock:
                        v = c[0]
                        time.sleep(0)
                        c[0] = v + 1
                else:
                    v = c[0]
                    time.sleep(0)
                    c[0] = v + 1

        ts = [threading.Thread(target=work) for _ in range(threads)]
        t0 = time.time()
        [t.start() for t in ts]
        [t.join() for t in ts]
        return c[0], round(time.time() - t0, 3)

    exp = threads * iters
    nl, tn = run(False)
    wl, tw = run(True)
    return {"expected": exp,
            "without_lock": {"result": nl, "lost_updates": exp - nl, "seconds": tn},
            "with_lock": {"result": wl, "lost_updates": exp - wl, "seconds": tw}}
