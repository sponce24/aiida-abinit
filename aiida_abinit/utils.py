import typing as typ

import numpy as np
from abipy.abio.abivars_db import get_abinit_variables
from abipy.abio.variable import InputVariable
from pymatgen import Element, Lattice
from pymatgen.core import units

from aiida import orm
from aiida.engine import calcfunction
from aiida_pseudo.data.pseudo import Psp8Data, JthXmlData


def structure_data_to_abivars(structure_data):
    """Convert a structure data to a dictionary of Abinit inputs."""
    natom = len(structure_data.sites)
    ntypat = len(structure_data.kinds)

    sites = structure_data.sites

    # Get list of unique kinds in order of appearance in sites
    types_of_kind = []
    for site in sites:
        if site.kind_name not in types_of_kind:
            site_kind = structure_data.get_kind(site.kind_name)
            types_of_kind.append(site_kind)

    # Get list of the nuclear charge of the unique kinds in order of appearance in sites
    znucl_type = [Element[kind.symbol].Z for kind in types_of_kind]
    # Map each site to a typat index using the site's kind
    # Also generate the list of pseudos
    typat = np.zeros(natom, np.int)
    for site_idx, site in enumerate(sites):
        typat[site_idx] = types_of_kind.index(structure_data.get_kind(site.kind_name))
    
    rprim = np.array(structure_data.cell) * units.ang_to_bohr
    xred = np.reshape([site.position for site in sites], (-1, 3))

    # Atomic information
    abivars = {
        'natom': natom,
        'ntypat': ntypat,
        'typat': typat,
        'znucl': znucl_type,
        'xred': xred
    }

    # Decide between (rprim, acell) and (angdeg, acell) for specifying the lattice
    if Lattice(structure_data.cell).is_hexagonal():
        abivars['geomode'] = 'angdeg'
        abivars['angdeg'] = np.array(structure_data.cell_angles)
        abivars['acell'] = rprim
    else:
        abivars['geomode'] = 'rprim'
        abivars['rprim'] = rprim
        abivars['acell'] = 3 * [1.0]

    return abivars, types_of_kind


def abivars_to_string(abivars, exclude=[]):
    """Convert a dictionary of Abinit inputs to a string sorted by sections."""
    width = 46
    lines = []

    var_database = get_abinit_variables()
    keys = [k for (k, v) in abivars.items() if k not in exclude and v is not None]
    sections_to_names = var_database.group_by_varset(keys)

    for section, names in sections_to_names.items():
        lines.append(width * '#')
        lines.append('####' + f'SECTION: {section}'.center(width - 1))
        lines.append(width * '#')
        for name in names:
            value = abivars[name]
            lines.append(str(InputVariable(name, value)))

    return '\n'.join(lines)


def validate_and_prepare_pseudos_inputs(
    structure: orm.StructureData,
    pseudos: typ.Optional[typ.Dict[str, typ.Union[Psp8Data, JthXmlData]]] = None
) -> typ.Dict[str, Psp8Data]:  # pylint: disable=invalid-name
    """Validate the given pseudos mapping with respect to the given structure.

    The pseudos dictionary should now be a dictionary of Psp8Data/JthXmlData nodes with the kind as linkname
    As such, if there are multiple kinds with the same element, there will be duplicate Psp8Data/JthXmlData nodes
    but multiple links for the same input node are not allowed. Moreover, to couple the Psp8Data/JthXmlData nodes
    to the Calculation instance, we have to go through the use_pseudo method, which takes the kind
    name as an additional parameter. When creating a Calculation through a Process instance, one
    cannot call the use methods directly but rather should pass them as keyword arguments. However,
    we can pass the additional parameters by using them as the keys of a dictionary

    :param structure: StructureData node
    :param pseudos: a dictionary where keys are the kind names and value are Psp8 nodes
    :raises: ValueError if no Psp8 is found for every element in the structure
    :returns: a dictionary of Psp8 nodes where the key is the kind name
    """

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
