# -*- coding: utf-8 -*-
"""Tests for the `AbinitCalculation` class."""
from aiida.common import datastructures


def test_pw_default(fixture_sandbox, generate_calc_job, generate_inputs_abinit, file_regression):
    """Test a default `Abinitcalculation`."""
    entry_point_name = 'abinit'

    inputs = generate_inputs_abinit()
    calc_info = generate_calc_job(fixture_sandbox, entry_point_name, inputs)
    psp8 = inputs['pseudos']['Si']

    cmdline_params = ['-in', 'aiida.in']
    local_copy_list = [(psp8.uuid, psp8.filename, './pseudo/Si.psp8')]
    retrieve_list = ['aiida.out', 'aiidao_GSR.nc']

    # Check the attributes of the returned `CalcInfo`
    assert isinstance(calc_info, datastructures.CalcInfo)
    assert isinstance(calc_info.codes_info[0], datastructures.CodeInfo)
    assert sorted(calc_info.codes_info[0].cmdline_params) == cmdline_params
    assert sorted(calc_info.local_copy_list) == sorted(local_copy_list)
    assert sorted(calc_info.retrieve_list) == sorted(retrieve_list)
    assert sorted(calc_info.remote_symlink_list) == sorted([])

    with fixture_sandbox.open('aiida.in') as handle:
        input_written = handle.read()

    # Checks on the files written to the sandbox folder as raw input
    assert sorted(fixture_sandbox.get_content_list()) == sorted(['aiida.in', 'pseudo'])
    file_regression.check(input_written, encoding='utf-8', extension='.in')
