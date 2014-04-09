#!/usr/bin/env python
import os
import sys
import worker

if __name__ == "__main__":
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "engine.settings")

    from django.core.management import execute_from_command_line

    worker.engine_thr_pool.init_pool()
    execute_from_command_line(sys.argv)
#     worker.engine_thr_pool.close_pool()
