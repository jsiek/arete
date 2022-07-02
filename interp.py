from abstract_syntax import *
from dataclasses import dataclass
from parser import parse
from typing import List, Set, Dict, Tuple, Any
import sys
import copy

@dataclass
class Value:
    temporary: bool

@dataclass
class Integer(Value):
    value: int
    def __str__(self):
        return repr(self.value)
    def __repr__(self):
        return repr(self.value)

@dataclass
class Boolean(Value):
    value: bool
    def __str__(self):
        return repr(self.value)
    def __repr__(self):
        return repr(self.value)
    
@dataclass
class Tuple(Value):
    elts: List[Value]
    def __str__(self):
        return "⟨" + ", ".join([str(e) for e in self.elts]) + "⟩"
    def __repr__(self):
        return str(self)
    
def priv_str(priv):
  if priv == 'none':
    return 'N'
  elif priv == 'read':
    return 'R'
  elif priv == 'write':
    return 'W'
  elif priv == 'dead':
    return 'D'
  else:
    raise Exception('in priv_str, unrecognized privilege: ' + str(priv))
    
@dataclass
class Pointer(Value):
    address: int
    privilege: str  # none, read, write
    __match_args__ = ("temporary", "address", "privilege")
    def __str__(self):
        return "⦅" + str(self.address) + "@" + priv_str(self.privilege) + "⦆"
    def __repr__(self):
        return str(self)

@dataclass
class Closure(Value):
    params: List[Any]
    body: Stmt
    env: Any # needs work
    __match_args__ = ("temporary", "params", "body", "env")
    def __str__(self):
        return "closure"
    def __repr__(self):
        return "closure"
    
@dataclass
class Cell:
    value: Value
    writers: int      # at most 1 writer, if 1 writer, no readers
    readers: int
    bystanders: int

    def initialize(self, priv, addr):
      if priv == 'write':
          if self.writers > 0 or self.readers > 0:
              raise Exception('write privilege requires unique ownership')
          self.writers = 1
          return Pointer(False, addr, 'write')
      elif priv == 'read':
          if self.writers != 0:
              raise Exception('read privilege requires no writers')
          self.readers += 1
          return Pointer(False, addr, 'read')
      else:
          raise Exception('initialize unexpected privilege: ' + priv)
      
    def copy(self, ptr):
        match ptr:
            case Pointer(tmp, addr, priv):
              if priv == 'write':
                  raise Exception('cannot copy a write pointer, share first')
              elif priv == 'read':
                  self.readers += 1
              elif priv == 'none':
                  self.bystanders += 1
              return Pointer(tmp, addr, priv)
            case _:
              raise Exception('expected Pointer in Cell.copy, not ' + str(ptr))

    def acquire(self, priv, ptr):
        if priv == 'write':
            if self.writers > 0:
                raise Exception('cannot acquire write, other writers')
            self.writers = 1
            ptr.privilege = 'write'
        elif priv == 'read':
            if self.writers > 0:
                raise Exception('cannot acquire read, other writers')
            self.readers += 1
            ptr.privilege = 'read'
        elif priv == 'none':
            self.bystanders += 1
            ptr.privilege = 'none'
        return ptr

    def kill(self, val):
        match val:
          case Pointer(tmp, addr, priv):
            if priv == 'dead':
                raise Exception('pointer already dead ' + str(val))
            elif priv == 'none':
                self.bystanders -= 1
            elif priv == 'read':
                self.readers -= 1
            elif priv == 'write':
                self.writers -= 1
            val.privilege = 'dead'
          case _:
            raise Exception('Cell.kill expected pointer, not ' + str(val))
          
    def __str__(self):
        return "⟦" +  str(self.value) + "|" + str(self.writers) + "/" \
               + str(self.readers) + "/" + str(self.bystanders) + "⟧"
    
    def __repr__(self):
        return str(self)
        
trace = False
    
# End the life of a value.
# If the value is a pointer, decrement the target's reference count.
def kill(val, mem):
    if trace:
        print('kill ' + str(val))
    match val:
      case Integer(tmp, value):
        pass
      case Pointer(tmp, addr, priv):
        mem[addr].kill(val)
      case Tuple(tmp, elts):
        for elt in elts:
            kill(elt, mem)
    if trace:
        print(mem)
        print()

