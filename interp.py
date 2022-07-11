from abstract_syntax import *
from dataclasses import dataclass
from parser import parse, set_filename
from typing import List, Set, Dict, Tuple, Any
from fractions import Fraction
import numbers
import sys
import copy

@dataclass
class Value:
    temporary: bool

@dataclass
class Number(Value):
    value: numbers.Number
    def equals(self, other):
        return self.value == other.value
    def initialize(self, kind, location, ret=False):
      if self.temporary:
          self.temporary = False
          return self
      else:
          return Number(False, self.value)
    def copy(self):
        return Number(True, self.value)
    def duplicate(self, percentage):
        return Number(True, self.value)
    def return_copy(self, kind, location):
      if self.temporary:
          return self
      else:
          return Number(True, self.value)
    def kill(self, mem, location):
        pass
    def __str__(self):
        return repr(self.value)
    def __repr__(self):
        return repr(self.value)

@dataclass
class Boolean(Value):
    value: bool
    def equals(self, other):
        return self.value == other.value
    def initialize(self, kind, location, ret=False):
      if self.temporary:
          self.temporary = False
          return self
      else:
          return Boolean(False, self.value)
    def copy(self):
        return Boolean(True, self.value)
    def duplicate(self, percentage):
        return Boolean(True, self.value)
    def return_copy(self, kind, location):
      if self.temporary:
          return self
      else:
          return Boolean(True, self.value)
    def kill(self, mem, location):
        pass
    def __str__(self):
        return repr(self.value)
    def __repr__(self):
        return repr(self.value)
    
def priv_str(priv):
  if priv == 'none':
    return 'N'
  elif priv == 'read':
    return 'R'
  elif priv == 'write':
    return 'W'
  elif priv == 'dead':
    return 'D'
  elif priv is None:
    return 'None'
  elif isinstance(priv, Fraction):
    return str(priv.numerator) + '/' + str(priv.denominator)
  else:
    return str(priv)

@dataclass
class Pointer(Value):
    address: int
    privilege: Fraction    # none is 0, read is 1/n, write is 1/1
    lender: Value          # who this pointer borrowed from, if any
    borrowers: List[Value] # who borrowed from this pointer
    
    __match_args__ = ("temporary", "address", "privilege")

    def equals(self, other):
        return self.address == other.address
    
    def __str__(self):
        # return "⦅ " + str(self.address) + " @" + priv_str(self.privilege) \
        #     + ", " + ("tmp" if self.temporary else "prm") \
        #     + (" from: " +str(self.lender) if not self.lender is None else "") \
        #     + "⦆" 
        return "⦅ " + str(self.address) + " @" + priv_str(self.privilege) + "⦆" 
    
    def __repr__(self):
        return str(self)

    def transfer(self, percent, other, location):
        if self.address != other.address:
            error(location, "cannot transfer between different addresses: "
                  + str(self.address) + " != " + str(other.address))
        amount = other.privilege * percent
        other.privilege -= amount
        self.privilege += amount
        
    def copy(self):
        if True:
            # take all the privilege
            return self.duplicate(1)
        else:
            # take 1/2 the privilege
            return self.duplicate(Fraction(1,2))

    def duplicate(self, percentage):
        other_priv = self.privilege * percentage
        self.privilege -= other_priv
        ptr = Pointer(True, self.address, other_priv, self, [])
        self.borrowers.append(ptr)
        return ptr
    
    # self: the pointer being initialized from
    # kind: the privilege of the pointer to return
    def initialize(self, kind, location, ret=False):
      if kind == 'write':
          # if not writable(self.privilege):
          #     error(location, 'initializing writable pointer requires writable pointer, not ' + str(self))
          if self.temporary:
              self.temporary = False
              return self
          else:
              ptr = self.duplicate(1)
              ptr.temporary = False
              return ptr
      elif kind == 'read':
          if self.temporary:
              self.temporary = False
              return self
          elif ret == True:
              ptr = self.duplicate(1)
              ptr.temporary = False
              return ptr
          else:
              ptr = self.duplicate(Fraction(1,2))
              ptr.temporary = False
              return ptr
      else:
          raise Exception('initialize unexpected privilege: ' + priv)

    # Copy the return value of a function.
    # Similar to initialize with respect to permissions, but
    # produces a temporary value.
    def return_copy(self, kind, location):
      if self.temporary:
          return self
      else:
          return self.duplicate(1)
          
      # if kind == 'write':
      #     if not writable(self.privilege):
      #         error(location, 'initializing writable pointer requires writable pointer, not ' + str(self))
      #     if self.temporary:
      #         return self
      #     else:
      #         self.privilege = Fraction(0,1)
      #         ptr = Pointer(True, self.address, Fraction(1, 1), self, [])
      #         self.borrowers.append(ptr)
      #         return ptr
      # elif kind == 'read':
      #     if self.temporary:
      #         return self
      #     else:
      #         half = self.privilege / 2
      #         self.privilege = half
      #         ptr = Pointer(True, self.address, half, self, [])
      #         self.borrowers.append(ptr)
      #         return ptr
      # else:
      #     raise Exception('initialize unexpected privilege: ' + priv)
      
    def kill(self, mem, location):
        if trace:
            print('kill ' + str(self))
        if self.lender is None:
            # consider automatically deleting
            # if self.privilege == Fraction(1,1):
            #     delete(self, mem, location)
            if self.privilege != Fraction(0,1):
                warning(location, 'memory leak, killing nonempty pointer'
                        + ' without lender')
            for b in self.borrowers:
                b.lender = None
        else:
            # redirect my borrowers to my lender
            if not (self.lender.address is None):
                self.lender.privilege += self.privilege
                for b in self.borrowers:
                    b.lender = self.lender
        self.address = None
        self.privilege = Fraction(0,1)
        self.lender = None

