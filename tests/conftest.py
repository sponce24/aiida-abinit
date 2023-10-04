# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name,too-many-statements
"""Initialise a text database and profile for pytest."""
import collections
import io
import os
import pathlib
import shutil
import tempfile

import pytest

pytest_plugins = ['aiida.manage.tests.pytest_fixtures']  # pylint: disable=invalid-name


@pytest.fixture(scope='session')
def filepath_tests():
    """Return the absolute filepath of the `tests` folder.

    .. warning:: if this file moves with respect to the `tests` folder, the implementation should change.

    :return: absolute filepath of `tests` folder which is the basepath for all test resources.
    """
    return os.path.dirname(os.path.abspath(__file__))


@pytest.fixture
def filepath_fixtures(filepath_tests):
    """Return the absolute filepath to the directory containing the file `fixtures`."""
    return os.path.join(filepath_tests, 'fixtures')


@pytest.fixture(scope='function')
def fixture_sandbox():
    """Return a `SandboxFolder`."""
    from aiida.common.folders import SandboxFolder
    with SandboxFolder() as folder:
        yield folder


@pytest.fixture
def fixture_localhost(aiida_localhost):
    """Return a localhost `Computer`."""
    localhost = aiida_localhost
    localhost.set_default_mpiprocs_per_machine(1)
    return localhost


@pytest.fixture
def fixture_code(fixture_localhost):
    """Return a `Code` instance configured to run calculations of given entry point on localhost `Computer`."""

    def _fixture_code(entry_point_name):
        from aiida.common import exceptions
        from aiida.orm import Code

        label = f'test.{entry_point_name}'

        try:
            return Code.objects.get(label=label)  # pylint: disable=no-member
        except exceptions.NotExistent:
            return Code(
                label=label,
                input_plugin_name=entry_point_name,
                remote_computer_exec=[fixture_localhost, '/bin/true'],
            )

    return _fixture_code


@pytest.fixture
def serialize_builder():
    """Serialize the given process builder into a dictionary with nodes turned into their value representation.

    :param builder: the process builder to serialize
    :return: dictionary
    """

    def serialize_data(data):
        # pylint: disable=too-many-return-statements
        from aiida.orm import BaseType, Dict, Code
        from aiida.plugins import DataFactory

        StructureData = DataFactory('structure')
        Psp8Data = DataFactory('pseudo.psp8')

        if isinstance(data, dict):
            return {key: serialize_data(value) for key, value in data.items()}

        if isinstance(data, BaseType):
            return data.value

        if isinstance(data, Code):
            return data.full_label

        if isinstance(data, Dict):
            return data.get_dict()

        if isinstance(data, StructureData):
            return data.get_formula()

        if isinstance(data, Psp8Data):
            return f'{data.element}<md5={data.md5}>'

        return data

    def _serialize_builder(builder):
        return serialize_data(builder._inputs(prune=True))  # pylint: disable=protected-access

    return _serialize_builder


@pytest.fixture(scope='session', autouse=True)
@pytest.mark.usefixtures('aiida_profile_clean')
def pseudo_dojo(generate_psp8_data):
    """Create an PseudoDojo pseudo potential family from scratch."""
    from aiida.common.constants import elements
    from aiida.plugins import GroupFactory, DataFactory

    PseudoDojo = GroupFactory('pseudo.family.pseudo_dojo')  # pylint: disable=invalid-name
    Psp8Data = DataFactory('pseudo.psp8')

    cutoffs = {}
    stringency = 'standard'

    with tempfile.TemporaryDirectory() as dirpath:
        for values in elements.values():

            element = values['symbol']
            psp8 = generate_psp8_data(element)
            filename = os.path.join(dirpath, f'{element}.psp8')

            with open(filename, 'w+b') as handle:
                with psp8.open(mode='rb') as source:
                    handle.write(source.read())
                    handle.flush()

            cutoffs[element] = {
                'cutoff_wfc': 36.0,
                'cutoff_rho': 144.0,
            }

        label = 'PseudoDojo/0.4/PBE/SR/standard/psp8'
        family = PseudoDojo.create_from_folder(pathlib.Path(dirpath), label, pseudo_type=Psp8Data)

    family.set_cutoffs(cutoffs, stringency, unit='Ry')

    return family


