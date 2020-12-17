import tempfile
import typing as typ

import numpy as np
from pymatgen.io.abinit.pseudos import Pseudo

from aiida import orm
from aiida.engine import calcfunction
from aiida_pseudo.data.pseudo import Psp8Data, JthXmlData


def array_to_input_string(array: typ.Union[list, tuple, np.ndarray]) -> str:
    """Convert an input array to a string formatted for Abinit"""

    nested = False
    input_string = ''
    for value in array:
        if isinstance(value, (list, tuple, np.ndarray)):
            nested = True
            input_string += array_to_input_string(value)
        else:
            if isinstance(value, float):
                input_string += f'    {value:0.10f}'
            else:
                input_string += f'    {value}'

    if not nested:
        input_string = '\n' + input_string

    return input_string


def aiida_psp8_to_abipy_pseudo(aiida_pseudo: Psp8Data,
                               pseudo_dir: str = '') -> Pseudo:
    """Convert an aiida-pseudo Psp8Data into a pymatgen/abipy Pseudo"""
    with tempfile.NamedTemporaryFile('w', encoding='utf-8') as f:
        f.write(aiida_pseudo.get_content())
        abinit_pseudo = Pseudo.from_file(f.name)
        f.close()
    abinit_pseudo.path = pseudo_dir + aiida_pseudo.attributes['filename']
    return abinit_pseudo


def validate_and_prepare_pseudos_inputs(
    structure: orm.StructureData,
    pseudos: typ.Optional[typ.Dict[str, typ.Union[Psp8Data, JthXmlData]]] = None
) -> typ.Dict[str, Psp8Data]:  # pylint: disable=invalid-name
    """Validate the given pseudos mapping with respect to the given structure.

    The pseudos dictionary should now be a dictionary of Psp8Data nodes with the kind as linkname
    As such, if there are multiple kinds with the same element, there will be duplicate Psp8Data nodes
    but multiple links for the same input node are not allowed. Moreover, to couple the Psp8Data nodes
    to the Calculation instance, we have to go through the use_pseudo method, which takes the kind
    name as an additional parameter. When creating a Calculation through a Process instance, one
    cannot call the use methods directly but rather should pass them as keyword arguments. However,
    we can pass the additional parameters by using them as the keys of a dictionary

    :param structure: StructureData node
    :param pseudos: a dictionary where keys are the kind names and value are Psp8 nodes
    :raises: ValueError if no Psp8 is found for every element in the structure
    :returns: a dictionary of Psp8 nodes where the key is the kind name
    """

    if isinstance(pseudos, (str, orm.Str)):
        raise TypeError(
            'you passed "pseudos" as a string - maybe you wanted to pass it as "pseudo_family" instead?'
        )

    for kind in structure.get_kind_names():
        if kind not in pseudos:
            raise ValueError(f'no pseudo available for element {kind}')
        elif not isinstance(pseudos[kind], (Psp8Data, JthXmlData)):
            raise ValueError(
                f'pseudo for element {kind} is not of type Psp8Data or JthXmlData')

    return pseudos


@calcfunction
def create_kpoints_from_distance(structure: orm.StructureData,
                                 distance: orm.Float) -> orm.KpointsData:
    """Generate a uniformly spaced kpoint mesh for a given structure.

    The spacing between kpoints in reciprocal space is guaranteed to be at least the defined distance.

    :param structure: the StructureData to which the mesh should apply
    :param distance: a Float with the desired distance between kpoints in reciprocal space
    :returns: a KpointsData with the generated mesh
    """
    epsilon = 1E-5

    kpoints = orm.KpointsData()
    kpoints.set_cell_from_structure(structure)
    kpoints.set_kpoints_mesh_from_density(distance.value)

    lengths_vector = [np.linalg.norm(vector) for vector in structure.cell]
    lengths_kpoint = kpoints.get_kpoints_mesh()[0]

    is_symmetric_cell = all(
        abs(length - lengths_vector[0]) < epsilon for length in lengths_vector)
    is_symmetric_mesh = all(length == lengths_kpoint[0]
                            for length in lengths_kpoint)

    # If the vectors of the cell all have the same length, the kpoint mesh should be isotropic as well
    if is_symmetric_cell and not is_symmetric_mesh:
        nkpoints = max(lengths_kpoint)
        kpoints.set_kpoints_mesh([nkpoints, nkpoints, nkpoints])

    return kpoints