# Copy a value.
def copy(val, mem):
    if trace:
        print('copy ' + str(val))
    match val:
      case Integer(tmp, value):
        return Integer(tmp, value)
      case Boolean(tmp, value):
        return Boolean(tmp, value)
      case Pointer(tmp, addr, priv):
        return mem[addr].copy(val)
      case Closure(tmp, params, body, env):
        return val # ??
      case Tuple(tmp, elts):
        return Tuple(True, [copy(v, mem) for v in elts])
      case _:
        raise Exception('in copy, unhandled value ' + repr(val))
    
def initialize(kind, val, mem):
  if trace:
      print('initialize ' + str(val) + ' into ' + kind)
  retval = None
  if val.temporary and trace:
      print('from temporary')
  match val:
    case Integer(tmp, value):
      if tmp:
          retval = val
          val.temporary = False
      else:
          retval = Integer(False, value)
    case Boolean(tmp, value):
      if tmp:
          retval = val
          val.temporary = False
      else:
          retval = Boolean(False, value)
    case Pointer(tmp, addr, priv):
      if tmp:
          if priv != kind:
              raise Exception('initialize privilege mismatch: ' + kind + ' != ' + priv)
          val.temporary = False
          retval = val
      else:
          retval = mem[addr].initialize(kind, addr)
    case Closure(tmp, params, body, env):
      retval = val # ??
    case Tuple(tmp, elts):
      if tmp:
          retval = val
      else:
          retval = copy(val, mem)
    case _:
      raise Exception('in initialize, unhandled value ' + repr(val))
  if trace:
      print('initialized from ' + str(val) + ' to ' + str(retval))
  return retval
        
def read(ptr, mem):
    match ptr:
      case Pointer(tmp, addr, priv):
        if priv == 'none':
            raise Exception('pointer does not have read privilege')
        if mem[addr].writers > 1:
            raise Exception('read requires no other writers')
        return mem[addr].value
      case _:
        raise Exception('in read expected a pointer, not ' + repr(ptr))

def write(ptr, val, mem):
    match ptr:
      case Pointer(tmp, addr, priv):
        if priv != 'write':
            raise Exception('pointer does not have write privilege')
        if mem[addr].writers > 1 or mem[addr].readers > 0:
            raise Exception('write requires unique ownership')
        kill(mem[addr].value, mem)
        mem[addr].value = copy(val, mem)
      case _:
        raise Exception('in read expected a pointer, not ' + repr(ptr))

def allocate_locals(vars_kinds, vals, env, mem):
    if trace:
        print('allocating ' + ', '.join([v for (v,k) in vars_kinds]))
    for ((var,kind), val) in zip(vars_kinds, vals):
        env[var] = initialize(kind, val, mem)
    if trace:
        print('finish allocating ' + ', '.join([v for (v,k) in vars_kinds]))

def deallocate_locals(vars_kinds, vals, env, mem):
    if trace:
        print('deallocating ' + ', '.join([v for (v,k) in vars_kinds]))
    for (var,kind) in vars_kinds:
        kill(env[var], mem)
    if trace:
        print('finished deallocating ' + ', '.join([v for (v,k) in vars_kinds]))
        
def call_function(fun, args, env, mem):
    f = interp_exp(fun, env, mem)
    vals = [interp_exp(arg, env, mem) for arg in args]
    match f:
        case Closure(tmp, params, body, clos_env):
          body_env = clos_env.copy()
          vars_kinds = [(param.ident, param.kind) for param in params]
          allocate_locals(vars_kinds, vals, body_env, mem)
          if trace:
              print('call ' + str(Call(fun, args)))
              print()
          retval = interp_stmt(body, body_env, mem)
          if trace:
              print('function parameter cleanup')
          deallocate_locals(vars_kinds, vals, body_env, mem)
          if trace:
              print('return from ' + str(fun) + ' with ' + str(retval))
              print(env)
              print(mem)
              print()
          return retval
        case _:
          raise Exception('expected function in call, not ' + repr(f))
    
def interp_init(init, env, mem):
    match init:
      case Initializer(kind, arg):
        val = interp_exp(arg, env, mem)
        return initialize(kind, val, mem)
      case _:
        raise Exception('in interp_init, expected an initializer, not '
                        + repr(init))
    