@pytest.fixture
def generate_calc_job():
    """Fixture to construct a new `CalcJob` instance and call `prepare_for_submission` for testing `CalcJob` classes.

    The fixture will return the `CalcInfo` returned by `prepare_for_submission` and the temporary folder that was passed
    to it, into which the raw input files will have been written.
    """

    def _generate_calc_job(folder, entry_point_name, inputs=None):
        """Fixture to generate a mock `CalcInfo` for testing calculation jobs."""
        from aiida.engine.utils import instantiate_process
        from aiida.manage.manager import get_manager
        from aiida.plugins import CalculationFactory

        manager = get_manager()
        runner = manager.get_runner()

        process_class = CalculationFactory(entry_point_name)
        process = instantiate_process(runner, process_class, **inputs)

        calc_info = process.prepare_for_submission(folder)

        return calc_info

    return _generate_calc_job


@pytest.fixture
def generate_calc_job_node(fixture_localhost):
    """Fixture to generate a mock `CalcJobNode` for testing parsers."""

    def flatten_inputs(inputs, prefix=''):
        """Flatten inputs recursively like :meth:`aiida.engine.processes.process::Process._flatten_inputs`."""
        flat_inputs = []
        for key, value in inputs.items():
            if isinstance(value, collections.Mapping):
                flat_inputs.extend(flatten_inputs(value, prefix=prefix + key + '__'))
            else:
                flat_inputs.append((prefix + key, value))
        return flat_inputs

    def _generate_calc_job_node(
        entry_point_name='base', computer=None, test_name=None, inputs=None, attributes=None, retrieve_temporary=None
    ):
        """Fixture to generate a mock `CalcJobNode` for testing parsers.

        :param entry_point_name: entry point name of the calculation class
        :param computer: a `Computer` instance
        :param test_name: relative path of directory with test output files in the `fixtures/{entry_point_name}` folder.
        :param inputs: any optional nodes to add as input links to the corrent CalcJobNode
        :param attributes: any optional attributes to set on the node
        :param retrieve_temporary: optional tuple of an absolute filepath of a temporary directory and a list of
            filenames that should be written to this directory, which will serve as the `retrieved_temporary_folder`.
            For now this only works with top-level files and does not support files nested in directories.
        :return: `CalcJobNode` instance with an attached `FolderData` as the `retrieved` node.
        """
        from aiida import orm
        from aiida.common import LinkType
        from aiida.plugins.entry_point import format_entry_point_string

        if computer is None:
            computer = fixture_localhost

        filepath_folder = None

        if test_name is not None:
            basepath = os.path.dirname(os.path.abspath(__file__))
            filename = os.path.join(entry_point_name[len('abinit.'):], test_name)
            filepath_folder = os.path.join(basepath, 'parsers', 'fixtures', filename)
            filepath_input = os.path.join(filepath_folder, 'aiida.in')

        entry_point = format_entry_point_string('aiida.calculations', entry_point_name)

        node = orm.CalcJobNode(computer=computer, process_type=entry_point)
        node.set_attribute('input_filename', 'aiida.in')
        node.set_attribute('output_filename', 'aiida.out')
        node.set_attribute('error_filename', 'aiida.err')
        node.set_option('resources', {'num_machines': 1, 'num_mpiprocs_per_machine': 1})
        node.set_option('max_wallclock_seconds', 1800)

        if attributes:
            node.set_attribute_many(attributes)

        if filepath_folder:
            from aiida.orm import StructureData
            from abipy.abio.abivars import AbinitInputFile
            try:
                parsed_input = AbinitInputFile(filepath_input)
            except FileNotFoundError:
                pass
            else:
                inputs['structure'] = StructureData(pymatgen=parsed_input.structure)
                inputs['parameters'] = orm.Dict(dict=parsed_input.datasets[0])

        if inputs:
            metadata = inputs.pop('metadata', {})
            options = metadata.get('options', {})

            for name, option in options.items():
                node.set_option(name, option)

            for link_label, input_node in flatten_inputs(inputs):
                input_node.store()
                node.add_incoming(input_node, link_type=LinkType.INPUT_CALC, link_label=link_label)

        node.store()

        if retrieve_temporary:
            dirpath, filenames = retrieve_temporary
            for filename in filenames:
                shutil.copy(os.path.join(filepath_folder, filename), os.path.join(dirpath, filename))

        if filepath_folder:
            retrieved = orm.FolderData()
            retrieved.put_object_from_tree(filepath_folder)

            # Remove files that are supposed to be only present in the retrieved temporary folder
            if retrieve_temporary:
                for filename in filenames:
                    retrieved.delete_object(filename)

            retrieved.add_incoming(node, link_type=LinkType.CREATE, link_label='retrieved')
            retrieved.store()

            remote_folder = orm.RemoteData(computer=computer, remote_path='/tmp')
            remote_folder.add_incoming(node, link_type=LinkType.CREATE, link_label='remote_folder')
            remote_folder.store()

        return node

    return _generate_calc_job_node


