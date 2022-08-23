from ast_types import *
from abstract_syntax import *

from utilities import *

def type_check_program(decls):
    env = {}
    for d in decls:
      d.declare_type(env, env)
    for d in decls:
      d.type_check(env)
        
    
