from typing import Optional, Any, List, Dict
from aiida.orm import Group, StructureData, Str
from aiida_pseudo.data.pseudo import Psp8Data
from aiida.common.exceptions import NotExistent

def validate_and_prepare_pseudos_inputs(structure: StructureData, pseudos: Optional[Dict[str, Psp8Data]]=None, pseudo_family=Str) -> Dict[str, Psp8Data]:  # pylint: disable=invalid-name
    """Validate the given pseudos mapping or pseudo potential family with respect to the given structure.

    Use the explicitly passed pseudos dictionary or use the pseudo_family in combination with the structure to obtain
    that dictionary.

    The pseudos dictionary should now be a dictionary of UPF nodes with the kind as linkname
    As such, if there are multiple kinds with the same element, there will be duplicate UPF nodes
    but multiple links for the same input node are not allowed. Moreover, to couple the UPF nodes
    to the Calculation instance, we have to go through the use_pseudo method, which takes the kind
    name as an additional parameter. When creating a Calculation through a Process instance, one
    cannot call the use methods directly but rather should pass them as keyword arguments. However,
    we can pass the additional parameters by using them as the keys of a dictionary

    :param structure: StructureData node
    :param pseudos: a dictionary where keys are the kind names and value are UpfData nodes
    :param pseudo_family: pseudopotential family name to use, should be Str node
    :raises: ValueError if neither pseudos or pseudo_family is specified or if no UpfData is found for
        every element in the structure
    :returns: a dictionary of UpfData nodes where the key is the kind name
    """

    if pseudos and pseudo_family:
        raise ValueError('you cannot specify both "pseudos" and "pseudo_family"')
    elif pseudos is None and pseudo_family is None:
        raise ValueError('neither an explicit pseudos dictionary nor a pseudo_family was specified')
    elif pseudo_family:
        try:
            family = Group.objects.get(label=pseudo_family.value)
        except NotExistent:
            raise NotExistent(f'No Psp8Family {pseudo_family.value} found')
        pseudos = family.get_pseudos(structure=structure)
    elif isinstance(pseudos, (str, Str)):
        raise TypeError('you passed "pseudos" as a string - maybe you wanted to pass it as "pseudo_family" instead?')

    for kind in structure.get_kind_names():
        if kind not in pseudos:
            raise ValueError(f'no pseudo available for element {kind}')
        elif not isinstance(pseudos[kind], Psp8Data):
            raise ValueError(f'pseudo for element {kind} is not of type Psp8Data')

    return pseudos