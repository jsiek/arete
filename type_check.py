from ast_types import *
from abstract_syntax import *

from utilities import *

def type_check_program(decls):
    env = {}
    new_decls = []
    for d in decls:
      env |= d.declare_type(env)
    for d in decls:
      new_decls += d.type_check(env)
    return new_decls
        
    
