# -*- coding: utf-8 -*-
"""Utilities for calculation job resources."""

__all__ = (
    'get_default_options',
    'seconds_to_timelimit',
)


def get_default_options(max_num_machines: int = 1, max_wallclock_seconds: int = 1800, with_mpi: bool = False) -> dict:
    """Return an instance of the options dictionary with the minimally required parameters for a `CalcJob`.

    :param max_num_machines: set the number of nodes, default=1
    :param max_wallclock_seconds: set the maximum number of wallclock seconds, default=1800
    :param with_mpi: whether to run the calculation with MPI enabled
    """
    return {
        'resources': {
            'num_machines': int(max_num_machines)
        },
        'max_wallclock_seconds': int(max_wallclock_seconds),
        'withmpi': with_mpi,
    }


def seconds_to_timelimit(seconds: int) -> str:
    """Convert seconds into a Slum-notation time limit for the ABINIT flag `--timelimit`.

    :param seconds: time limit in seconds
    :returns: Slurm-notation time limit (hours:minutes:seconds)
    """
    days = seconds // 86400
    seconds -= days * 86400
    hours = seconds // 3600
    seconds -= hours * 3600
    minutes = seconds // 60
    seconds -= minutes * 60
    timelimit = ''
    if days > 0:
        timelimit += f'{days}-'
    if hours > 0:
        timelimit += f'{hours:02d}:'
    timelimit += f'{minutes:02d}:{seconds:02d}'
    return timelimit