def writable(frac):
    return frac == Fraction(1, 1)

def readable(frac):
    return Fraction(0, 1) < frac and frac < Fraction(1, 1)

def none(frac):
    return frac == Fraction(0, 1)

def check_privilege(frac: Fraction, kind: str):
    if kind == 'write':
        return writable(frac)
    elif kind == 'read':
        return readable(frac)
    elif kind == 'none':
        return none(frac)
    else:
        raise Exception('unrecognized privilege kind: ' + str(kind))

def privilege_to_fraction(priv):
    if priv == 'write':
        return Fraction(1, 1)
    elif priv == 'read':
        return Fraction(1, 2)
    elif priv == 'none':
        return Fraction(0, 1)
    else:
        raise Exception('unrecognized privilege: ' + priv)
    
@dataclass
class Closure(Value):
    params: List[Any]
    return_priv: str
    body: Stmt
    env: Any # needs work
    __match_args__ = ("temporary", "params", "return_priv", "body", "env")
    def initialize(self, kind, location, ret=False):
        return self # ???
    def kill(self, mem, location):
        pass # ???
    def __str__(self):
        return "closure"
    def __repr__(self):
        return "closure"
    
trace = False
next_address = 0

def allocate(vals, mem):
    global next_address
    addr = next_address
    next_address += 1
    mem[addr] = vals
    return Pointer(True, addr, Fraction(1,1), None, [])

def read(ptr, index, mem, location, dup):
    if not isinstance(ptr, Pointer):
        error(location, 'in read expected a pointer, not ' + str(ptr))
    if none(ptr.privilege):
        error(location, 'pointer does not have read privilege: ' + str(ptr))
    # whether to copy here or not?
    # see tests/fail_indirect_write
    if dup:
        retval = mem[ptr.address][index].duplicate(ptr.privilege)
    else:
        retval = mem[ptr.address][index]
    if trace:
        print('read ' + str(ptr) + ' @ ' + str(index))
        print('    from: ' + str(mem[ptr.address][index]))
        print('    to: ' + str(retval))
    return retval
    #return mem[ptr.address]

def write(ptr, index, val, mem, location):
    if not isinstance(ptr, Pointer):
        error(location, 'in write expected a pointer, not ' + str(ptr))
    if not writable(ptr.privilege):
        error(location, 'pointer does not have write privilege: ' + str(ptr))
    mem[ptr.address][index].kill(mem, location)
    if val.temporary:
        mem[ptr.address][index] = val
    else:
        mem[ptr.address][index] = val.copy()
    mem[ptr.address][index].temporary = False