@pytest.fixture(scope='session')
def generate_psp8_data():
    """Return a `Psp8Data` instance for the given element a file for which should exist in `tests/fixtures/pseudos`."""

    def _generate_psp8_data(element):
        """Return `Pps8Data` node."""
        from aiida_pseudo.data.pseudo import Psp8Data
        from aiida.common.constants import elements
        try:
            atomic_number = [number for number in elements if elements[number]['symbol'] == element]
            atomic_number = float(atomic_number[0])
        except IndexError as error:
            raise ValueError(f'Could not associate an atomic number to {element}.') from error
        content = f'{element}    ONCVPSP-3.2.3.1  r_core=   1.60303   1.72197   1.91712\n' \
                  f'{atomic_number:0.4f}      4.0000      170510    zatom,zion,pspd\n' \
                   '8      11   2     4   600     0    pspcod,pspxc,lmax,lloc,mmax,r2well\n' \
                   '5.99000000  4.00000000  0.00000000    rchrg fchrg qchrg\n' \
                   '2     2     2     0     0    nproj\n' \
                   '1     1           extension_switch'
        stream = io.BytesIO(content.encode('utf-8'))
        return Psp8Data(stream, filename=f'{element}.psp8')

    return _generate_psp8_data


@pytest.fixture
def generate_structure():
    """Return a `StructureData` representing bulk silicon."""

    def _generate_structure(structure_id='silicon'):
        """Return a `StructureData` representing bulk silicon or a snapshot of a single water molecule dynamics."""
        from aiida.orm import StructureData

        if structure_id == 'silicon':
            param = 5.43
            cell = [[param / 2., param / 2., 0], [param / 2., 0, param / 2.], [0, param / 2., param / 2.]]
            structure = StructureData(cell=cell)
            structure.append_atom(position=(0., 0., 0.), symbols='Si', name='Si')
            structure.append_atom(position=(param / 4., param / 4., param / 4.), symbols='Si', name='Si')
        elif structure_id == 'water':
            structure = StructureData(cell=[[5.29177209, 0., 0.], [0., 5.29177209, 0.], [0., 0., 5.29177209]])
            structure.append_atom(position=[12.73464656, 16.7741411, 24.35076238], symbols='H', name='H')
            structure.append_atom(position=[-29.3865565, 9.51707929, -4.02515904], symbols='H', name='H')
            structure.append_atom(position=[1.04074437, -1.64320127, -1.27035021], symbols='O', name='O')
        else:
            raise KeyError('Unknown structure_id=\'{}\''.format(structure_id))
        return structure

    return _generate_structure


@pytest.fixture
def generate_kpoints_mesh():
    """Return a `KpointsData` node."""

    def _generate_kpoints_mesh(npoints):
        """Return a `KpointsData` with a mesh of npoints in each direction."""
        from aiida.orm import KpointsData

        kpoints = KpointsData()
        kpoints.set_kpoints_mesh([npoints] * 3)

        return kpoints

    return _generate_kpoints_mesh


@pytest.fixture(scope='session')
def generate_parser():
    """Fixture to load a parser class for testing parsers."""

    def _generate_parser(entry_point_name):
        """Fixture to load a parser class for testing parsers.

        :param entry_point_name: entry point name of the parser class
        :return: the `Parser` sub class
        """
        from aiida.plugins import ParserFactory
        return ParserFactory(entry_point_name)

    return _generate_parser


