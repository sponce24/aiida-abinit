#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Run a simple silicon SCF calculation using AbinitCalculation.

Use the AbinitCalculation

Usage: python example_dft.py --code abinit-9.2.1-ab@localhost --pseudo_family psp8
"""
import os

import click
import pymatgen as mg
from aiida import cmdline
from aiida.engine import run
from aiida.orm import Dict, Group, StructureData, KpointsData
from aiida_abinit.calculations import AbinitCalculation


def example_dft(code, pseudo_family):
    """Run simple silicon DFT calculation."""

    print('Testing Abinit Total energy on Silicon using AbinitCalculation')

    thisdir = os.path.dirname(os.path.realpath(__file__))
    structure = StructureData(pymatgen=mg.core.Structure.from_file(os.path.join(thisdir, 'files', 'Si.cif')))
    pseudo_family = Group.objects.get(label=pseudo_family)
    pseudos = pseudo_family.get_pseudos(structure=structure)

    kpoints = KpointsData()
    kpoints.set_cell_from_structure(structure)
    kpoints.set_kpoints_mesh([2, 2, 2])

    parameters_dict = {
        'code':
        code,
        'structure':
        structure,
        'pseudos':
        pseudos,
        'kpoints':
        kpoints,
        'parameters':
        Dict(
            dict={
                'ecut': 8.0,  # Maximal kinetic energy cut-off, in Hartree
                'nstep': 20,  # Maximal number of SCF cycles
                'toldfe': 1.0e-6  # Will stop when, twice in a row, the difference
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
                    'num_mpiprocs_per_machine': 3,
                }
            }
        }
    }

    print('Running calculation...')
    run(AbinitCalculation, **parameters_dict)


PSEUDO_FAMILY = cmdline.params.options.OverridableOption(
    '-P', '--pseudo_family', help='Psp8Family identified by its label'
)


@click.command()
@cmdline.utils.decorators.with_dbenv()
@cmdline.params.options.CODE()
@PSEUDO_FAMILY()
def cli(code, pseudo_family):
    """Run example.

    Example usage: $ python ./example_dft.py --code abinit@localhost --pseudo_family psp8

    Help: $ python ./example_dft.py --help
    """
    example_dft(code, pseudo_family)


if __name__ == '__main__':
    cli()  # pylint: disable=no-value-for-parameter