def interp_exp(e, env, mem):
    match e:
      case Var(x):
        if x not in env:
            raise Exception('use of undefined variable ' + x)
        return env[x]
      case Int(n):
        return Integer(True, n)
      case Bool(b):
        return Boolean(True, b)
      case Prim('add', args):
        left = interp_exp(args[0], env, mem)
        right = interp_exp(args[1], env, mem)
        return Integer(True, left.value + right.value)
      case Prim('sub', args):
        left = interp_exp(args[0], env, mem)
        right = interp_exp(args[1], env, mem)
        return Integer(True, left.value - right.value)
      case Prim('neg', args):
        val = interp_exp(args[0], env, mem)
        return Integer(True, - val.value)
      case New(init):
        val = interp_init(init, env, mem)
        addr = len(mem)
        mem[addr] = Cell(val, 0, 1, 0)
        return Pointer(True, addr, 'read')
      case Deref(arg):
        ptr = interp_exp(arg, env, mem)
        val = read(ptr, mem)
        return val
      case Acquire(arg, new_priv):
        ptr = interp_exp(arg, env, mem)
        match ptr:
          case Pointer(tmp, addr, priv):
            mem[addr].kill(ptr)
            if trace:
                print('acquire ' + str(ptr) + ' ! ' + new_priv)
                print(env)
                print(mem)
                print()
            return mem[addr].acquire(new_priv, ptr)
          case _:
            raise Exception('acquire expects a pointer, not ' + str(ptr))
      case Lambda(params, body):
        return Closure(True, params, body, env)
      case Call(fun, args):
        return call_function(fun, args, env, mem)
      case TupleExp(inits):
        return Tuple(True, [interp_init(init, env, mem) for init in inits])
      case Index(arg, index):
        val = interp_exp(arg, env, mem)
        ind = interp_exp(index, env, mem)
        match val:
          case Tuple(tmp, elts):
            match ind:
              case Integer(tmp, i):
                return elts[i]
              case _:
                raise Exception('index must be an integer, not ' + repr(ind))
          case _:
            raise Exception('cannot index into ' + repr(val))
      case _:
        raise Exception('error in interp_exp, unhandled: ' + repr(e)) 

def pattern_match(pat, val, matches):
    if trace:
        print('pattern_match(' + str(pat) + "," + str(val) + ")")
        print()
    match pat:
      case WildCard():
        return True
      case VarPat(kind, id):
        matches[id] = (kind, val)
        return True
      case TuplePat(pat_elts):
        match val:
          case Tuple(tmp, elts):
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
      case VarInit(var, init, rest):
        # allow recursion
        rest_env = env.copy()
        rest_env[var] = None
        val = interp_exp(init.arg, rest_env, mem)
        vars_kinds = [(var,init.kind)]
        allocate_locals(vars_kinds, [val], rest_env, mem)
        retval = interp_stmt(rest, rest_env, mem)
        deallocate_locals(vars_kinds, [val], rest_env, mem)
        return retval
      case Write(lhs, rhs):
        ptr = interp_exp(lhs, env, mem)
        val = interp_exp(rhs, env, mem) # ???
        write(ptr, val, mem)
      case Expr(e):
        interp_exp(e, env, mem)
      case Return(e):
        retval = interp_exp(e, env, mem)
        retval = copy(retval, mem)
        retval.temporary = True
        return retval
      case Seq(first, rest):
        retval = interp_stmt(first, env, mem)
        if retval is None:
            return interp_stmt(rest, env, mem)
        else:
            return retval
      case Pass():
        pass
      case IfStmt(cond, thn, els):
        c = interp_exp(cond, env, mem)
        if c.value:
            return interp_stmt(thn, env, mem)
        else:
            return interp_stmt(els, env, mem)
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
               vars_kinds = [(x,kind) for x, (kind,v) in matches.items()]
               vals = [v for x, (kind,v) in matches.items()]
               allocate_locals(vars_kinds, vals, body_env, mem)
               if trace:
                   print('case body_env')
                   print(body_env)
                   print(mem)
                   print()
               retval = interp_stmt(c.body, body_env, mem)
               deallocate_locals(vars_kinds, vals, body_env, mem)
               return retval
        raise Exception('error, no match')
      case Delete(arg):
        p = interp_exp(arg, env, mem)
        if trace:
            print('delete ' + str(p))
        match p:
          case Pointer(tmp, addr, priv):
            if priv == 'write':
              mem[addr] = None
            else:
              raise Exception('delete require write privilege, not ' + priv)
        if trace:
            print(env)
            print(mem)
            print()
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
            if trace:
                print('result: ' + str(retval.value))
            exit(retval.value)
    except Exception as ex:
        if expect_fail:
            exit(0)
        else:
            print('unexpected failure: ' + str(ex))
            print()
            raise
            exit(-1)

