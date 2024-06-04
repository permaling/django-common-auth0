from __future__ import unicode_literals

__author__ = 'David Baum'

from multiprocessing import Pool
from typing import Callable, List

import tqdm


def run_processes_pool(function: Callable, data: List, verbose: bool, num_workers: int) -> List:
    num_workers = 1 if num_workers < 1 else num_workers
    pool = Pool(processes=num_workers)
    results = list(
        tqdm.tqdm(pool.imap(function, data, 100), total=len(data), disable=not verbose)
    )
    pool.close()
    pool.join()
    return results
