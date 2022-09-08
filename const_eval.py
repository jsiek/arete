# Propagate constants.
# TODO: split these functions into AST methods.
# TODO: more partial evaluation.



from abstract_syntax import *
from functions import *
from variables_and_binding import *
from variants import *
from tuples_and_arrays import *
from records import *
from modules import *
from pointers import *
from futures import *
from interfaces_and_impls import *
from dataclasses import dataclass
from parser import parse, set_filename
from typing import List, Set, Dict, Tuple, Any
from fractions import Fraction
import numbers
import sys
import copy
from utilities import *
from ast_types import *

def const_eval_decls(decls, env):
    new_decls = []
    for d in decls:
        new_decls += d.const_eval(env)
    return new_decls