def delete(ptr, mem, location):
    match ptr:
      case Pointer(tmp, addr, priv):
        if not writable(priv):
          error(location, 'delete needs writable pointer, not ' + str(ptr))
        for val in mem[addr]:
            val.kill(mem, location)
        del mem[addr]
        ptr.privilege = Fraction(0, 1)
        ptr.address = None
    
def allocate_locals(vars_kinds, vals, env, location):
    if trace:
        print('allocating ' + ', '.join([v for (v,k) in vars_kinds]))
    for ((var,kind), val) in zip(vars_kinds, vals):
        env[var] = val.initialize(kind, location)
    if trace:
        print('finish allocating ' + ', '.join([v for (v,k) in vars_kinds]))

def deallocate_locals(vars_kinds, vals, env, mem, location):
    if trace:
        print('deallocating ' + ', '.join([v for (v,k) in vars_kinds]))
    for (var,kind) in vars_kinds:
        env[var].kill(mem, location)
    if trace:
        print('finished deallocating ' + ', '.join([v for (v,k) in vars_kinds]))

def kill_temp(val, mem, location):
    if not (val is None):
        if val.temporary:
            val.kill(mem, location)
        
def call_function(fun, args, env, mem, location):
    f = interp_exp(fun, env, mem)
    vals = [interp_exp(arg, env, mem) for arg in args]
    match f:
      case Closure(tmp, params, return_priv, body, clos_env):
        body_env = clos_env.copy()
        vars_kinds = [(param.ident, param.kind) for param in params]
        allocate_locals(vars_kinds, vals, body_env, location)
        if trace:
            print('call ' + str(Call(location, fun, args)))
            print()
            
        try:
          retval = interp_stmt(body, body_env, mem, return_priv)
        except Exception as ex:
          raise Exception(error_header(location) + ' in call ' + str(Call(location, fun, args)) + '\n' + str(ex))
        
        if trace:
            print('deallocate locals from call to ' + str(fun))
        deallocate_locals(vars_kinds, vals, body_env, mem, location)
        kill_temp(f, mem, location)
        for val in vals:
            kill_temp(val, mem, location)
        if trace:
            print('return from ' + str(fun) + ' with ' + str(retval))
            print(env)
            print(mem)
            print()
        return retval
      case _:
        error(location, 'expected function in call, not ' + repr(f))
    
def interp_init(init, env, mem, ret=False):
    match init:
      case Initializer(kind, arg):
        val = interp_exp(arg, env, mem)
        return val.initialize(kind, init.location, ret=ret)
      case _:
        error(init.location, 'in interp_init, expected an initializer, not '
              + repr(init))

def to_number(val, location):
    match val:
      case Number(tmp, value):
        return value
      case _:
        error(location, 'expected an integer, not ' + str(val))

def to_boolean(val, location):
    match val:
      case Boolean(tmp, value):
        return value
      case _:
        error(location, 'expected a boolean, not ' + str(val))

