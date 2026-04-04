"""Pseudocode notes for the bucketed dedup/count pipeline.

MEM_BUDGET = xxx  # 之后假设为 24G

# 0. The number of buckets
num_buckets = (file_size / MEM_BUDGET) * k1 * k2
# k1 是膨胀系数，因为文件读取后得到的数据结构，大小可能会膨胀，尤其是 Python，实际可以考虑用 C++。
# k2 是计数环节期望进程数
# 计数处理流程是 Read -> CPU -> Write，SSD 的带宽较大(如5GB/s)。
# MEM_BUDGET 是内存预算，如果不 * k2，期望每个桶刚好占满内存，实际上会导致: SSD 空闲 + 多核 CPU 没有充分利用 + 刚好塞不下第二个 bucket 进一步浪费。
# 我们暂且设 k2 = 8 (cpu >= 8 核), k1 = 2 (C++), MEM_BUDGET=24GB(比如32G的机器)
# num_buckets: 1024 / 24 = 42, 42 * 8 * 2 = 672
# 8 个块大概会让碎片更小，CPU 处理的时间更短（进而减少磁盘空闲等待时间）；当然如果内存利用满的话，SSD 的速度其实 8 个和 1 个块是差不太多的。
# 但要注意 file pointer 个数上限，但 672 不至于超
# 实际的边界情况要考虑某些块过大 / 过小。最简单的办法是啥也不干，能并行多少个就并行多少个（只要不超过 8）
# 理论更优的，可以考虑拆分/合并，合并还好说，但拆分的话要考虑不能把一个 key 拆成多个部分，但其实也好解决，有几个就模几就好了。但还是无法解决一个极端情况，就是数据太倾斜了（热 key），最极限就是 2 个桶，拆完后发现一个桶接近 0，数据全跑另一个桶了。这种情况其实倒也没关系，因为这种情况反而不会爆内存，所以可以假装没发生；或者考虑拆分更多的小块，再组装成大块。
# 实际上应该不用考虑这么多，理论最优的太麻烦而且不一定真优，让我们采用第一种方法

# 1. 分桶
open file pointers: f[N]

with open input_file:
    for line in input_file:
        id = hash(line) % N
        f[id].append(line)

close all f[N]

# 2. 多进程并行计数
task_queue

open file pointers: f[k2]  # 每 worker 拥有自己的输出文件，各写各的，不用加锁（锁可能会让并行写退化成串行）

启动 k2 个进程:
    each worker with its f[i]:
        while task_queue not empty:
            bucket_id = task_queue.pop()
            bucket = read_bucket(bucket_id)
            counts = {}  # unordered_map in C++
            counts = count(line) for line in bucket
            write counts to f[i]
            delete bucket

wait for all workers

# 3. 合并输出
concat all worker output_files into final output
"""
