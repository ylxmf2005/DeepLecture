"""
大文件去重计数 —— 分桶 v2（工程化版本）

解决的问题：
  1. 桶数量怎么定？ → 根据文件大小和内存预算自动计算
  2. 单机文件描述符有限？ → 分批写桶，不同时打开太多文件
  3. 某个桶哈希倾斜太大？ → 检测超大桶，用不同 seed 二次分桶
  4. 逐桶计数能并行吗？ → 用多进程并行处理独立的桶
"""

import hashlib
import os
import resource
from concurrent.futures import ProcessPoolExecutor, as_completed

# ──────────────────────────────────────────────
# 配置
# ──────────────────────────────────────────────

DEFAULT_MEM_BUDGET = 512 * 1024 * 1024  # 512 MB，期望每个桶加载后不超过这个
FD_RESERVE = 64  # 留给系统的文件描述符数量
WRITE_BATCH_SIZE = 4096  # 每攒这么多行才 flush 一次，减少系统调用


# ══════════════════════════════════════════════
# 第零步：自动决定桶的数量
# ══════════════════════════════════════════════
#
#   思路很简单：
#     num_buckets = ceil(file_size / mem_budget)
#
#   但还要受两个上限约束：
#     - 文件描述符上限（ulimit -n）
#     - 实际经验值上限（桶太多 → 分桶阶段随机写太碎，磁盘吃不消）
#
#   所以：
#     num_buckets = min(
#         ceil(file_size / mem_budget),   # 内存约束
#         fd_limit - FD_RESERVE,          # 文件描述符约束
#         4096                            # 经验上限
#     )