def interp_exp(e, env, mem, dup=True, ret=False):
    match e:
      case Var(x):
        if x not in env:
            error(e.location, 'use of undefined variable ' + x)
        return env[x]
      case Int(n):
        return Number(True, n)
      case Bool(b):
        return Boolean(True, b)
      case Prim('equal', args):
        left = interp_exp(args[0], env, mem)
        right = interp_exp(args[1], env, mem)
        retval = Boolean(True, left.equals(right))
        kill_temp(left, mem, e.location)
        kill_temp(right, mem, e.location)
        return retval
      case Prim('not_equal', args):
        left = interp_exp(args[0], env, mem)
        right = interp_exp(args[1], env, mem)
        retval = Boolean(True, not left.equals(right))
        kill_temp(left, mem, e.location)
        kill_temp(right, mem, e.location)
        return retval
      case Prim('add', args):
        left = to_number(interp_exp(args[0], env, mem), e.location)
        right = to_number(interp_exp(args[1], env, mem), e.location)
        return Number(True, left + right)
      case Prim('sub', args):
        left = to_number(interp_exp(args[0], env, mem), e.location)
        right = to_number(interp_exp(args[1], env, mem), e.location)
        return Number(True, left - right)
      case Prim('mul', args):
        left = to_number(interp_exp(args[0], env, mem), e.location)
        right = to_number(interp_exp(args[1], env, mem), e.location)
        return Number(True, left * right)
      case Prim('div', args):
        left = to_number(interp_exp(args[0], env, mem), e.location)
        right = to_number(interp_exp(args[1], env, mem), e.location)
        return Number(True, Fraction(left, right))
      case Prim('neg', args):
        val = to_number(interp_exp(args[0], env, mem), e.location)
        return Number(True, - val)
      case Prim('and', args):
        left = to_boolean(interp_exp(args[0], env, mem), e.location)
        right = to_boolean(interp_exp(args[1], env, mem), e.location)
        return Boolean(True, left and right)
      case Prim('or', args):
        left = to_boolean(interp_exp(args[0], env, mem), e.location)
        right = to_boolean(interp_exp(args[1], env, mem), e.location)
        return Boolean(True, left or right)
      case Prim('not', args):
        val = to_boolean(interp_exp(args[0], env, mem), e.location)
        return Boolean(True, not val)
      case Prim('null'):
        return Pointer(True, None, Fraction(0,1), None, [])
      case Prim('is_null', args):
        ptr = interp_exp(args[0], env, mem)
        match ptr:
          case Pointer(tmp, addr, priv):
            retval = Boolean(True, addr is None)
          case _:
            retval = Boolean(True, False)
        kill_temp(ptr, mem, e.location)
        return retval
      case Prim('split', args):
        ptr = interp_exp(args[0], env, mem)
        ptr1 = ptr.duplicate(Fraction(1, 2))
        ptr2 = ptr.duplicate(Fraction(1, 1))
        return allocate([ptr1, ptr2], mem)
      case Prim('permission', args):
        ptr = interp_exp(args[0], env, mem, dup=False)
        return Number(True, ptr.privilege)
      case Prim('join', args):
        ptr1 = interp_exp(args[0], env, mem)
        ptr2 = interp_exp(args[1], env, mem)
        ptr = ptr1.duplicate(1)
        if trace:
            print('join ' + str(ptr1) + ' ' + str(ptr2))
        ptr.transfer(1, ptr2, e.location)
        if trace:
            print('into ' + str(ptr))
        return ptr
      case New(inits):
        vals = [interp_init(init, env, mem) for init in inits]
        return allocate(vals, mem)
      case Lambda(params, return_priv, body):
        return Closure(True, params, return_priv, body, env)
      case Call(fun, args):
        return call_function(fun, args, env, mem, e.location)
      case Index(arg, index):
        ptr = interp_exp(arg, env, mem, dup=dup)
        ind = interp_exp(index, env, mem)
        if trace:
            print('indexing ptr ' + str(ptr) + ' @ ' + str(ind))
        match ind:
          case Number(tmp, i):
            retval = read(ptr, i, mem, e.location, dup)
            kill_temp(ptr, mem, e.location)
            kill_temp(ind, mem, e.location)
            if trace:
                print('index result: ' + str(retval))
            return retval
          case _:
            error(e.location, 'index must be an integer, not ' + repr(ind))
      case _:
        error(e.location, 'error in interp_exp, unhandled: ' + repr(e)) 

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
      case _:
        raise Exception('error in pattern match, unhandled: ' + repr(pat))

def error_header(location):
    return '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
            
def error(location, msg):
    raise Exception(error_header(location) + msg)

def warning(location, msg):
    header = '{file}:{line1}.{column1}-{line2}.{column2}: ' \
        .format(file=location.filename,
                line1=location.line, column1=location.column,
                line2=location.end_line, column2=location.end_column)
    print(header + 'warning: ' + msg)

