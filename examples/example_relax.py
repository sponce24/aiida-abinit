#!/usr/bin/env python
"""Run a simple silicon DFT relaxation calculation on localhost.

Use the AbinitBaseWorkChain

Usage: python ./example_relax.py
"""
import os
import pymatgen as mg

from aiida import load_profile
from aiida.engine import run
from aiida.orm import (Code, Dict, StructureData)
from aiida_abinit.workchains.base import AbinitBaseWorkChain

load_profile()

# Pseudopotentials.
# You need to add it when setting up the code [prepend_text]

CODE = 'abinit-9.2.1-ab@localhost'
code = Code.get_from_string(CODE)
thisdir = os.path.dirname(os.path.realpath(__file__))

def example_base(code):
    """Run simple silicon DFT calculation."""

    print("Testing the AbinitBaseWorkChain on Silicon using DFT")

    thisdir = os.path.dirname(os.path.realpath(__file__))

    # Structure.
    structure = StructureData(pymatgen=mg.Structure.from_file(os.path.join(thisdir, "files", 'Si.cif')))

    base_parameters_dict = {
        'abinit' : {
            'code': code,
                'structure': structure,
                'parameters': Dict(dict={
                'optcell' : 2,       # Cell optimization
                'ionmov'  : 22,      # Atoms relaxation
                'tolmxf'  : 5.0e-5,  # Tolerence on the maximal force
                'ecutsm'  : 0.5,     # Energy cutoff smearing, in Hartree
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
                 }),
                'metadata': {
                    'options': {
                        'withmpi': True,
                        'max_wallclock_seconds': 10 * 60,
                        'resources': {
                            'num_machines': 1,
                            'num_mpiprocs_per_machine': 4,
                                    }
                                }
                            }            
                }  
            }
     
    run(AbinitBaseWorkChain, **base_parameters_dict)    

# Run the example
example_base(code)