def decide_num_buckets(file_size: int, mem_budget: int) -> int:
    if file_size == 0:
        return 1

    # 内存约束：文件大小 / 每桶预算，向上取整
    by_mem = max(1, -(-file_size // mem_budget))  # ceil division trick

    # 文件描述符约束
    soft_limit, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    by_fd = soft_limit - FD_RESERVE

    # 取三者最小值
    num = min(by_mem, by_fd, 4096)
    return max(1, num)


# ══════════════════════════════════════════════
# 第一步：分桶（Partition）
# ══════════════════════════════════════════════
#
#   为什么用 md5 而不是 Python 内置 hash()？
#     - hash() 在不同进程/运行中结果不同（PYTHONHASHSEED 随机化）
#     - 二次分桶时需要换 seed，md5(seed + line) 可控且均匀


def hash_to_bucket(line: bytes, num_buckets: int, seed: int = 0) -> int:
    h = hashlib.md5(seed.to_bytes(4, "little") + line).digest()
    # 取前 4 字节当 uint32，再取模
    val = int.from_bytes(h[:4], "little")
    return val % num_buckets


def partition(input_path: str, bucket_dir: str, num_buckets: int, seed: int = 0) -> list[str]:
    """把输入文件分到 num_buckets 个桶文件里，返回桶文件路径列表。"""

    bucket_paths = [os.path.join(bucket_dir, f"bucket_{seed}_{i:04d}.bin") for i in range(num_buckets)]

    # ── 分批写策略 ──
    # 不是同时打开所有桶文件，而是在内存里攒 buffer，满了再刷
    # 这样同一时刻只需要打开一个文件
    buffers: list[list[bytes]] = [[] for _ in range(num_buckets)]
    buf_bytes = 0

    def flush_all():
        nonlocal buf_bytes
        for i, buf in enumerate(buffers):
            if buf:
                with open(bucket_paths[i], "ab") as fp:
                    fp.write(b"".join(buf))
                buf.clear()
        buf_bytes = 0

    with open(input_path, "rb", buffering=16 * 1024 * 1024) as fin:
        for raw in fin:
            line = raw.rstrip(b"\r\n")
            i = hash_to_bucket(line, num_buckets, seed)
            entry = line + b"\n"
            buffers[i].append(entry)
            buf_bytes += len(entry)

            # 内存里攒的数据超过 64MB 就刷一次
            if buf_bytes >= 64 * 1024 * 1024:
                flush_all()

    flush_all()
    return bucket_paths


# ══════════════════════════════════════════════
# 第二步：逐桶计数（支持二次分桶）
# ══════════════════════════════════════════════
#
#   如果某个桶文件太大（比如 > mem_budget），
#   说明这个桶里的行太多了，一次放不进内存。
#   解决方法：用不同的 seed 对这个桶再做一次分桶。


def count_one_bucket(bucket_path: str, mem_budget: int, bucket_dir: str) -> list[tuple[bytes, int]]:
    """
    处理单个桶，返回 [(line, count), ...]。
    如果桶太大，递归二次分桶。
    """
    file_size = os.path.getsize(bucket_path)

    if file_size <= mem_budget:
        # ── 正常路径：桶够小，直接在内存里计数 ──
        counts: dict[bytes, int] = {}
        with open(bucket_path, "rb") as fb:
            for raw in fb:
                line = raw.rstrip(b"\n")
                counts[line] = counts.get(line, 0) + 1
        return list(counts.items())

    else:
        # ── 异常路径：桶太大，二次分桶 ──
        #   用 seed=1（或更高）重新 partition 这个超大桶
        #   然后递归处理每个子桶
        sub_dir = os.path.join(bucket_dir, "resplit_" + os.path.basename(bucket_path))
        sub_n = max(4, -(-file_size // mem_budget))
        sub_paths = partition(bucket_path, sub_dir, sub_n, seed=1)

        results = []
        for sp in sub_paths:
            if os.path.exists(sp) and os.path.getsize(sp) > 0:
                results.extend(count_one_bucket(sp, mem_budget, sub_dir))
                os.remove(sp)
        return results


# ══════════════════════════════════════════════
# 第三步：多进程并行
# ══════════════════════════════════════════════
#
#   每个桶之间完全独立，天然适合并行。
#
#   为什么用多进程而不是多线程？
#     - dict 计数是 CPU 密集的（大量哈希计算和内存分配）
#     - Python 的 GIL 会让多线程在 CPU 密集任务上退化为串行
#     - 多进程绕过 GIL，真正利用多核
#
#   worker 数量 = min(CPU 核数, 桶数量)
#   不能开太多，否则：
#     - 每个 worker 都要加载一个桶到内存 → 总内存 = worker数 × 桶大小
#     - 所以 max_workers 还要受 总内存预算 / 单桶预算 约束


def _worker(args):
    """在子进程里执行，处理单个桶。"""
    bucket_path, mem_budget, bucket_dir = args
    if not os.path.exists(bucket_path) or os.path.getsize(bucket_path) == 0:
        return []
    result = count_one_bucket(bucket_path, mem_budget, bucket_dir)
    os.remove(bucket_path)
    return result


def dedup_count_parallel(
    input_path: str,
    output_path: str,
    bucket_dir: str,
    mem_budget: int = DEFAULT_MEM_BUDGET,
    max_workers: int | None = None,
):
    os.makedirs(bucket_dir, exist_ok=True)

    file_size = os.path.getsize(input_path)
    num_buckets = decide_num_buckets(file_size, mem_budget)

    # 计算总行数（用于最后校验）
    total_lines = 0
    with open(input_path, "rb") as f:
        for _ in f:
            total_lines += 1

    print(f"文件大小: {file_size / 1024**3:.2f} GB")
    print(f"内存预算: {mem_budget / 1024**2:.0f} MB/桶")
    print(f"桶数量:   {num_buckets}")
    print(f"总行数:   {total_lines}")

    # ── 第一步：分桶 ──
    print("分桶中...")
    bucket_paths = partition(input_path, bucket_dir, num_buckets)

    # ── 第二步 + 第三步：多进程并行计数 ──
    if max_workers is None:
        cpu_count = os.cpu_count() or 4
        # 并行度受限于：CPU 核数、桶数量、总内存（每个 worker 占一份 mem_budget）
        max_workers = min(cpu_count, num_buckets, max(1, (mem_budget * num_buckets) // mem_budget))
        max_workers = min(max_workers, cpu_count)

    print(f"并行计数中... (workers={max_workers})")

    total_out = 0
    out_tmp = output_path + ".tmp"

    with (
        open(out_tmp, "wb", buffering=16 * 1024 * 1024) as fout,
        ProcessPoolExecutor(max_workers=max_workers) as pool,
    ):
        tasks = [(bp, mem_budget, bucket_dir) for bp in bucket_paths]
        futures = {pool.submit(_worker, t): t for t in tasks}

        for future in as_completed(futures):
            results = future.result()
            for line, cnt in results:
                fout.write(str(cnt).encode("ascii") + b"\t" + line + b"\n")
                total_out += cnt

    os.replace(out_tmp, output_path)

    # ── 校验 ──
    if total_out != total_lines:
        raise RuntimeError(f"数据丢失！输入 {total_lines} 行，输出合计 {total_out}")

    print(f"完成！唯一行写入 {output_path}")


# ══════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("用法: python 1_bucket_v2.py <输入文件> <输出文件> [内存预算MB]")
        sys.exit(1)

    inp, out = sys.argv[1], sys.argv[2]
    mem = int(sys.argv[3]) * 1024 * 1024 if len(sys.argv) > 3 else DEFAULT_MEM_BUDGET

    dedup_count_parallel(inp, out, bucket_dir=".buckets", mem_budget=mem)