def interp_stmt(s, env, mem, return_priv):
    if trace:
        print()
        print('interp_stmt ' + repr(s))
        print(env)
        print(mem)
        print()
    match s:
      case VarInit(var, init, rest):
        # allow recursion
        rest_env = env.copy()
        rest_env[var.ident] = None
        val = interp_exp(init, rest_env, mem)
        vars_kinds = [(var.ident, var.kind)]
        allocate_locals(vars_kinds, [val], rest_env, s.location)
        retval = interp_stmt(rest, rest_env, mem, return_priv)
        deallocate_locals(vars_kinds, [val], rest_env, mem, s.location)
        return retval
      case Write(lhs, index, rhs):
        ptr = interp_exp(lhs, env, mem, dup=False)
        i = interp_exp(index, env, mem)
        val = interp_exp(rhs, env, mem)
        write(ptr, to_number(i, s.location), val, mem, s.location)
        kill_temp(ptr, mem, s.location)
        kill_temp(i, mem, s.location)
        kill_temp(val, mem, s.location)
      case Transfer(lhs, percent, rhs):
        dest_ptr = interp_exp(lhs, env, mem, dup=False)
        amount = to_number(interp_exp(percent, env, mem), s.location)
        src_ptr = interp_exp(rhs, env, mem, dup=False)
        if trace:
            print('transfering ' + str(amount) + ' from ' + str(src_ptr) \
                  + ' to ' + str(dest_ptr))
        dest_ptr.transfer(amount, src_ptr, s.location)
        if trace:
            print('after, src= ' + str(src_ptr) + ' dest= ' + str(dest_ptr))
      case Expr(e):
        val = interp_exp(e, env, mem)
        kill_temp(val, mem, s.location)
      case Assert(e):
        val = to_boolean(interp_exp(e, env, mem), s.location)
        if not val:
          error(e.location, "assertion failed: " + str(e))
      case Return(e):
        retval = interp_exp(e, env, mem, ret=True)
        return retval.return_copy(return_priv, e.location)
      case Seq(first, rest):
        retval = interp_stmt(first, env, mem, return_priv)
        if retval is None:
            return interp_stmt(rest, env, mem, return_priv)
        else:
            return retval
      case Pass():
        pass
      case IfStmt(cond, thn, els):
        c = to_boolean(interp_exp(cond, env, mem), cond.location)
        if c:
            return interp_stmt(thn, env, mem, return_priv)
        else:
            return interp_stmt(els, env, mem, return_priv)
      case Match(arg, cases):
        val = interp_exp(arg, env, mem)
        for c in cases:
           matches = {}
           if pattern_match(c.pat, val, matches):
               kill_temp(val, mem, arg.location)
               body_env = env.copy()
               if trace:
                   print('matches')
                   print(matches)
                   print()
               vals = [v for x, (kind,v) in matches.items()]
               vars_kinds = [(x,kind) for x, (kind,v) in matches.items()]
               allocate_locals(vars_kinds, vals, body_env, c.location)
               if trace:
                   print('case body_env')
                   print(body_env)
                   print(mem)
                   print()
               retval = interp_stmt(c.body, body_env, mem, return_priv)
               deallocate_locals(vars_kinds, vals, body_env, mem, c.location)
               return retval
        error(s.location, 'no case was a match for ' + str(val))
      case Delete(arg):
        ptr = interp_exp(arg, env, mem)
        if trace:
            print('delete ' + str(ptr))
        delete(ptr, mem, s.location)
        kill_temp(ptr, mem, s.location)
        if trace:
            print(env)
            print(mem)
            print()
      case _:
        raise Exception('error in interp_stmt, unhandled: ' + repr(s)) 

def interp(p):
    env = {}
    mem = {}
    retval = interp_stmt(p, env, mem, 'read')
    if trace:
        print(env)
        print(mem)
        print()
    if len(mem) > 0:
        print('result: ' + str(retval.value))
        error(p.location, 'memory leak, memory size = ' + str(len(mem))) 
    return retval

if __name__ == "__main__":
    filename = sys.argv[1]
    set_filename(filename)
    file = open(filename, 'r')
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
            #print('unexpected failure: ' + str(ex))
            print(str(ex))
            print()


