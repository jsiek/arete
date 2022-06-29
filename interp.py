from abstract_syntax import *
from dataclasses import dataclass
from parser import parse
from typing import List, Set, Dict, Tuple, Any
import sys
import copy

@dataclass
class Value:
    pass

@dataclass
class Integer(Value):
    value: int
    def __str__(self):
        return repr(self.value)
    def __repr__(self):
        return repr(self.value)

@dataclass
class Tuple(Value):
    elts: List[Value]
    def __str__(self):
        return "⟨" + ",".join([str(e) for e in self.elts]) + "⟩"
    def __repr__(self):
        return "⟨" + ",".join([str(e) for e in self.elts]) + "⟩"
    
@dataclass
class Pointer(Value):
    address: int
    privilege: str  # none, read, write
    __match_args__ = ("address", "privilege")

@dataclass
class Closure(Value):
    params: List[Any]
    body: Stmt
    env: Any # needs work
    __match_args__ = ("params", "body", "env")
    def __str__(self):
        return "closure"
    def __repr__(self):
        return "closure"
    
@dataclass
class Cell:
    value: Value
    owners: int
    observers: int
    def inc_owner(self):
        self.owners += 1
    def dec_owner(self):
        self.owners -= 1
        if self.count() == 0:
            self.value = None
    def inc_observer(self):
        self.observers += 1
    def dec_observer(self):
        self.observers -= 1
        if self.count() == 0:
            self.value = None
    def count(self):
        return self.owners + self.observers
        
trace = False
    
# End the life of a value.
# If the value is a pointer, decrement the target's reference count.
def kill(val, mem):
    match val:
      case Integer(value):
        pass
      case Pointer(addr, priv):
        if priv == 'none':
            mem[addr].dec_observer()
        else:
            mem[addr].dec_owner()
        val.addr = None
        val.privilege = None

# Copy a value.
# If it is a pointer, it must not have 'write' privilege.
def copy(val, mem):
    match val:
      case Integer(value):
        return Integer(value)
      case Pointer(addr, priv):
        if priv == 'write':
            raise Exception('to copy, pointer must not have write privilege')
        elif priv == 'read':
            mem[addr].inc_owner()
        elif priv == 'none':
            mem[addr].inc_observer()
        return Pointer(addr, priv)
      case Closure(params, body, env):
        return val # ??
      case _:
        raise Exception('in copy, unhandled value ' + repr(val))
    
def initialize(kind, val, mem):
  match val:
    case Integer(value):
      return Integer(value)
    case Pointer(addr, priv):
      if kind == 'take' or kind == 'borrow':
          if priv == 'write':
              mem[addr].inc_observer()
              val.priv = 'none'
              return Pointer(addr, 'write')
          else:
              raise Exception('take requires a write pointer')
      elif kind == 'share':
          if priv == 'write':
              val.priv = 'read'
          elif priv == 'none':
              raise Exception('share requires a read or write pointer')
          mem[addr].inc_owner()
          return Pointer(addr, 'read')
    case Closure(params, body, env):
      return val # ??
    case Tuple(elts):
      return val # ??
    case _:
      raise Exception('in initialize, unhandled value ' + repr(val))
        
def read(ptr, mem):
    match ptr:
      case Pointer(addr, priv):
        if priv == 'none':
            raise Exception('pointer does not have read privilege')
        return mem[addr].value
      case _:
        raise Exception('in read expected a pointer, not ' + repr(ptr))

def write(ptr, val, mem):
    match ptr:
      case Pointer(addr, priv):
        if priv != 'write':
            raise Exception('pointer does not have write privilege')
        if mem[addr].owners != 1:
            raise Exception('write requires unique ownership')
        kill(mem[addr].value, mem)
        mem[addr].value = copy(val, mem)
      case _:
        raise Exception('in read expected a pointer, not ' + repr(ptr))

def revive(ptr, mem):
    match ptr:
      case Pointer(addr, priv):
        if mem[addr].owners != 0:
            raise Exception("can't revive an aliased value")
        else:
            mem[addr].inc_owner()
            mem[addr].dec_observer()
            ptr.priv = 'write'
      case _:
        raise Exception('in revive expected a pointer, not ' + repr(ptr))
    
