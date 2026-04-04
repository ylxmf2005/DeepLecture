import heapq
import os
import struct
from contextlib import ExitStack

REC_HDR = struct.Struct("<QQ")  # (query_len, count)
EST_OVERHEAD_PER_KEY = 128  # Python 粗估，每个新 key 的额外开销，实际可能更大


def normalize_line(raw: bytes) -> bytes:
    # 默认：只做换行规范化
    # 最后一行没 \n 也要能处理
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    if raw.endswith(b"\r"):
        raw = raw[:-1]
    return raw


def write_record(fp, query: bytes, cnt: int):
    fp.write(REC_HDR.pack(len(query), cnt))
    fp.write(query)


def read_record(fp):
    hdr = fp.read(REC_HDR.size)
    if not hdr:
        return None
    if len(hdr) != REC_HDR.size:
        raise OSError("corrupted run file header")
    qlen, cnt = REC_HDR.unpack(hdr)
    query = fp.read(qlen)
    if len(query) != qlen:
        raise OSError("corrupted run file body")
    return query, cnt


def flush_run(counts: dict, run_dir: str, run_id: int) -> str:
    items = sorted(counts.items(), key=lambda kv: kv[0])

    tmp_path = os.path.join(run_dir, f"run_{run_id:06d}.bin.tmp")
    fin_path = os.path.join(run_dir, f"run_{run_id:06d}.bin")

    with open(tmp_path, "wb", buffering=16 * 1024 * 1024) as fp:
        for query, cnt in items:
            write_record(fp, query, cnt)

    os.replace(tmp_path, fin_path)
    counts.clear()
    return fin_path


def merge_runs(run_paths, output_path):
    heap = []

    with ExitStack() as stack:
        files = [stack.enter_context(open(p, "rb", buffering=16 * 1024 * 1024)) for p in run_paths]

        for i, fp in enumerate(files):
            rec = read_record(fp)
            if rec is not None:
                query, cnt = rec
                heapq.heappush(heap, (query, cnt, i))

        out_tmp = output_path + ".tmp"
        total_out_count = 0

        with open(out_tmp, "wb", buffering=16 * 1024 * 1024) as out:
            cur_query = None
            cur_count = 0

            while heap:
                query, cnt, idx = heapq.heappop(heap)

                if cur_query is None:
                    cur_query = query
                    cur_count = cnt
                elif query == cur_query:
                    cur_count += cnt
                else:
                    # 输出格式建议 count 在前，方便解析
                    out.write(str(cur_count).encode("ascii") + b"\t" + cur_query + b"\n")
                    total_out_count += cur_count
                    cur_query = query
                    cur_count = cnt

                nxt = read_record(files[idx])
                if nxt is not None:
                    nq, nc = nxt
                    heapq.heappush(heap, (nq, nc, idx))

            if cur_query is not None:
                out.write(str(cur_count).encode("ascii") + b"\t" + cur_query + b"\n")
                total_out_count += cur_count

    os.replace(out_tmp, output_path)
    return total_out_count


def dedup_count(input_path, output_path, run_dir, mem_budget_bytes):
    os.makedirs(run_dir, exist_ok=True)

    counts = {}
    mem_est = 0
    run_paths = []
    total_input_lines = 0

    with open(input_path, "rb", buffering=16 * 1024 * 1024) as fin:
        for raw in fin:
            q = normalize_line(raw)
            total_input_lines += 1

            old = counts.get(q)
            if old is None:
                counts[q] = 1
                mem_est += len(q) + EST_OVERHEAD_PER_KEY
            else:
                counts[q] = old + 1

            if mem_est >= mem_budget_bytes:
                run_paths.append(flush_run(counts, run_dir, len(run_paths)))
                mem_est = 0

    if counts:
        run_paths.append(flush_run(counts, run_dir, len(run_paths)))

    # 如果 run 文件太多，应该做多阶段 merge，这里先写单阶段版本
    total_out_count = merge_runs(run_paths, output_path)

    if total_out_count != total_input_lines:
        raise RuntimeError(f"count mismatch: input_lines={total_input_lines}, output_sum={total_out_count}")
