#!/usr/bin/env python
"""Run a simple silicon DFT calculation on localhost.

Usage: ./example_dft.py
"""
import os
import sys
import click

import pymatgen as mg

from aiida import cmdline
from aiida.engine import run
from aiida.orm import (Code, Dict, SinglefileData, StructureData)
from aiida.common import NotExistent

def example_dft(abinit_code):
    """Run simple silicon DFT calculation."""

    print("Testing Abinit Total energy on Silicon using DFT")

    thisdir = os.path.dirname(os.path.realpath(__file__))

    # Structure.
    structure = StructureData(pymatgen=mg.Structure.from_file(os.path.join(thisdir, "files", 'Si_mp-149_primitive.cif')))

    # Pseudopotentials.
    #pseudo_file = SinglefileData(file=os.path.join(thisdir, "..", "files", "GTH_POTENTIALS"))
    os.system('export $ABI_PSPDIR=/home/sponce/program/abinit-9.2.1/tests/Psps_for_tests')

    parameters_dict = {
        'ntypat'   :  1,
        'znucl'    :  1,
        'natom'    :  2,
        'ecut'     : 10,
        'kptopt'   :  0,
        'nkpt'     :  1,
        'nstep'    : 10,
        'toldfe'   : 1.0e-6,
        'pp_dirpath' : '\"$ABI_PSPDIR\"',
        'pseudos'    : '\"PseudosTM_pwteter/14si.pspnc\"'
    }
     
    builder = abinit_code.get_builder()
    builder.code = abinit_code
    builder.structure = structure
    builder.parameters = Dict(dict = parameters_dict)
    
    builder.metadata.options.withmpi = False
    builder.metadata.options.resources = {
        'num_machines': 1,
        'num_mpiprocs_per_machine': 1,
    
    }
    builder.metadata.options.max_wallclock_seconds = 120 
    builder.metadata.description = "Abinit silicon example DFT calculation."

    print("Submit calculation...")
    run(builder)

@click.command()
@cmdline.utils.decorators.with_dbenv()
@cmdline.params.options.CODE()
def cli(code):
    """Run example.

    Example usage: $ python ./example_dft.py --code abinit@localhost

    Help: $ python ./example_dft.py --help
    """
    example_dft(code)

if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
