"""
Calculations provided by aiida_abinit.

Register calculations via the "aiida.calculations" entry point in setup.json.
"""
import io
import os

from aiida import orm
from aiida.common import datastructures, exceptions
from aiida.engine import CalcJob
from aiida.orm import RemoteData
from aiida_pseudo.data.pseudo import Psp8Data, JthXmlData

from . import utils

class AbinitCalculation(CalcJob):
    """`CalcJob` implementation for the Abinit"""

    _PSEUDO_SUBFOLDER = './pseudo/'
    _PSEUDO_EXTENSION = {
        Psp8Data: '.psp8',
        JthXmlData: '.xml'
    }
    _OUTPUT_SUBFOLDER = './out/'
    _PREFIX = 'aiida'
    _DEFAULT_INPUT_FILE = 'aiida.in'
    _DEFAULT_OUTPUT_FILE = 'aiida.out'
    _DEFAULT_GSR_FILE = _PREFIX + 'o_GSR.nc'
    _DEFAULT_HIST_FILE = _PREFIX + 'o_HIST.nc'
    _DEFAULT_OUT_FILE = _PREFIX + 'o_OUT.nc'
    _DEFAULT_EIG_FILE = _PREFIX + 'o_EIG.nc'
    _DEFAULT_WFK_FILE = _PREFIX + 'o_WFK.nc'
    _DEFAULT_DDB_FILE = _PREFIX + 'o_DDB'
    _DEFAULT_SCF_DEN_FILE = _PREFIX + 'o_DEN'
    _DEFAULT_RELAX_DEN_FILE = _PREFIX + 'o_TIM1_DEN'

    # Additional files that should always be retrieved for the specific plugin
    _internal_retrieve_list = []

    # Blocked keywords
    _blocked_keywords = {
        # Structure
        'acell',
        'rprim',
        'rprimd',
        'angdeg',
        'xred',
        'xcart',
        'xangst',
        'znucl',
        'typat',
        'ntypat',
        'natom',
        # k-points
        'ngkpt',
        'shiftk',
        'nshiftk',
        # Pseudopotentials
        'pseudos',
        'ppdirpath'
    }

    # In restarts, will not copy but use symlinks
    _default_symlink_usage = True

    # In restarts, it will copy from the parent the following
    _restart_copy_from = os.path.join(_OUTPUT_SUBFOLDER, '*')

    # In restarts, it will copy the previous folder in the following one
    _restart_copy_to = _OUTPUT_SUBFOLDER

    @classmethod
    def define(cls, spec):
        """Define inputs and outputs of the calculation."""
        # yapf: disable
        super(AbinitCalculation, cls).define(spec)
        spec.inputs['metadata']['options']['resources'].default = lambda: {'num_machines': 1}
        # spec.inputs['metadata']['options']['parser_name'].default = 'abinit'
        
        spec.input('metadata.options.parser_name', valid_type=str, default='abinit')
        spec.input('metadata.options.input_filename', valid_type=str, default=cls._DEFAULT_INPUT_FILE)
        spec.input('metadata.options.output_filename', valid_type=str, default=cls._DEFAULT_OUTPUT_FILE)
        spec.input('metadata.options.output_gsr', valid_type=str, default=cls._DEFAULT_GSR_FILE)
        spec.input('metadata.options.output_hist', valid_type=str, default=cls._DEFAULT_HIST_FILE)
        spec.input('metadata.options.output_out', valid_type=str, default=cls._DEFAULT_OUT_FILE)
        spec.input('metadata.options.withmpi', valid_type=bool, default=True)
        spec.input('structure', valid_type=orm.StructureData,
            help='The input structure.')
        spec.input('kpoints', valid_type=orm.KpointsData, help='The k-point mesh or k-point path.')
        spec.input('parameters', valid_type=orm.Dict,
            help='The input parameters that are to be used to construct the input file.')
        spec.input('settings', valid_type=orm.Dict, required=False,
            help='Optional parameters to affect the way the calculation job and the parsing are performed.')
        spec.input('parent_folder', valid_type=RemoteData, required=False,
            help='An optional working directory of a previously completed calculation to restart from.')
        spec.input_namespace('pseudos', valid_type=(Psp8Data, JthXmlData), dynamic=True,
            help='A mapping of `Psp8Data` or `JthXmlData` nodes onto the kind name to which they should apply.')

        # Unrecoverable errors: file missing
        spec.exit_code(100, 'ERROR_MISSING_OUTPUT_FILES', message='Calculation did not produce all expected output files.')
        # Unrecoverable errors: resources like the retrieved folder or its expected contents are missing.
        spec.exit_code(200, 'ERROR_NO_RETRIEVED_FOLDER', message='The retrieved folder data node could not be accessed.')
        spec.exit_code(210, 'ERROR_OUTPUT_MISSING', message='The retrieved folder did not contain the required output file.')
        # Unrecoverable errors: required retrieved files could not be read, parsed or are otherwise incomplete.
        spec.exit_code(301, 'ERROR_OUTPUT_READ', message='The output file could not be read.')
        spec.exit_code(302, 'ERROR_OUTPUT_PARSE', message='The output file could not be parsed.')
        spec.exit_code(303, 'ERROR_OUTPUT_INCOMPLETE', message='The output file was incomplete.')
        spec.exit_code(304, 'ERROR_OUTPUT_CONTAINS_ABORT', message='The output file contains the word "ABORT"')
        spec.exit_code(312, 'ERROR_STRUCTURE_PARSE', message='The output structure could not be parsed.')
        spec.exit_code(350, 'ERROR_UNEXPECTED_PARSER_EXCEPTION', message='The parser raised an unexpected exception.')
        # Significant errors but calculation can be used to restart
        spec.exit_code(400, 'ERROR_OUT_OF_WALLTIME', message='The calculation stopped prematurely because it ran out of walltime.')
        spec.exit_code(500, 'ERROR_GEOMETRY_CONVERGENCE_NOT_REACHED',
                       message='The ionic minimization cycle did not converge for the given thresholds.')

        # Outputs
        spec.output('output_parameters', valid_type=orm.Dict,
            help='The `output_parameters` output node of the successful calculation.')
        spec.output('output_structure', valid_type=orm.StructureData, required=False,
            help='The `output_structure` output node of the successful calculation if present.')
        spec.output('output_trajectory', valid_type=orm.ArrayData, required=False,
            help='The `output_trajectory` output notde of the successful calculation if present.')
        spec.default_output_node = 'output_parameters'

    def prepare_for_submission(self, folder):
        """
        Create input files.

        :param folder: an `aiida.common.folders.Folder` where the plugin should temporarily place all files needed by
            the calculation.
        :return: `aiida.common.datastructures.CalcInfo` instance
        """
        if 'settings' in self.inputs:
            settings = _uppercase_dict(self.inputs.settings.get_dict(), dict_name='settings')
        else:
            settings = {}

        ####    VALIDATION CHECKS    ###########################################
        # Check that a pseudo potential was specified for each kind present in the `StructureData`
        kinds = [kind.name for kind in self.inputs.structure.kinds]
        if set(kinds) != set(self.inputs.pseudos.keys()):
            msg = 'Mismatch between the defined pseudos and the list of kinds of the structure.\n' \
                'Pseudos: {};\nKinds: {}'.format(', '.join(list(self.inputs.pseudos.keys())), ', '.join(list(kinds)))
            raise exceptions.InputValidationError(msg)

        # Check that no blocked keywords have ben provided in the input parameters
        provided_blocked_keywords = []
        for keyword in self._blocked_keywords:
            if keyword in self.inputs.parameters.get_dict():
                provided_blocked_keywords.append(keyword)
        if provided_blocked_keywords:
            msg = f'Input keyword(s) {provided_blocked_keywords} were provided in `input_parameters`, but they must ' \
                'be set automatically by the input generator.'
            raise exceptions.InputValidationError(msg)

        ####    FOLDERS AND FILES    ###########################################
        remote_symlink_list = []
        remote_copy_list = []
        local_copy_list = []

        # Create the subfolder that will contain the pseudopotentials
        folder.get_subfolder(self._PSEUDO_SUBFOLDER, create=True)

        input_filecontent, local_copy_pseudo_list = self._generate_input_data()
        local_copy_list += local_copy_pseudo_list

        with io.open(folder.get_abs_path(self._DEFAULT_INPUT_FILE), mode='w', encoding='utf-8') as f:
            f.write(input_filecontent)

        # Operations for restarting
        symlink = settings.pop('PARENT_FOLDER_SYMLINK', self._default_symlink_usage)  # a boolean
        if symlink:
            if 'parent_folder' in self.inputs:
                # I put the symlink to the old parent ./out folder
                remote_symlink_list.append((
                    self.inputs.parent_folder.computer.uuid,
                    os.path.join(self.inputs.parent_folder.get_remote_path(),
                                 self._restart_copy_from), self._restart_copy_to
                ))
        else:
            # copy remote output dir, if specified
            if 'parent_folder' in self.inputs:
                remote_copy_list.append((
                    self.inputs.parent_folder.computer.uuid,
                    os.path.join(self.inputs.parent_folder.get_remote_path(),
                                 self._restart_copy_from), self._restart_copy_to
                ))

        ####    CODE    ########################################################
        codeinfo = datastructures.CodeInfo()
        codeinfo.code_uuid = self.inputs.code.uuid
        codeinfo.cmdline_params = [self.options.input_filename]
        codeinfo.stdout_name = self.metadata.options.output_filename
        codeinfo.withmpi = self.inputs.metadata.options.withmpi

        ####    CALC INFO    ###################################################
        calcinfo = datastructures.CalcInfo()
        calcinfo.codes_info = [codeinfo]
        calcinfo.stdin_name = self.metadata.options.input_filename
        calcinfo.stdout_name = self.metadata.options.output_filename
        calcinfo.retrieve_list = []
        calcinfo.retrieve_list.append(self.metadata.options.output_filename)
        calcinfo.retrieve_list.extend([self._DEFAULT_OUT_FILE, self._DEFAULT_GSR_FILE])
        calcinfo.retrieve_list.extend(settings.pop('ADDITIONAL_RETRIEVE_LIST', []))
        calcinfo.remote_symlink_list = remote_symlink_list
        calcinfo.remote_copy_list = remote_copy_list
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

    def _generate_input_data(self):
        input_parameters = self.inputs.parameters.get_dict()
        structure = self.inputs.structure
        kinds = set([kind.name for kind in self.inputs.structure.kinds])
        kpoints_mesh = self.inputs.kpoints.get_kpoints_mesh()[0]
        pseudos = self.inputs.pseudos

        ####    STRUCTURE    ###################################################
        # Create structure-related abinit parameters
        structure_parameters, types_of_kind = utils.structure_data_to_abivars(structure)

        ####    PSEUDOPOTENTIALS    ############################################
        # Create the copy list for pseudopotential files and mapping to kinds
        local_copy_pseudo_list = []
        kind_pseudo_file_mapping = {}
        for kind in kinds:
            pseudo = pseudos[kind.name]
            pseudo_file_name = kind + self._PSEUDO_EXTENSION[type(pseudo)]
            local_copy_pseudo_list.append(
                (pseudo.uuid, pseudo.filename, self._PSEUDO_SUBFOLDER + pseudo_file_name)
            )
            kind_pseudo_file_mapping[kind.name] = pseudo_file_name
        pseudo_files = [kind_pseudo_file_mapping[kind.name] for kind in types_of_kind]

        # Create the abinit input parameters for the pseudos
        pseudos_string = ', '.join(pseudo_files)
        pseudo_parameters = {
            'pseudos': f'"{pseudos_string}"',
            'pp_dirpath': f'"{self._PSEUDO_SUBFOLDER}"'
        }

        ####    K-POINTS    ####################################################
        kpoint_parameters = {
            'ngkpt': kpoints_mesh,
            'kptopt': input_parameters.get('kptopt', 1),
            'skiftk': [[0.0, 0.0, 0.0]],
            'nshiftk': 1,
        }

        ####    FILE CONTENTS    ###############################################
        # Combine parameters
        abinit_parameters = {**input_parameters, **structure_parameters, **pseudo_parameters, **kpoint_parameters}

        # Create input file contents
        input_filecontent = utils.abivars_to_string(abinit_parameters)

        return input_filecontent, local_copy_pseudo_list


