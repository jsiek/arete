from abstract_syntax import *
from dataclasses import dataclass
from parser import parse
import sys

@dataclass
class Integer:
    value: int

@dataclass
class Pointer:
    address: int
    privilege: str  # none, read, write
    __match_args__ = ("address", "privilege")

# Increment the reference count of an address
def increment(addr, mem):
    (v, count) = mem[addr]
    mem[addr] = (v, count + 1)

# Decrement the reference count of an address
def decrement(addr, mem):
    (v, count) = mem[addr]
    new_count = count - 1
    if new_count == 0:
        mem[addr] = (None, 0)
    else:
        mem[addr] = (v, new_count)
    
def share(ptr, mem):
    match ptr:
      case Pointer(addr, priv):
        if priv == 'none':
            raise Exception('cannot share if have no privileges')
        increment(addr, mem)
        ptr.privilege = 'read'
        return Pointer(addr, 'read')
      case _:
        raise Exception('expected pointer, not ' + repr(ptr))

def release(ptr, mem):
    match ptr:
      case Pointer(addr, priv):
        if priv != 'write':
            raise Exception('cannot release if do not have write privilege')
        ptr.addr = -1
        ptr.privilege = 'none'
        return Pointer(addr, 'write')
      case _:
        raise Exception('expected pointer, not ' + repr(ptr))

def kill(val, mem):
    match val:
      case Integer(value):
        pass
      case Pointer(addr, priv):
        if priv != 'write':
            raise Exception('cannot kill if do not have write privilege')
        decrement(addr, mem)
        val.addr = -1
        val.privilege = 'none'

def bind(val, mem):
  match val:
    case Integer(value):
      return Integer(value)
    case Pointer(address, priv):
      if mem[address][1] > 0 and priv != 'read':
        raise Exception('in bind, cannot steal from owner')
      increment(address, mem)
      return val
    case _:
      raise Exception('in bind, unhandled value ' + repr(val))
        
def copy(val, mem):
    match val:
      case Integer(value):
        return Integer(value)
      case Pointer(address, priv):
        if priv != 'read':
            raise Exception('in copy, pointer must have read privilege, not ' + priv)
        increment(address, mem)
        return Pointer(address, priv)
      case _:
        raise Exception('in copy, unhandled value ' + repr(val))
    
def read(ptr, mem):
    match ptr:
      case Pointer(addr, priv):
        if priv == 'none':
            raise Exception('cannot read if do not have read privilege')
        return mem[addr][0]
      case _:
        raise Exception('in read expected a pointer, not ' + repr(ptr))

def write(ptr, val, mem):
    match ptr:
      case Pointer(addr, priv):
        if priv != 'write':
            raise Exception('cannot write if do not have write privilege')
        (old_val, count) = mem[addr]
        if count != 1:
            raise Exception('write requires unique ownership')
        kill(old_val, mem)
        mem[addr] = (copy(val, mem), count)
      case _:
        raise Exception('in read expected a pointer, not ' + repr(ptr))
    
    
def interp_exp(e, env, mem):
    match e:
      case Var(x):
        return env[x]
      case Int(n):
        return Integer(n)
      case Prim('add', args):
        left = interp_exp(args[0], env, mem)
        right = interp_exp(args[1], env, mem)
        return Integer(left.value + right.value)
      case Prim('sub', args):
        left = interp_exp(args[0], env, mem)
        right = interp_exp(args[1], env, mem)
        return Integer(left.value - right.value)
      case Prim('neg', args):
        return Integer(- interp_exp(args[0], env, mem).value)
      case New(arg):
        val = interp_exp(arg, env, mem)
        addr = len(mem)
        mem[addr] = (copy(val, mem), 0)
        return Pointer(addr, 'write')
      case Deref(arg):
        ptr = interp_exp(arg, env, mem)
        return read(ptr, mem)
      case Share(arg):
        ptr = interp_exp(arg, env, mem)
        return share(ptr, mem)
      case Release(arg):
        ptr = interp_exp(arg, env, mem)
        return release(ptr, mem)
      case _:
        raise Exception('error in interp_exp, unhandled: ' + repr(e)) 
    
def interp_stmt(s, env, mem):
    print('interp_stmt ' + repr(s))
    match s:
      case Return(e):
        return interp_exp(e, env, mem)
      case Init(var, init):
        val = interp_exp(init, env, mem)
        env[var] = bind(val, mem)
      case Assign(var, rhs):
        kill(env[var], mem)
        env[var] = interp_exp(rhs, env, mem)
      case Write(lhs, rhs):
        ptr = interp_exp(lhs, env, mem)
        val = interp_exp(rhs, env, mem)
        write(ptr, copy(val, mem), mem)
      case _:
        raise Exception('error in interp_stmt, unhandled: ' + repr(s)) 

def interp(p):
    env = {}
    memory = {}
    rv = None
    for s in p:
        rv = interp_stmt(s, env, memory)
        if not (rv is None):
            break
        print(env)
        print(memory)
        print()
    print(env)
    print(memory)
    print()
    return rv

if __name__ == "__main__":
    file = open(sys.argv[1], 'r')
    p = file.read()
    ast = parse(p)
    retval = interp(ast)
    print('return value:')
    print(retval)
