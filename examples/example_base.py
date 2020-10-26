#!/usr/bin/env python
"""Run a simple silicon SCF calculation using AbinitBaseWorkChain.

Use the AbinitBaseWorkChain

Usage: python ./example_base.py --code abinit-9.2.1-ab@localhost --pseudo_family psp8
"""
import os

import click
import pymatgen as mg
from aiida import cmdline
from aiida.engine import run
from aiida.orm import Dict, Group, Str, StructureData
from aiida_abinit.workflows.base import AbinitBaseWorkChain

def example_base(code, pseudo_family):
    """Run simple silicon DFT calculation."""

    print("Testing the AbinitBaseWorkChain single-point on Silicon")

    thisdir = os.path.dirname(os.path.realpath(__file__))
    structure = StructureData(pymatgen=mg.Structure.from_file(os.path.join(thisdir, "files", 'Si.cif')))

    base_parameters_dict = {
        'pseudo_family': Str(pseudo_family),
        'abinit' : {
            'code': code,
            'structure': structure,
            'parameters': Dict(dict={
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
                }),
            'metadata': {
                'options': {
                    'withmpi': True,
                    'max_wallclock_seconds': 2 * 60,
                    'resources': {
                        'num_machines': 1,
                        'num_mpiprocs_per_machine': 4,
                    }
                }
            }            
        }  
    }
     
    print("Running work chain...")
    run(AbinitBaseWorkChain, **base_parameters_dict)    

PSEUDO_FAMILY = cmdline.params.options.OverridableOption('-P', '--pseudo_family', help='Psp8Family identified by its label')
@click.command()
@cmdline.utils.decorators.with_dbenv()
@cmdline.params.options.CODE()
@PSEUDO_FAMILY()
def cli(code, pseudo_family):
    """Run example.

    Example usage: $ python ./example_base.py --code abinit@localhost --pseudo_family psp8

    Help: $ python ./example_base.py --help
    """
    example_base(code, pseudo_family)

if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter