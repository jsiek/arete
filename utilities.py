from dataclasses import dataclass
from lark.tree import Meta
from values import *

def env_init(env, var, val):
    env[var] = [val]

def env_get(env, var):
    return env[var][0]

def env_set(env, var, val):
    env[var][0] = val

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
        
compare_ops = { 'less': lambda x, y: x < y,
                'less_equal': lambda x, y: x <= y,
                'greater': lambda x, y: x > y,
                'greater_equal': lambda x, y: x >= y}

def eval_prim(op, vals, mem, location):
    match op:
      case 'equal':
        left, right = vals
        retval = Boolean(True, left.equals(right))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case 'not_equal':
        left, right = vals
        retval = Boolean(True, not left.equals(right))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case 'add':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, left + right)
      case 'sub':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, left - right)
      case 'mul':
        left = to_number(vals[0], location)
        right = to_number(vals[0], location)
        return Number(True, left * right)
      case 'div':
        left = to_number(vals[0], location)
        right = to_number(vals[1], location)
        return Number(True, Fraction(left, right))
      case 'neg':
        val = to_number(vals[0], location)
        return Number(True, - val)
      case 'and':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(True, left and right)
      case 'or':
        left = to_boolean(vals[0], location)
        right = to_boolean(vals[1], location)
        return Boolean(True, left or right)
      case 'not':
        val = to_boolean(vals[0], location)
        return Boolean(True, not val)
      case 'null':
        # fraction is 1/1 because null has all of nothing! -Jeremy
        return Pointer(True, None, Fraction(1,1), None)
      case 'is_null':
        ptr = vals[0]
        match ptr:
          case Pointer(tmp, addr, priv):
            retval = Boolean(True, addr is None)
          case _:
            retval = Boolean(True, False)
        kill_temp(ptr, mem, location)
        return retval
      case 'split':
        ptr = vals[0]
        ptr1 = ptr.duplicate(Fraction(1, 2))
        ptr2 = ptr.duplicate(Fraction(1, 1))
        return allocate([ptr1, ptr2], mem)
      case 'join':
        ptr1, ptr2 = vals
        if trace:
            print('join ' + str(ptr1) + ' with ' + str(ptr2))
        ptr = ptr1.duplicate(1)
        ptr.transfer(1, ptr2, location)
        if trace:
            print('result of join: ' + str(ptr))
        return ptr
      case cmp if cmp in compare_ops.keys():
        left, right = vals
        l = to_number(left, location)
        r = to_number(right, location)
        retval = Boolean(True, compare_ops[cmp](l, r))
        kill_temp(left, mem, location)
        kill_temp(right, mem, location)
        return retval
      case _:
        error(location, 'unknown primitive operator ' + op)
    
