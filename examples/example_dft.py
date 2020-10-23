#!/usr/bin/env python
"""Run a simple silicon DFT calculation on localhost.

Usage: python example_dft.py --code abinit-9.2.1-ab@localhost
"""
import os
import sys
import click
import pymatgen as mg

from aiida import cmdline
from aiida.engine import run
from aiida.orm import (Code, Dict, SinglefileData, StructureData)

# Pseudopotentials.
# You need to add it when setting up the code [prepend_text]

def example_dft(abinit_code):
    """Run simple silicon DFT calculation."""

    print("Testing Abinit Total energy on Silicon using DFT")

    thisdir = os.path.dirname(os.path.realpath(__file__))

    # Structure.
    structure = StructureData(pymatgen=mg.Structure.from_file(os.path.join(thisdir, "files", 'Si.cif')))

    parameters_dict = {
        'ecut'    : 8.0,     # Maximal kinetic energy cut-off, in Hartree
        'kptopt'  : 1,       # Option for the automatic generation of k points
        'ngkpt'   : '2 2 2', # This is a 2x2x2 grid based on the primitive vectors
        'nshiftk' : 1,       # of the reciprocal space (that form a BCC lattice !)
        'shiftk'  : '0 0 0',
        'nstep'   : 20,      # Maximal number of SCF cycles
        'toldfe'  : 1.0e-6,  # Will stop when, twice in a row, the difference 
                             # between two consecutive evaluations of total energy 
                             # differ by less than toldfe (in Hartree)
        'diemac'  : 12.0,    # Precondition for SCF cycle using a model dielectric
        'pp_dirpath' : '\"$ABI_PSPDIR\"',
        'pseudos'    : '\"PseudosTM_pwteter/14si.pspnc\"'
    }
     
    builder = abinit_code.get_builder()
    builder.code = abinit_code
    builder.structure = structure
    builder.parameters = Dict(dict = parameters_dict)
    
    builder.metadata.options.withmpi = True
    builder.metadata.options.resources = {
        'num_machines': 1,
        'num_mpiprocs_per_machine': 2,
    
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