@pytest.fixture
def generate_remote_data():
    """Return a `RemoteData` node."""

    def _generate_remote_data(computer, remote_path, entry_point_name=None):
        """Return a `KpointsData` with a mesh of npoints in each direction."""
        from aiida.common.links import LinkType
        from aiida.orm import CalcJobNode, RemoteData
        from aiida.plugins.entry_point import format_entry_point_string

        entry_point = format_entry_point_string('aiida.calculations', entry_point_name)

        remote = RemoteData(remote_path=remote_path)
        remote.computer = computer

        if entry_point_name is not None:
            creator = CalcJobNode(computer=computer, process_type=entry_point)
            creator.set_option('resources', {'num_machines': 1, 'num_mpiprocs_per_machine': 1})
            remote.add_incoming(creator, link_type=LinkType.CREATE, link_label='remote_folder')
            creator.store()

        return remote

    return _generate_remote_data


@pytest.fixture
def generate_bands_data():
    """Return a `BandsData` node."""

    def _generate_bands_data():
        """Return a `BandsData` instance with some basic `kpoints` and `bands` arrays."""
        import numpy
        from aiida.plugins import DataFactory
        BandsData = DataFactory('array.bands')  # pylint: disable=invalid-name
        bands_data = BandsData()

        bands_data.set_kpoints(numpy.array([[0., 0., 0.], [0.625, 0.25, 0.625]]))

        bands_data.set_bands(
            numpy.array([[-5.64024889, 6.66929678, 6.66929678, 6.66929678, 8.91047649],
                         [-1.71354964, -0.74425095, 1.82242466, 3.98697455, 7.37979746]]),
            units='eV'
        )

        return bands_data

    return _generate_bands_data


@pytest.fixture
def generate_workchain():
    """Generate an instance of a `WorkChain`."""

    def _generate_workchain(entry_point, inputs):
        """Generate an instance of a `WorkChain` with the given entry point and inputs.

        :param entry_point: entry point name of the work chain subclass.
        :param inputs: inputs to be passed to process construction.
        :return: a `WorkChain` instance.
        """
        from aiida.engine.utils import instantiate_process
        from aiida.manage.manager import get_manager
        from aiida.plugins import WorkflowFactory

        process_class = WorkflowFactory(entry_point)
        runner = get_manager().get_runner()
        process = instantiate_process(runner, process_class, **inputs)

        return process

    return _generate_workchain


@pytest.fixture
def generate_inputs_abinit(fixture_code, generate_structure, generate_kpoints_mesh, generate_psp8_data):
    """Generate default inputs for an `AbinitCalculation."""

    def _generate_inputs_abinit():
        """Generate default inputs for an `AbinitCalculation."""
        from aiida.orm import Dict
        from aiida_abinit.utils.resources import get_default_options

        inputs = {
            'code': fixture_code('abinit'),
            'structure': generate_structure(),
            'kpoints': generate_kpoints_mesh(2),
            'parameters': Dict(dict={
                'ecut': 18.0,
                'nstep': 20,
                'toldfe': 1.0e-6
            }),
            'pseudos': {
                'Si': generate_psp8_data('Si')
            },
            'metadata': {
                'options': get_default_options()
            }
        }

        return inputs

    return _generate_inputs_abinit


@pytest.fixture
def generate_workchain_abinit(generate_workchain, generate_inputs_abinit, generate_calc_job_node):
    """Generate an instance of a `AbinitBaseWorkChain`."""

    def _generate_workchain_abinit(exit_code=None, inputs=None, return_inputs=False):
        from plumpy import ProcessState
        from aiida.orm import Dict

        entry_point = 'abinit.base'

        if inputs is None:
            abinit_inputs = generate_inputs_abinit()
            kpoints = abinit_inputs.pop('kpoints')
            inputs = {'abinit': abinit_inputs, 'kpoints': kpoints}

        if return_inputs:
            return inputs

        process = generate_workchain(entry_point, inputs)

        if exit_code is not None:
            node = generate_calc_job_node(inputs={'parameters': Dict()})
            node.set_process_state(ProcessState.FINISHED)
            node.set_exit_status(exit_code.status)

            process.ctx.iteration = 1
            process.ctx.children = [node]

        return process

    return _generate_workchain_abinit
