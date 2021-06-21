# -*- coding: utf-8 -*-
"""Dictionary utility functions."""
import typing as ty

from aiida.common import exceptions

__all__ = ('lowercase_dict', 'uppercase_dict')


def lowercase_dict(dictionary: dict, dict_name: str = 'dictionary') -> dict:
    """Recursively lowercase the keys of a (nested) dictionary.

    :param dictionary: input dictionary
    :param dict_name: name for the dictionary, used for exceptions
    :returns: input dictionary, but with keys all lowercase
    """
    return _case_transform_dict(dictionary, dict_name, '_lowercase_dict', str.lower)


def uppercase_dict(dictionary: dict, dict_name: str = 'dictionary') -> dict:
    """Recursively upercase the keys of a (nested) dictionary.

    :param dictionary: input dictionary
    :param dict_name: name for the dictionary, used for exceptions
    :returns: input dictionary, but with keys all uppercase
    """
    return _case_transform_dict(dictionary, dict_name, '_uppercase_dict', str.upper)


def _case_transform_dict(dictionary: dict, dict_name: str, func_name: str, transform: ty.Callable) -> dict:
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
