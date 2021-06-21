# -*- coding: utf-8 -*-
"""CalcJob class for Abinit."""
import io

# from pymatgen.core import Element
from pymatgen.io.abinit.abiobjects import structure_to_abivars
from abipy.abio.inputs import AbinitInput
from abipy.core.structure import Structure as AbiStructure
from abipy.data.hgh_pseudos import HGH_TABLE

from aiida import orm
from aiida.common import constants, datastructures, exceptions
from aiida.engine import CalcJob
from aiida.orm import RemoteData
from aiida_pseudo.data.pseudo import Psp8Data, JthXmlData


class AbinitCalculation(CalcJob):
    """AiiDA calculation plugin wrapping the abinit executable."""

    # Defaults.
    _PROJECT_NAME = 'aiida'
    _DEFAULT_INPUT_FILE = f'{_PROJECT_NAME}.in'
    _DEFAULT_OUTPUT_FILE = f'{_PROJECT_NAME}.out'
    _DEFAULT_GSR_FILE_NAME = f'{_PROJECT_NAME}o_GSR.nc'
    _DEFAULT_HIST_FILE_NAME = f'{_PROJECT_NAME}o_HIST.nc'
    _PSEUDO_SUBFOLDER = './pseudo/'

    _BLOCKED_KEYWORDS = ['ngkpt', 'kptopt', 'acell', 'angdeg', 'rprim', 'brvltt']

    @classmethod
    def define(cls, spec):
        """Define inputs and outputs of the calculation."""
        # yapf: disable
        super(AbinitCalculation, cls).define(spec)

        # Inputs
        spec.input('metadata.options.input_filename',
                   valid_type=str,
                   default=cls._DEFAULT_INPUT_FILE)
        spec.input('metadata.options.output_filename',
                   valid_type=str,
                   default=cls._DEFAULT_OUTPUT_FILE)
        spec.input('metadata.options.output_gsr_filename',
                   valid_type=str,
                   default=cls._DEFAULT_GSR_FILE_NAME)
        spec.input('metadata.options.output_hist_filename',
                   valid_type=str,
                   required=False,
                   default=cls._DEFAULT_HIST_FILE_NAME)
        spec.input('metadata.options.withmpi',
                   valid_type=bool,
                   default=True)

        spec.input('structure',
                   valid_type=orm.StructureData,
                   help='The main input structure.')
        spec.input('kpoints',
                   valid_type=orm.KpointsData,
                   help='The k-point mesh or path')
        spec.input('parameters',
                   valid_type=orm.Dict,
                   help='The ABINIT input parameters.')
        spec.input('settings',
                   valid_type=orm.Dict,
                   required=False,
                   help='Various special settings.')
        spec.input('parent_calc_folder',
                   valid_type=RemoteData,
                   required=False,
                   help='A remote folder used for restarts.')
        spec.input_namespace('pseudos',
                             valid_type=(Psp8Data, JthXmlData),
                             help='The pseudopotentials.',
                             dynamic=True)

        spec.inputs['metadata']['options']['parser_name'].default = 'abinit'
        spec.inputs['metadata']['options']['resources'].default = {
                'num_machines': 1, 'num_mpiprocs_per_machine': 1, }

        # Unrecoverable errors: file missing
        spec.exit_code(100, 'ERROR_MISSING_OUTPUT_FILES',
                       message='Calculation did not produce all expected output files.')
        # Unrecoverable errors: resources like the retrieved folder or its expected contents are missing.
        spec.exit_code(200, 'ERROR_NO_RETRIEVED_FOLDER',
                       message='The retrieved folder data node could not be accessed.')
        spec.exit_code(210, 'ERROR_OUTPUT_MISSING',
                       message='The retrieved folder did not contain the required output file.')
        # Unrecoverable errors: required retrieved files could not be read, parsed or are otherwise incomplete.
        spec.exit_code(301, 'ERROR_OUTPUT_READ',
                       message='The output file could not be read.')
        spec.exit_code(302, 'ERROR_OUTPUT_PARSE',
                       message='The output file could not be parsed.')
        spec.exit_code(303, 'ERROR_OUTPUT_INCOMPLETE',
                       message='The output file was incomplete.')
        spec.exit_code(304, 'ERROR_OUTPUT_CONTAINS_ABORT',
                       message='The output file contains the word "ABORT"')
        spec.exit_code(312, 'ERROR_STRUCTURE_PARSE',
                       message='The output structure could not be parsed.')
        spec.exit_code(350, 'ERROR_UNEXPECTED_PARSER_EXCEPTION',
                       message='The parser raised an unexpected exception.')
        # Significant errors but calculation can be used to restart
        spec.exit_code(400, 'ERROR_OUT_OF_WALLTIME',
                       message='The calculation stopped prematurely because it ran out of walltime.')
        spec.exit_code(500, 'ERROR_GEOMETRY_CONVERGENCE_NOT_REACHED',
                       message='The ionic minimization cycle did not converge for the given thresholds.')

        # Outputs
        spec.output('output_parameters',
                    valid_type=orm.Dict,
                    required=True,
                    help='Various output quantities.')
        spec.output('output_structure',
                    valid_type=orm.StructureData,
                    required=False,
                    help='Final structure of the calculation if present.')
        spec.output('output_trajectory',
                    valid_type=orm.TrajectoryData,
                    required=False,
                    help='Trajectory of various output quantities over the calculation if present.')
        spec.default_output_node = 'output_parameters'

    def _validate_parameters(self):
        """Validate the 'parameters' input `Dict` node.

        Check that no blocked keywords are present.
        """
        keyword_intersection = set(self.inputs.parameters.keys()) & set(self._BLOCKED_KEYWORDS)
        if len(keyword_intersection) > 0:
            raise exceptions.InputValidationError(
                f"Some blocked input keywords were provided: {', '.join(list(keyword_intersection))}"
            )

    def _validate_pseudos(self):
        """Validate the 'pseudos' input namespace.

        Check that each 'kind' in the input `StructureData` has a corresponding pseudopotential.
        """
        kinds = [kind.name for kind in self.inputs.structure.kinds]
        if set(kinds) != set(self.inputs.pseudos.keys()):
            raise exceptions.InputValidationError(
                'Mismatch between the defined pseudos and the list of kinds of the structure.\n'
                'Pseudos: {};\nKinds:{}'.format(', '.join(list(self.inputs.pseudos.keys())), ', '.join(list(kinds)))
            )

    def prepare_for_submission(self, folder):
        """Create the input file(s) from the input nodes.

        :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files needed by
            the calculation.
        :return: `aiida.common.datastructures.CalcInfo` instance
        """
        ### SETUP ###
        # Set up any variables, containers, etc. necessary for the submission preparation
        # FILE LISTS
        local_copy_list = []

        ### INPUT VALIDATION ###
        # Perform input validation
        self._validate_parameters()
        self._validate_pseudos()

        ### PREPARATION ###
        # Prepare inputs for passing to abipy which does the heavy lifting
        # STRUCTURE
        # abipy has its own subclass of pymatgen's `Structure`, so we use that
        pmg_structure = self.inputs.structure.get_pymatgen()
        abi_structure = AbiStructure.as_structure(pmg_structure)
        abi_structure = abi_structure.abi_sanitize(primitive=False)

        # PSEUDOS
        # Set up the pseudopotential subfolder and make sure to copy over the pseudopotential files
        folder.get_subfolder(self._PSEUDO_SUBFOLDER, create=True)
        for kind in self.inputs.structure.get_kind_names():
            psp = self.inputs.pseudos[kind]
            local_copy_list.append((psp.uuid, psp.filename, f'{self._PSEUDO_SUBFOLDER}{psp.filename}'))
        # Pseudopotentials _must_ be listed in the same order as 'znucl' in the input file.
        # So, we need to get 'znucl' as abipy will write it then construct the appropriate 'pseudos' string.
        znucl = structure_to_abivars(abi_structure)['znucl']
        ordered_pseudo_filenames = [self.inputs.pseudos[constants.elements[Z]['symbol']].filename for Z in znucl]
        pseudo_parameters = {
            'pseudos': '"' + ', '.join(ordered_pseudo_filenames) + '"',
            'pp_dirpath': f'"{self._PSEUDO_SUBFOLDER}"'
        }

        # KPOINTS
        kpoints_mesh = self.inputs.kpoints.get_kpoints_mesh()[0]
        # k-points are provided to abipy separately from the main input parameters, so we pop out
        # parameters related to the k-points
        input_parameters = self.inputs.parameters.get_dict()
        shiftk = input_parameters.pop('shiftk', [0.0, 0.0, 0.0])

        ### INPUT CREATION AND WRITING ###
        # Use abipy to write the input file
        # ABINIT INPUT
        input_parameters = {**input_parameters, **pseudo_parameters}

        # We give abipy the HGH_TABLE only so it won't error; we don't actually print these to file.
        abi_input = AbinitInput(
            structure=abi_structure,
            pseudos=HGH_TABLE,
            abi_kwargs=input_parameters
        )
        abi_input.set_kmesh(
            ngkpt=kpoints_mesh,
            shiftk=shiftk
        )

        # WRITE INPUT FILE
        with io.open(folder.get_abs_path(self._DEFAULT_INPUT_FILE), mode='w', encoding='utf-8') as stream:
            stream.write(abi_input.to_string(with_pseudos=False))

        ### CODE ###
        # Set up the code info to pass to `CalcInfo`
        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.cmdline_params = [self.options.input_filename]
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        ### CALC INFO ###
        # Set up the calc info so AiiDA knows what to do with everything
        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.stdin_name = self.options.input_filename
        calcinfo.stdout_name = self.options.output_filename
        calcinfo.retrieve_list = [self.metadata.options.output_filename,
                                  self.metadata.options.output_gsr_filename,
                                  self.metadata.options.output_hist_filename]
        calcinfo.remote_symlink_list = []
        calcinfo.remote_copy_list = []
        calcinfo.local_copy_list = local_copy_list
        if 'parent_calc_folder' in self.inputs:
            comp_uuid = self.inputs.parent_calc_folder.computer.uuid
            remote_path = self.inputs.parent_calc_folder.get_remote_path()
            copy_info = (comp_uuid, remote_path, self._DEFAULT_PARENT_CALC_FLDR_NAME)
            # If running on the same computer - make a symlink.
            if self.inputs.code.computer.uuid == comp_uuid:
                calcinfo.remote_symlink_list.append(copy_info)
            # If not - copy the folder.
            else:
                calcinfo.remote_copy_list.append(copy_info)

        return calcinfo