def _lowercase_dict(dictionary, dict_name):
    return _case_transform_dict(dictionary, dict_name, '_lowercase_dict', str.lower)


def _uppercase_dict(dictionary, dict_name):
    return _case_transform_dict(dictionary, dict_name, '_uppercase_dict', str.upper)


def _case_transform_dict(dictionary, dict_name, func_name, transform):
    from collections import Counter

    if not isinstance(dictionary, dict):
        raise TypeError(f'{func_name} accepts only dictionaries as argument, got {type(dictionary)}')
    new_dict = dict((transform(str(k)), v) for k, v in dictionary.items())
    if len(new_dict) != len(dictionary):
        num_items = Counter(transform(str(k)) for k in dictionary.keys())
        double_keys = ','.join([k for k, v in num_items if v > 1])
        raise exceptions.InputValidationError(
            "Inside the dictionary '{}' there are the following keys that "
            'are repeated more than once when compared case-insensitively: {}.'
            'This is not allowed.'.format(dict_name, double_keys)
        )
    return new_dict


def _pop_parser_options(calc_job_instance, settings_dict, ignore_errors=True):
    """Delete any parser options from the settings dictionary.

    The parser options key is found via the get_parser_settings_key() method of the parser class specified as a metadata
    input.
    """
    from aiida.plugins import ParserFactory
    from aiida.common import EntryPointError
    try:
        parser_name = calc_job_instance.inputs['metadata']['options']['parser_name']
        parser_class = ParserFactory(parser_name)
        parser_opts_key = parser_class.get_parser_settings_key().upper()
        return settings_dict.pop(parser_opts_key, None)
    except (KeyError, EntryPointError, AttributeError) as exc:
        # KeyError: input 'metadata.options.parser_name' is not defined;
        # EntryPointError: there was an error loading the parser class form its entry point
        #   (this will probably cause errors elsewhere too);
        # AttributeError: the parser class doesn't have a method get_parser_settings_key().
        if ignore_errors:
            pass
        else:
            raise exc