def interp_exp(e, env, mem):
    match e:
      case Var(x):
        if x not in env:
            raise Exception('use of undefined variable ' + x)
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
        mem[addr] = Cell(copy(val, mem), 1, 0)
        return Pointer(addr, 'write')
      case Deref(arg):
        ptr = interp_exp(arg, env, mem)
        return read(ptr, mem)
      case Lambda(params, body):
        return Closure(params, body, env)
      case Call(fun, args):
        f = interp_exp(fun, env, mem)
        vals = [interp_exp(arg, env, mem) for arg in args]
        match f:
            case Closure(params, body, clos_env):
              body_env = clos_env.copy()
              for (param, arg) in zip(params, vals):
                  body_env[param.ident] = initialize(param.kind, arg, mem)
              retval = interp_stmt(body, body_env, mem)
              for param in params:
                  kill(body_env[param.ident], mem)
              for (param, arg) in zip(params, vals):
                  if param.kind == 'borrow':
                      revive(arg, mem)
              return retval
            case _:
              raise Exception('expected function in call, not ' + repr(f))
      case TupleExp(elts):
        return Tuple([interp_exp(e, env, mem) for e in elts])
      case Index(arg, index):
        val = interp_exp(arg, env, mem)
        ind = interp_exp(index, env, mem)
        match val:
          case Tuple(elts):
            match ind:
              case Integer(i):
                return elts[i]
              case _:
                raise Exception('index must be an integer, not ' + repr(ind))
          case _:
            raise Excpeiont('cannot index into ' + repr(val))
      case _:
        raise Exception('error in interp_exp, unhandled: ' + repr(e)) 

def pattern_match(pat, val, matches):
    if trace:
        print('pattern_match(' + str(pat) + "," + str(val) + ")")
        print()
    match pat:
      case VarPat(id):
        matches[id] = val
        return True
      case TuplePat(pat_elts):
        match val:
          case Tuple(elts):
            if len(pat_elts) != len(elts):
                return False
            for (p, v) in zip(pat_elts, elts):
                r = pattern_match(p, v, matches)
                if not r:
                    return False
            return True
          case _:
            return False
      case _:
        raise Exception('error in pattern match, unhandled: ' + repr(pat))
    
def interp_stmt(s, env, mem):
    if trace:
        print('interp_stmt ' + repr(s))
        print(env)
        print(mem)
        print()
    match s:
      case Init(kind, var, init, rest):
        val = interp_exp(init, env, mem)
        env[var] = initialize(kind, val, mem)
        retval = interp_stmt(rest, env, mem)
        kill(env[var], mem)
        if kind == 'borrow':
            revive(val, mem)
        return retval
      case Write(lhs, rhs):
        ptr = interp_exp(lhs, env, mem)
        val = interp_exp(rhs, env, mem)
        write(ptr, val, mem)
      case Expr(e):
        interp_exp(e, env, mem)
      case Return(e):
        return interp_exp(e, env, mem)
      case Seq(first, rest):
        retval = interp_stmt(first, env, mem)
        if retval is None:
            return interp_stmt(rest, env, mem)
        else:
            return retval
      case Pass():
        pass
      case Match(arg, cases):
        val = interp_exp(arg, env, mem)
        for c in cases:
           matches = {}
           if pattern_match(c.pat, val, matches):
               body_env = env.copy()
               if trace:
                   print('matches')
                   print(matches)
                   print()
               for x,v in matches.items():
                   body_env[x] = v
               if trace:
                   print('body_env')
                   print(body_env)
                   print()
               return interp_stmt(c.body, body_env, mem)
        raise Exception('error, no match')
      case _:
        raise Exception('error in interp_stmt, unhandled: ' + repr(s)) 

def interp(p):
    env = {}
    mem = {}
    retval = interp_stmt(p, env, mem)
    if trace:
        print(env)
        print(mem)
        print()
    return retval

if __name__ == "__main__":
    file = open(sys.argv[1], 'r')
    expect_fail = False
    if 'fail' in sys.argv:
        expect_fail = True
    if 'trace' in sys.argv:
        trace = True
    p = file.read()
    ast = parse(p, trace)
    try:
        retval = interp(ast)
        if expect_fail:
            print("expected failure, but didn't")
            exit(-1)
        else:
            exit(retval.value)
    except Exception as ex:
        if expect_fail:
            exit(0)
        else:
            print('unexpected failure: ' + str(ex))
            raise
            exit(-1)

