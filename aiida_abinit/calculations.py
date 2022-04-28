# -*- coding: utf-8 -*-
"""CalcJob class for Abinit."""
import io
import os
import typing as ty

from pymatgen.io.abinit.abiobjects import structure_to_abivars
from abipy.abio.inputs import AbinitInput
from abipy.core.structure import Structure as AbiStructure
from abipy.data.hgh_pseudos import HGH_TABLE

from aiida import orm
from aiida.common import constants, datastructures, exceptions
from aiida.engine import CalcJob
from aiida_pseudo.data.pseudo import Psp8Data, JthXmlData

from aiida_abinit.utils import uppercase_dict, seconds_to_timelimit


class AbinitCalculation(CalcJob):
    """AiiDA calculation plugin wrapping the abinit executable."""

    _DEFAULT_PREFIX = 'aiida'
    _DEFAULT_INPUT_EXTENSION = 'in'
    _DEFAULT_OUTPUT_EXTENSION = 'out'
    _PSEUDO_SUBFOLDER = './pseudo/'

    _BLOCKED_KEYWORDS = [
        # Structure-related keywords set automatically from the `StructureData``
        'acell',
        'angdeg',
        'natom',
        'ntypat',
        'rprim',
        'rprimd',
        'brvltt',
        'typat',
        'xcart',
        'xred',
        'znucl',
        'natrd',
        'xyzfile',
        # K-point-related keywords set automatically from the `KpointsData`
        'kpt',
        'ngkpt',
        'nkpath',
        'nkpt',
        'nshiftk',
        'wtk'
    ]

    @classmethod
    def define(cls, spec):
        """Define inputs and outputs of the calculation."""
        # yapf: disable
        super(AbinitCalculation, cls).define(spec)

        spec.input('metadata.options.prefix',
                   valid_type=str,
                   default=cls._DEFAULT_PREFIX)
        spec.input('metadata.options.input_extension',
                   valid_type=str,
                   default=cls._DEFAULT_INPUT_EXTENSION)
        spec.input('metadata.options.output_extension',
                   valid_type=str,
                   default=cls._DEFAULT_OUTPUT_EXTENSION)
        spec.input('metadata.options.withmpi',
                   valid_type=bool,
                   default=True)

        spec.input('structure',
                   valid_type=orm.StructureData,
                   help='The input structure.')
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
                   valid_type=orm.RemoteData,
                   required=False,
                   help='A remote folder used for restarts.')
        spec.input_namespace('pseudos',
                             valid_type=(Psp8Data, JthXmlData),
                             help='The pseudopotentials.',
                             dynamic=True)
        options = spec.inputs['metadata']['options']
        options['parser_name'].default = 'abinit'
        options['resources'].default = {'num_machines': 1, 'num_mpiprocs_per_machine': 1}
        options['input_filename'].default = f'{cls._DEFAULT_PREFIX}.{cls._DEFAULT_INPUT_EXTENSION}'
        options['output_filename'].default = f'{cls._DEFAULT_PREFIX}.{cls._DEFAULT_OUTPUT_EXTENSION}'

        # Unrecoverable errors: file missing
        spec.exit_code(100, 'ERROR_MISSING_OUTPUT_FILES',
                       message='Calculation did not produce all expected output files.')
        spec.exit_code(101, 'ERROR_MISSING_GSR_OUTPUT_FILE',
                       message='Calculation did not produce the expected `[prefix]o_GSR.nc` output file.')
        spec.exit_code(102, 'ERROR_MISSING_HIST_OUTPUT_FILE',
                       message='Calculation did not produce the expected `[prefix]o_HIST.nc` output file.')
        # Unrecoverable errors: resources like the retrieved folder or its expected contents are missing.
        spec.exit_code(200, 'ERROR_NO_RETRIEVED_FOLDER',
                       message='The retrieved folder data node could not be accessed.')
        spec.exit_code(210, 'ERROR_OUTPUT_MISSING',
                       message='The retrieved folder did not contain the `stdout` output file.')
        # Unrecoverable errors: required retrieved files could not be read, parsed or are otherwise incomplete.
        spec.exit_code(301, 'ERROR_OUTPUT_READ',
                       message='The `stdout` output file could not be read.')
        spec.exit_code(302, 'ERROR_OUTPUT_PARSE',
                       message='The `stdout` output file could not be parsed.')
        spec.exit_code(303, 'ERROR_RUN_NOT_COMPLETED',
                       message='The `abipy` `EventsParser` reports that the runw as not completed.')
        spec.exit_code(304, 'ERROR_OUTPUT_CONTAINS_ERRORS',
                       message='The output file contains one or more error messages.')
        spec.exit_code(305, 'ERROR_OUTPUT_CONTAINS_WARNINGS',
                       message='The output file contains one or more warning messages.')
        spec.exit_code(312, 'ERROR_STRUCTURE_PARSE',
                       message='The output structure could not be parsed.')
        # Significant errors but calculation can be used to restart
        spec.exit_code(400, 'ERROR_OUT_OF_WALLTIME',
                       message='The calculation stopped prematurely because it ran out of walltime.')
        spec.exit_code(500, 'ERROR_SCF_CONVERGENCE_NOT_REACHED',
                       message='The SCF minimization cycle did not converge.')
        spec.exit_code(501, 'ERROR_GEOMETRY_CONVERGENCE_NOT_REACHED',
                       message='The ionic minimization cycle did not converge.')

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
        spec.output('output_bands',
                    valid_type=orm.BandsData,
                    required=False,
                    help='Final electronic bands if present.')
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
            pseudos_str = ', '.join(list(self.inputs.pseudos.keys()))
            kinds_str = ', '.join(list(kinds))
            raise exceptions.InputValidationError(
                'Mismatch between the defined pseudos and the list of kinds of the structure.\n'
                f'Pseudos: {pseudos_str};\nKinds:{kinds_str}'
            )

    def _generate_inputdata(self,
                            parameters: orm.Dict,
                            pseudos,
                            structure: orm.StructureData,
                            kpoints: orm.KpointsData) -> ty.Tuple[str, list]:
        """Generate the input file content and list of pseudopotential files to copy.

        :param parameters: input parameters Dict
        :param pseudos: pseudopotential input namespace
        :param structure: input structure
        :param kpoints: input kpoints
        :returns: input file content, pseudopotential copy list
        """
        local_copy_pseudo_list = []

        # `abipy`` has its own subclass of Pymatgen's `Structure`, so we use that
        pmg_structure = structure.get_pymatgen()
        abi_structure = AbiStructure.as_structure(pmg_structure)
        # NOTE: need to refine the `abi_sanitize` parameters
        abi_structure = abi_structure.abi_sanitize(symprec=1e-3, angle_tolerance=5,
            primitive=True, primitive_standard=False)

        for kind in structure.get_kind_names():
            pseudo = pseudos[kind]
            local_copy_pseudo_list.append((pseudo.uuid, pseudo.filename, f'{self._PSEUDO_SUBFOLDER}{pseudo.filename}'))
        # Pseudopotentials _must_ be listed in the same order as 'znucl' in the input file.
        # So, we need to get 'znucl' as abipy will write it then construct the appropriate 'pseudos' string.
        znucl = structure_to_abivars(abi_structure)['znucl']
        ordered_pseudo_filenames = [pseudos[constants.elements[Z]['symbol']].filename for Z in znucl]
        pseudo_parameters = {
            'pseudos': '"' + ', '.join(ordered_pseudo_filenames) + '"',
            'pp_dirpath': f'"{self._PSEUDO_SUBFOLDER}"'
        }

        input_parameters = parameters.get_dict()

        # Use `abipy`` to write the input file
        input_parameters = {**input_parameters, **pseudo_parameters}

        # `AbinitInput` requires a valid pseudo table / list of pseudos, so we give it the `HGH_TABLE`,
        # which should always work. In the end, we do _not_ print these to the input file.
        abi_input = AbinitInput(
            structure=abi_structure,
            pseudos=HGH_TABLE,
            abi_kwargs=input_parameters
        )
        try:
            abi_input.set_kmesh(
                ngkpt=kpoints.get_kpoints_mesh()[0],
                shiftk=input_parameters.pop('shiftk', [0.0, 0.0, 0.0]),
                kptopt=input_parameters.pop('kptopt', 1)
            )
        except AttributeError:
            abi_input['kptopt'] = input_parameters.pop('kptopt', 0)
            abi_input['kptnrm'] = input_parameters.pop('kptnrm', 1)
            abi_input['kpt'] = kpoints.get_kpoints()
            abi_input['nkpt'] = len(abi_input['kpt'])

        return abi_input.to_string(with_pseudos=False), local_copy_pseudo_list

    def _generate_cmdline_params(self, settings: dict) -> ty.List[str]:
        # The input file has to be the first parameter
        cmdline_params = [self.metadata.options.input_filename]

        # If a max wallclock is set in the `options`, we also set the `--timelimit` param
        if 'max_wallclock_seconds' in self.metadata.options:
            max_wallclock_seconds = self.metadata.options.max_wallclock_seconds
            cmdline_params.extend(['--timelimit', seconds_to_timelimit(max_wallclock_seconds)])

        # If a number of OMP threads is set in the options, we set the `--omp-num-threads` param
        if 'num_omp_threads' in self.metadata.options.resources:
            omp_num_threads = self.metadata.options.resources['omp_num_threads']
            cmdline_params.extend(['--omp-num-threads', f'{omp_num_threads:d}'])

        # Enable verbose mode if requested in the settings
        if settings.pop('VERBOSE', False):
            cmdline_params.append('--verbose')

        # Enable a dry run if requested in the settings
        # NOTE: don't pop here, we need to know about dry runs when generating the retrieve list
        if settings.get('DRY_RUN', False):
            cmdline_params.append('--dry-run')

        return cmdline_params

    def _generate_retrieve_list(self, parameters: orm.Dict, settings: dict) -> list:
        """Generate the list of files to retrieve based on the type of calculation requested in the input parameters.

        :param parameters: input parameters
        :returns: list of files to retreive
        """
        parameters = parameters.get_dict()
        prefix = self.metadata.options.prefix

        # Start with the files that should always be retrieved: stdout, .abo, then add manually provided files
        retrieve_list = [f'{prefix}.{postfix}' for postfix in [self._DEFAULT_OUTPUT_EXTENSION]]
        retrieve_list += settings.pop('ADDITIONAL_RETRIEVE_LIST', [])

        # NOTE: pop here, we don't need this setting anymore
        if not settings.pop('DRY_RUN', False):
            # In all cases except for dry runs: o_GSR.nc
            retrieve_list += [f'{prefix}{postfix}' for postfix in ['o_GSR.nc']]
            # When moving ions: o_HIST.nc
            if parameters.get('ionmov', 0) > 0:
                retrieve_list += [f'{prefix}{postfix}' for postfix in ['o_HIST.nc']]

        # There may be duplicates from the `ADDITIONAL_RETRIEVE_LIST` setting, so clean up using set()
        return list(set(retrieve_list))

    def prepare_for_submission(self, folder):
        """Create the input file(s) from the input nodes.

        :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files needed by
            the calculation.
        :return: `aiida.common.datastructures.CalcInfo` instance
        """
        # Process the `settings`` so that capitalization isn't an issue
        settings = uppercase_dict(self.inputs.settings.get_dict()) if 'settings' in self.inputs else {}

        # Validate the input parameters and pseudopotentials
        self._validate_parameters()
        self._validate_pseudos()

        # Create lists which specify files to copy and symlink
        local_copy_list = []
        remote_copy_list = []
        remote_symlink_list = []

        # Create the subfolder which will contain the pseudopotential files
        folder.get_subfolder(self._PSEUDO_SUBFOLDER, create=True)

        # Generate the input file content and list of pseudopotential files to copy
        arguments = [
            self.inputs.parameters,
            self.inputs.pseudos,
            self.inputs.structure,
            self.inputs.kpoints
        ]
        input_filecontent, local_copy_pseudo_list = self._generate_inputdata(*arguments)

        # Merge the pseudopotential copy list with the overall copy list then write the input file
        local_copy_list += local_copy_pseudo_list
        with io.open(folder.get_abs_path(self.metadata.options.input_filename), mode='w', encoding='utf-8') as stream:
            stream.write(input_filecontent)

        # List the files to copy or symlink in the case of a restart
        if 'parent_folder' in self.inputs:
            # Symlink by default if on the same computer, otherwise copy by default
            same_computer = self.inputs.code.computer.uuid == self.inputs.parent_folder.computer.uuid
            if settings.pop('PARENT_FOLDER_SYMLINK', same_computer):
                remote_symlink_list.append((
                    self.inputs.parent_folder.computer.uuid,
                    os.path.join(self.inputs.parent_folder.get_remote_path(), '*'),
                    './')
                )
            else:
                remote_copy_list.append((
                    self.inputs.parent_folder.computer.uuid,
                    os.path.join(self.inputs.parent_folder.get_remote_path(), '*'),
                    './')
                )

        # Generate the commandline parameters
        cmdline_params = self._generate_cmdline_params(settings)

        # Generate list of files to retrieve from wherever the calculation is run
        retrieve_list = self._generate_retrieve_list(self.inputs.parameters, settings)

        # Set up the `CodeInfo` to pass to `CalcInfo`
        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.cmdline_params = cmdline_params
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        # Set up the `CalcInfo` so AiiDA knows what to do with everything
        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.stdin_name = self.metadata.options.input_filename
        calcinfo.stdout_name = self.metadata.options.output_filename
        calcinfo.retrieve_list = retrieve_list
        calcinfo.remote_symlink_list = remote_symlink_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.local_copy_list = local_copy_list

        return calcinfo
