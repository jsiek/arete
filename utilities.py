from dataclasses import dataclass
from lark.tree import Meta

def env_init(env, var, val):
    env[var] = [val]

def env_get(env, var):
    return env[var][0]

def env_set(env, var, val):
    env[var][0] = val

@dataclass
class AST:
    location: Meta

@dataclass
class Exp(AST):
    pass

@dataclass
class Stmt(AST):
    pass

@dataclass
class Decl(AST):
    pass


def declare_locals(vars, env):
    for var in vars:
        env_init(env, var, None)

def allocate_locals(var_priv_vals, env, location):
    for var, priv, val in var_priv_vals:
        if priv == 'write' and isinstance(val, Pointer) \
           and val.permission != Fraction(1,1):
            error(location, 'need writable pointer, not ' + str(val))
        elif priv == 'read' and isinstance(val, Pointer) \
                  and (not val.address is None) \
                  and val.permission == Fraction(0,1):
            error(location, 'need readable pointer, not ' + str(val))
        env_set(env, var, val)

def deallocate_locals(vars, env, mem, location):
    for var in vars:
        v = env_get(env, var)
        if not v is None:
            v.kill(mem, location)

def kill_temp(val, mem, location):
    if not (val is None):
        if val.temporary:
            val.kill(mem, location)
        
