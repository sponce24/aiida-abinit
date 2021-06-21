# -*- coding: utf-8 -*-
"""Tests for the `AbinitCalculation` class."""
import pytest

from aiida import orm
from aiida.common import datastructures


def test_abinit_default(fixture_sandbox, generate_calc_job, generate_inputs_abinit, file_regression):
    """Test a default `AbinitCalculation`."""
    entry_point_name = 'abinit'

    inputs = generate_inputs_abinit()
    calc_info = generate_calc_job(fixture_sandbox, entry_point_name, inputs)
    psp8 = inputs['pseudos']['Si']

    cmdline_params = ['aiida.in', '--timelimit', '30:00']
    local_copy_list = [(psp8.uuid, psp8.filename, './pseudo/Si.psp8')]
    retrieve_list = ['aiida.out', 'aiida.abo', 'aiidao_OUT.nc', 'aiidao_EIG.nc', 'aiidao_GSR.nc']

    # Check the attributes of the returned `CalcInfo`
    assert isinstance(calc_info, datastructures.CalcInfo)
    assert isinstance(calc_info.codes_info[0], datastructures.CodeInfo)
    assert calc_info.codes_info[0].cmdline_params == cmdline_params
    assert sorted(calc_info.local_copy_list) == sorted(local_copy_list)
    assert sorted(calc_info.retrieve_list) == sorted(retrieve_list)
    assert sorted(calc_info.remote_symlink_list) == sorted([])

    with fixture_sandbox.open('aiida.in') as handle:
        input_written = handle.read()

    # Checks on the files written to the sandbox folder as raw input
    assert sorted(fixture_sandbox.get_content_list()) == sorted(['aiida.in', 'pseudo'])
    file_regression.check(input_written, encoding='utf-8', extension='.in')


@pytest.mark.parametrize(
    'ionmov,dry_run,retrieve_list',
    [(0, False, ['aiida.out', 'aiida.abo', 'aiidao_OUT.nc', 'aiidao_EIG.nc', 'aiidao_GSR.nc']),
     (2, False, ['aiida.out', 'aiida.abo', 'aiidao_OUT.nc', 'aiidao_EIG.nc', 'aiidao_GSR.nc', 'aiidao_HIST.nc']),
     (0, True, ['aiida.out', 'aiida.abo', 'aiidao_OUT.nc']), (2, True, ['aiida.out', 'aiida.abo', 'aiidao_OUT.nc'])]
)
def test_abinit_retrieve(
    fixture_sandbox, generate_calc_job, generate_inputs_abinit, file_regression, ionmov, dry_run, retrieve_list
):
    """Test an various retrieve list situations for `AbinitCalculation`."""
    entry_point_name = 'abinit'

    inputs = generate_inputs_abinit()
    inputs['parameters']['ionmov'] = ionmov
    inputs['settings'] = orm.Dict(dict={'DRY_RUN': dry_run})
    calc_info = generate_calc_job(fixture_sandbox, entry_point_name, inputs)

    assert sorted(calc_info.retrieve_list) == sorted(retrieve_list)

    with fixture_sandbox.open('aiida.in') as handle:
        input_written = handle.read()

    # Checks on the files written to the sandbox folder as raw input
    assert sorted(fixture_sandbox.get_content_list()) == sorted(['aiida.in', 'pseudo'])
    file_regression.check(input_written, encoding='utf-8', extension='.in')


# yapf: disable
@pytest.mark.parametrize(
    'settings,cmdline_params',
    [({'DrY_rUn': True, 'verbose': False}, ['aiida.in', '--timelimit', '30:00', '--dry-run']),
     ({'dry_run': True, 'verbose': True}, ['aiida.in', '--timelimit', '30:00', '--verbose', '--dry-run']),
     ({'DRY_RUN': False, 'verbose': True}, ['aiida.in', '--timelimit', '30:00', '--verbose'])]
)
# yapf: enable
def test_abinit_cmdline_params(fixture_sandbox, generate_calc_job, generate_inputs_abinit, settings, cmdline_params):
    """Test various command line parameters for `AbinitCalculation`."""
    entry_point_name = 'abinit'

    inputs = generate_inputs_abinit()
    inputs['settings'] = orm.Dict(dict=settings)
    calc_info = generate_calc_job(fixture_sandbox, entry_point_name, inputs)

    assert calc_info.codes_info[0].cmdline_params == cmdline_params
