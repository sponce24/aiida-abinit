#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run a simple silicon SCF calculation using AbinitBaseWorkChain.

Use the AbinitBaseWorkChain

Usage: python ./example_base.py --code abinit-9.2.1-ab@localhost --pseudo_family nc-sr-04_pbe_standard_psp8
"""
import os

import click
import pymatgen as pmg
from aiida import cmdline
from aiida.engine import run
from aiida.orm import Float, Dict, Group, StructureData
from aiida_abinit.workflows.base import AbinitBaseWorkChain


def example_base(code, pseudo_family):
    """Run simple silicon DFT calculation."""

    print('Testing the AbinitBaseWorkChain single-point on Silicon')

    thisdir = os.path.dirname(os.path.realpath(__file__))
    structure = StructureData(pymatgen=pmg.core.Structure.from_file(os.path.join(thisdir, 'files', 'Si.cif')))
    pseudo_family = Group.objects.get(label=pseudo_family)
    pseudos = pseudo_family.get_pseudos(structure=structure)

    base_parameters_dict = {
        'kpoints_distance': Float(0.3),  # 1 / Angstrom
        'abinit': {
            'code':
            code,
            'structure':
            structure,
            'pseudos':
            pseudos,
            'parameters':
            Dict(
                dict={
                    'ecut': 8.0,  # Maximal kinetic energy cut-off, in Hartree
                    'nstep': 20,  # Maximal number of SCF cycles
                    'toldfe': 1.0e-6,  # Will stop when, twice in a row, the difference
                    # between two consecutive evaluations of total energy
                    # differ by less than toldfe (in Hartree)
                }
            ),
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

    print('Running work chain...')
    run(AbinitBaseWorkChain, **base_parameters_dict)


PSEUDO_FAMILY = cmdline.params.options.OverridableOption(
    '-P', '--pseudo_family', help='Psp8Family identified by its label'
)


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
