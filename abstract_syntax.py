from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction
from utilities import *

verbose = False

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # read, write
    ident: str
    type_annot: Type
    __match_args__ = ("kind", "ident")
    def __str__(self):
        return self.kind + ' ' + self.ident + ': ' + str(self.type_annot)
    def __repr__(self):
        return str(self)

# Miscelaneous

@dataclass
class Initializer:
  location: Meta
  percentage: Exp
  arg: Exp
  __match_args__ = ("location", "percentage", "arg")
  def __str__(self):
      return str(self.percentage) + " of " + str(self.arg)
  def __repr__(self):
      return str(self)
  def free_vars(self):
      percent_fv = set() if isinstance(self.percentage, str) \
          else self.percentage.free_vars()
      return percent_fv | self.arg.free_vars()
  def step(self, action, machine):
    if action.state == 0:
      if self.percentage == 'default':
        if isinstance(action.context, AddressCtx):
            self.percentage = Frac(self.location, action.context.percentage)
        else:
            self.percentage = Frac(self.location, Fraction(1,2))
      machine.schedule(self.percentage, action.env)
    elif action.state == 1:
      percent = action.results[0][0]
      amount = to_number(percent, self.location)
      if isinstance(action.context, AddressCtx):
          ctx = AddressCtx(True, amount)
      elif isinstance(action.context, ValueCtx):
          ctx = ValueCtx(True, amount)
      machine.schedule(self.arg, action.env, ctx)
    else:
      val = action.results[1][0]
      val_copy = val.duplicate(1)
      machine.finish_expression(val_copy, self.location)
      
# Expressions

# Dimitri:
# lvalue for let, inout, and set parameters, rvalue for sink parameters.

@dataclass
class Call(Exp):
  fun: Exp
  args: List[Initializer]
  
  __match_args__ = ("fun", "args")
  
  def __str__(self):
      return str(self.fun) \
          + "(" + ", ".join([str(arg) for arg in self.args]) + ")"
  
  def __repr__(self):
      return str(self)
  
  def free_vars(self):
      return self.fun.free_vars() \
          | set().union(*[arg.free_vars() for arg in self.args])
  
  def set_closure(self, action, machine):
      if action.clos is None:
        action.clos = action.results[0][0]
        if not isinstance(action.clos, Closure):
          error(self.location, 'expected function in call, not '
                + str(action.clos))
          
  def step(self, action, machine):
    if action.state == 0:
      # evaluate the operator subexpression
      machine.schedule(self.fun, action.env)
      action.clos = None
    elif action.state <= len(self.args):
      self.set_closure(action, machine)
      # evaluate the operand subexpressions
      percent = priv_to_percent(action.clos.params[action.state - 1].kind)
      machine.schedule(self.args[action.state - 1], action.env,
                       AddressCtx(True, percent))
    elif action.state == len(self.args) + 1:
      self.set_closure(action, machine)
      # call the function
      match action.clos:
        case Closure(name, params, ret_mode, body, clos_env):
          action.params = params
          action.body_env = clos_env.copy()
          args = [val for val,ctx in action.results[1:]]
          if len(params) != len(args):
            error(self.location, 'wrong number of arguments, expected '
                  + str(len(params)) + ' not ' + str(len(args)))
          # In the following, duplicate the val? -Jeremy
          var_priv_vals = [(p.ident, p.kind, arg) \
                           for p, arg in zip(params, args)]
          allocate_locals(var_priv_vals, action.body_env, machine.memory,
                          self.location)
          machine.push_frame()
          machine.schedule(body, action.body_env, return_mode=ret_mode)
        case _:
          error(self.location, 'expected function in call, not '
                + str(action.clos))
    else:
      # return from the function
      deallocate_locals([p.ident for p in action.params], action.body_env,
                        machine.memory, self.location)
      if action.return_value is None:
        action.return_value = Void()
      if isinstance(action.context, ValueCtx):
        if action.clos.return_mode == 'value':
          retval = action.return_value
        elif action.clos.return_mode == 'address':
          retval = machine.memory.read(action.return_value, self.location,
                                       AddressCtx(True, Fraction(1,1)))
          action.return_value.kill(machine.memory, self.location)
        else:
          raise Exception('unrecognized return_mode: '
                          + action.clos.return_mode)
      elif isinstance(action.context, AddressCtx):
        if action.clos.return_mode == 'value':
          retval = machine.memory.allocate(action.return_value)
        elif action.clos.return_mode == 'address':
          retval = action.return_value # duplicate?
        else:
          raise Exception('unrecognized return_mode: '
                          + action.clos.return_mode)
      else:
        error(self.location, 'unknown context ' + repr(action.context))
        
      machine.finish_expression(retval, self.location)

@dataclass
class Prim(Exp):
    op: str
    args: List[Exp]
    __match_args__ = ("op", "args")
    def __str__(self):
        return self.op + \
            "(" + ", ".join([str(arg) for arg in self.args]) + ")"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set().union(*[arg.free_vars() for arg in self.args])
    def step(self, action, machine):
      if action.state < len(self.args):
        dup = not self.op in set(['permission','upgrade', 'split','join'])
        context = ValueCtx(dup, Fraction(1,2))
        machine.schedule(self.args[action.state], action.env, context)
      else:
        retval = eval_prim(self.op, [val for val, ctx in action.results],
                           machine, self.location)
        if isinstance(action.context, AddressCtx):
          # join produces an address, no need to allocate
          if self.op != 'join':
            retval = machine.memory.allocate(retval)
        machine.finish_expression(retval, self.location)
            
@dataclass
class Member(Exp):
    arg: Exp
    field: str
    __match_args__ = ("arg", "field")
    def __str__(self):
        return str(self.arg) + "." + self.field
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env, AddressCtx(True, Fraction(1,2)))
      else:
        mod_ptr = action.results[0][0]
        mod = machine.memory.read(mod_ptr, self.location,
                                  ValueCtx(False, Fraction(1,1)))
        if not isinstance(mod, Module):
          error(e.location, "expected a module, not " + str(val))
        if self.field in mod.exports.keys():
          ptr = mod.exports[self.field]
          if isinstance(action.context, ValueCtx):
            if action.context.duplicate:
              result = machine.memory.read(ptr, self.location, action.context)
            else:
              result = machine.memory.raw_read(ptr.address, ptr.path,
                                               self.location)
          elif isinstance(action.context, AddressCtx):
            if action.context.duplicate:
              result = ptr.duplicate(action.context.percentage)
            else:
              result = ptr
          else:
            raise Exception('in Member.step, bad context '
                            + repr(action.context))
          machine.finish_expression(result, self.location)
        else:
          error(self.location, 'no member ' + self.field
                + ' in module ' + mod.name)

# TODO: do we need `new`? Can it be replaced by taking the address
#   of a 1-element tuple? -Jeremy
@dataclass
class New(Exp):
    init: Initializer
    __match_args__ = ("init",)
    def __str__(self):
        return 'new ' + str(self.init)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.init, action.env, ValueCtx(True, Fraction(1,1)))
      else:
        ptr = machine.memory.allocate(action.results[0][0].duplicate(1))
        if isinstance(action.context, ValueCtx):
            result = ptr
        elif isinstance(action.context, AddressCtx):
            result = machine.memory.allocate(ptr)
        if not action.context.duplicate:
            error(self.location, 'new not allowed in this context')
        machine.finish_expression(result, self.location)

@dataclass
class Array(Exp):
    size: Exp
    arg: Exp
    __match_args__ = ("size","arg")
    def __str__(self):
        return "new " + "[" + str(self.size) + "]" + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.size.free_vars() | self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.size, action.env)
      elif action.state == 1:
        machine.schedule(self.arg, action.env)
      else:
        sz = action.results[0][0]
        val = action.results[1][0]
        size = to_integer(sz, self.location)
        vals = [val.duplicate(Fraction(1,2)) for i in range(0,size-1)]
        vals.append(val)
        array = TupleValue(vals)
        if isinstance(action.context, ValueCtx):
            result = array
        elif isinstance(action.context, AddressCtx):
            result = machine.memory.allocate(array)
        if not action.context.duplicate:
          error(self.location, 'arrays not allowed in this context')
        machine.finish_expression(result, self.location)

@dataclass
class TupleExp(Exp):
    inits: List[Initializer]
    __match_args__ = ("inits",)
    def __str__(self):
        return '(new ' + ', '.join([str(e) for e in self.inits]) + ')'
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set().union(*[init.free_vars() for init in self.inits])
    def step(self, action, machine):
      if action.state < len(self.inits):
        machine.schedule(self.inits[action.state], action.env)
      else:
        tup = TupleValue([val.duplicate(1) for (val,ctx) in action.results])
        if isinstance(action.context, ValueCtx):
          result = tup
        elif isinstance(action.context, AddressCtx):
          result = machine.memory.allocate(tup)
        if not action.context.duplicate:
          error(self.location, 'tuple not allowed in this context')
        machine.finish_expression(result, self.location)
        
@dataclass
class Var(Exp):
    ident: str
    __match_args__ = ("ident",)
    def __str__(self):
        return self.ident
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set([self.ident])
    def step(self, action, machine):
        if self.ident not in action.env:
            error(self.location, 'use of undefined variable ' + self.ident)
        ptr = action.env[self.ident]
        if isinstance(action.context, ValueCtx):
          if action.context.duplicate:
            result = machine.memory.read(ptr, self.location, action.context)
          else:
            result = machine.memory.raw_read(ptr.address, ptr.path,
                                             self.location)
        elif isinstance(action.context, AddressCtx):
          if action.context.duplicate:
            result = ptr.duplicate(action.context.percentage)
          else:
            result = ptr
        else:
          raise Exception('in Var.step, bad context ' + repr(action.context))
        machine.finish_expression(result, self.location)

@dataclass
class Int(Exp):
    value: int
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action, machine):
        val = Number(self.value)
        if isinstance(action.context, ValueCtx):
            result = val
        elif isinstance(action.context, AddressCtx):
            result = machine.memory.allocate(val)
        if not action.context.duplicate:
          error(self.location, 'integer not allowed in this context')
        machine.finish_expression(result, self.location)

@dataclass
class Frac(Exp):
    value: Fraction
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action,  machine):
        val = Number(self.value)
        if isinstance(action.context, ValueCtx):
            result = val
        elif isinstance(action.context, AddressCtx):
            result = machine.memory.allocate(val)
        if not action.context.duplicate:
          error(self.location, 'fraction not allowed in this context')
        machine.finish_expression(result, self.location)
    
@dataclass
class Bool(Exp):
    value: bool
    __match_args__ = ("value",)
    def __str__(self):
        return str(self.value)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action, machine):
        val = Boolean(self.value)
        if isinstance(action.context, ValueCtx):
            result = val
        elif isinstance(action.context, AddressCtx):
            result = machine.memory.allocate(val)
        if not action.context.duplicate:
          error(self.location, 'Boolean not allowed in this context')
        machine.finish_expression(result, self.location)
    
@dataclass
class Index(Exp):
    arg: Exp
    index: Exp
    __match_args__ = ("arg", "index")
    def __str__(self):
        return str(self.arg) + "[" + str(self.index) + "]"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() | self.index.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env, action.context)
      elif action.state == 1:
        machine.schedule(self.index, action.env)
      else:
        ind = action.results[1][0]
        i = to_integer(ind, self.location)
        if isinstance(action.context, ValueCtx):
          if tracing_on():
              print('in Index.step, ValueCtx')
          tup = action.results[0][0]
          if not isinstance(tup, TupleValue):
            error(self.location, 'expected a tuple, not ' + str(tup))
          if action.context.duplicate:
            retval = tup.elts[int(i)].duplicate(1)
          else:
            retval = tup.elts[int(i)]
        elif isinstance(action.context, AddressCtx):
          if tracing_on():
              print('in Index.step, AddressCtx')
          ptr = action.results[0][0]
          # what if not action.context.duplicate? -Jeremy
          retval = ptr.element_address(int(i), action.context.percentage)
        else:
          error(self.location, 'unrecognized context ' + repr(action.context))
        
        machine.finish_expression(retval, self.location)

@dataclass
class Deref(Exp):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return '*' + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env, action.context)
      else:
        if tracing_on():
            print('in Deref.step')
        ptr = action.results[0][0]
        if not isinstance(ptr, Pointer):
          error(self.location, 'deref expected a pointer, not ' + str(ptr))
        retval = machine.memory.read(ptr, self.location, action.context)
        machine.finish_expression(retval, self.location)

@dataclass
class AddressOf(Exp):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return '&' + str(self.arg)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env,
                         AddressCtx(action.context.duplicate, Fraction(1,1)))
      else:
        if isinstance(action.context, ValueCtx):
          ptr = action.results[0][0]
          if action.context.duplicate:
            retval = ptr.duplicate(action.context.percentage)
          else:
            retval = ptr
        else:
          error(self.location, '& (address of) not allowed in this context')
        machine.finish_expression(retval, self.location)
        
@dataclass
class Lambda(Exp):
    params: List[Param]
    return_mode: str    # 'value' or 'address'
    body: Stmt
    name: str = "lambda"
    __match_args__ = ("params", "return_mode", "body", "name")
    def __str__(self):
        return "function " \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " { " + str(self.body) + " }"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars() - set([p.ident for p in self.params])
    def step(self, action, machine):
        clos_env = {}
        free = self.body.free_vars() - set([p.ident for p in self.params])
        for x in free:
            if not x in action.env.keys():
              error(self.location, 'in closure, undefined variable ' + x)
            v = action.env[x]
            clos_env[x] = v.duplicate(Fraction(1,2))            
            # if not (v is None):
            #     clos_env[x] = v.duplicate(Fraction(1,2))
            # else:
            #     clos_env[x] = action.env[x]
        clos = Closure(self.name, self.params, self.return_mode, self.body,
                       clos_env)
        if isinstance(action.context, ValueCtx):
            result = clos
        elif isinstance(action.context, AddressCtx):
            result = machine.memory.allocate(clos)
        else:
            error(self.location, 'function not allowed in this context')
        machine.finish_expression(result, self.location)
    
@dataclass
class IfExp(Exp):
    cond: Exp
    thn: Exp
    els: Exp
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
        return "(" + str(self.cond) + "?" + str(self.thn) \
            + " : " + str(self.els) + ")"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.cond, action.env)
      elif action.state == 1:
        cond = action.results[0][0]
        if to_boolean(cond, self.location):
          machine.schedule(self.thn, action.env, action.context)
        else:
          machine.schedule(self.els, action.env, action.context)
      elif action.state == 2:
        retval = action.results[1][0].duplicate(1)
        machine.finish_expression(retval, self.location)
    
@dataclass
class Let(Exp):
    var: Param
    init: Initializer
    body: Exp
    __match_args__ = ("var", "init", "body")
    def __str__(self):
        return "var " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() | \
            (self.body.free_vars() - set([self.var.ident]))
    def step(self, action, machine):
      if action.state == 0:
        context = AddressCtx(True, priv_to_percent(self.var.kind))
        machine.schedule(self.init, action.env, context)
      elif action.state == 1:
        val = action.results[0][0]
        action.body_env = action.env.copy()
        var_priv_vals = [(self.var.ident, self.var.kind, val)]
        allocate_locals(var_priv_vals, action.body_env, machine.memory,
                        self.location)
        machine.schedule(self.body, action.body_env, action.context)
      else:
        deallocate_locals([self.var.ident], action.body_env, machine.memory,
                          self.location)
        result = action.results[1][0].duplicate(1)
        machine.finish_expression(result, self.location)

@dataclass
class FutureExp(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
    return "future " + str(self.arg)
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.arg.free_vars()
  def step(self, action, machine):
    thread = machine.spawn(self.arg, action.env)
    if isinstance(action.context, ValueCtx):
      retval = Future(thread)
    elif isinstance(action.context, AddressCtx):
      future = Future(thread)
      retval = machine.memory.allocate(future)
    if not action.context.duplicate:
        error(self.location, 'future not allowed in this context')
    machine.finish_expression(retval, self.location)

@dataclass
class Wait(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  def __str__(self):
    return "wait " + str(self.arg)
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.arg.free_vars()
  def step(self, action, machine):
    if action.state == 0:
      machine.schedule(self.arg, action.env,
                       ValueCtx(True, Fraction(1,1)))
    else:
      future = action.results[0][0]
      if not isinstance(future, Future):
        error(self.location, 'in wait, expected a future, not ' + str(future))
      if not future.thread.result is None \
         and future.thread.num_children == 0:
        if isinstance(action.context, ValueCtx):
          result = future.thread.result
        elif isinstance(action.context, AddressCtx):
          result = machine.memory.allocate(future.thread.result)
        machine.finish_expression(result, self.location)
  
    
# Statements

@dataclass
class Seq(Stmt):
  first: Stmt
  rest: Stmt
  __match_args__ = ("first", "rest")
  def __str__(self):
    if verbose:
      return str(self.first) + "\n" + str(self.rest)
    else:
      return "..."
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return self.first.free_vars() | self.rest.free_vars()
  def step(self, action, machine):
    if action.state == 0:
      machine.schedule(self.first, action.env)
    elif not action.return_value is None:
      machine.finish_statement(self.location)
    else:
      machine.finish_statement(self.location)
      machine.schedule(self.rest, action.env)
    
@dataclass
class LetInit(Exp):
    var: Param
    init: Initializer
    body: Stmt
    __match_args__ = ("var", "init", "body")
    def __str__(self):
      if verbose:
        return "let " + str(self.var) + " = " + str(self.init) + ";\n" \
            + str(self.body)
      else:
        return "let " + str(self.var) + " = " + str(self.init) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.init.free_vars() \
            | (self.body.free_vars() - set([self.var.ident]))
    def step(self, action, machine):
      if action.state == 0:
        context = AddressCtx(True, priv_to_percent(self.var.kind))
        machine.schedule(self.init, action.env, context)
      elif action.state == 1:
        val = action.results[0][0]
        action.body_env = action.env.copy()
        var_priv_vals = [(self.var.ident, self.var.kind, val)]
        allocate_locals(var_priv_vals, action.body_env, machine.memory,
                        self.init.location)
        machine.schedule(self.body, action.body_env)
      else:
        deallocate_locals([self.var.ident], action.body_env,
                          machine.memory, self.location)
        machine.finish_statement(self.location)

@dataclass
class VarInit(Exp):
    var: str
    rhs: Exp
    body: Stmt
    __match_args__ = ("var", "rhs", "body")
    def __str__(self):
      if verbose:
        return "var " + str(self.var) + " = " + str(self.rhs) + ";\n" \
            + str(self.body)
      else:
        return "var " + str(self.var) + " = " + str(self.rhs) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.rhs.free_vars() \
            | (self.body.free_vars() - set([self.var]))

# Dimitri:
# return values are always evaluated for their rvalue

@dataclass
class Return(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "return " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        if action.return_mode == 'value':
          context = ValueCtx(True, Fraction(1,1))
        elif action.return_mode == 'address':
          context = AddressCtx(True, Fraction(1,1))
        machine.schedule(self.arg, action.env, context)
      else:
        action.return_value = action.results[0][0].duplicate(1)
        machine.finish_statement(self.location)
    
@dataclass
class Write(Stmt):
    lhs: Exp
    rhs: Initializer
    __match_args__ = ("lhs", "rhs")
    def __str__(self):
        return str(self.lhs) + " = " + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.rhs.free_vars()
    def step(self, action, machine):
      # TODO: switch the ordering back to lhs then rhs?
      if action.state == 0:
        machine.schedule(self.rhs, action.env)
      elif action.state == 1:
        machine.schedule(self.lhs, action.env, AddressCtx(True, Fraction(1,1)))
      else:
        val_ptr = action.results[0][0]
        ptr = action.results[1][0]
        machine.memory.write(ptr, val_ptr, self.location)
        machine.finish_statement(self.location)

@dataclass
class Transfer(Stmt):
    lhs: Exp
    percent: Exp
    rhs: Exp
    __match_args__ = ("lhs", "percent", "rhs")
    def __str__(self):
        return str(self.lhs) + " <- " + str(self.percent) + " of " \
            + str(self.rhs) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.lhs.free_vars() | self.percent.free_vars() \
            | self.rhs.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.lhs, action.env, ValueCtx(False, Fraction(1,1)))
      elif action.state == 1:
        machine.schedule(self.percent, action.env)
      elif action.state == 2:
        machine.schedule(self.rhs, action.env, ValueCtx(False, Fraction(1,1)))
      else:
        dest_ptr = action.results[0][0]
        amount = action.results[1][0]
        src_ptr = action.results[2][0]
        percent = to_number(amount, self.location)
        dest_ptr.transfer(percent, src_ptr, self.location)
        machine.finish_statement(self.location)
    
@dataclass
class Delete(Stmt):
    arg: Exp
    __match_args__ = ("arg",)
    def __str__(self):
        return "delete " + str(self.arg) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.arg, action.env, ValueCtx(True, Fraction(1,1)))
      else:
        ptr = action.results[0][0]
        if not isinstance(ptr, Pointer):
          error(self.location, 'in delete, expected a pointer, not ' + str(ptr))
        delete(ptr, machine.memory, self.location)
        ptr.address = None
        ptr.permission = Fraction(0,1)
        machine.finish_statement(self.location)
    
@dataclass
class Expr(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.exp, action.env)
      else:
        machine.finish_statement(self.location)

@dataclass
class Assert(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return "assert " + str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.exp, action.env)
      else:
        val = to_boolean(action.results[0][0], self.location)
        if not val:
          error(self.location, "assertion failed: " + str(self.exp))
        machine.finish_statement(self.location)

@dataclass
class IfStmt(Stmt):
    cond: Exp
    thn: Stmt
    els: Stmt
    __match_args__ = ("cond", "thn", "els")
    def __str__(self):
      if verbose:
        return "if " + "(" + str(self.cond) + ") " + str(self.thn) \
            + " else " + str(self.els)
      else:
        return "if " + "(" + str(self.cond) + ") ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.cond, action.env)
      elif action.state == 1:
        if to_boolean(action.results[0][0], self.location):
          machine.schedule(self.thn, action.env)
        else:
          machine.schedule(self.els, action.env)
      else:
        machine.finish_statement(self.location)

@dataclass
class While(Stmt):
    cond: Exp
    body: Stmt
    __match_args__ = ("cond", "body")
    def __str__(self):
        return "while " + "(" + str(self.cond) + ")\n" + str(self.body) 
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.body.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.cond, action.env)
      elif action.state == 1:
        if to_boolean(action.results[0][0], self.cond.location):
          machine.schedule(self, action.env)
          machine.schedule(self.body, action.env)
        else:
          machine.finish_statement(self.location)
      else:
        machine.finish_statement(self.location)
    
@dataclass
class Pass(Stmt):
    def __str__(self):
        return "pass"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return set()
    def step(self, action, machine):
      machine.finish_statement(self.location)

@dataclass
class Block(Stmt):
    body: Exp
    __match_args__ = ("body",)
    def __str__(self):
        return "{\n" + str(self.body) + "\n}"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.body.free_vars()
    def step(self, action, machine):
      if action.state == 0:
        machine.schedule(self.body, action.env)
      else:
        machine.finish_statement(self.location)
    
# Declarations
    
@dataclass
class Global(Exp):
  name: str
  type_annot: Type
  rhs: Exp
  __match_args__ = ("name", "type_annot", "rhs")
  def __str__(self):
    return "var " + str(self.name) + " : " + str(self.type_annot) \
        + " = " + str(self.rhs) + ";"
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return init.free_vars()
  def local_vars(self):
    return set([var.ident])
  def step(self, action, machine):
    if action.state == 0:
      machine.schedule(self.rhs, action.env)
    else:
      machine.memory.write(action.env[self.name], action.results[0][0],
                           self.location)
      machine.finish_declaration(self.location)

@dataclass
class ConstantDef(Exp):
  name: str
  type_annot: Type
  rhs: Exp
  __match_args__ = ("name", "type_annot", "rhs")
  def __str__(self):
    return "const " + str(self.name) + " : " + str(self.type_annot) \
        + " = " + str(self.rhs) + ";"
  def __repr__(self):
    return str(self)
  def free_vars(self):
    return init.free_vars()
  def local_vars(self):
    return set([var.ident])

@dataclass
class TypeDef(Exp):
  name: str
  type: Type
  __match_args__ = ("name", "type")
  def __str__(self):
    return "type " + str(self.name) + " = " + str(self.type) + ";"
  def __repr__(self):
    return str(self)
  def step(self, action, machine):
    machine.finish_declaration(self.location)

  
@dataclass
class Function(Decl):
    name: str
    params: List[Param]
    return_type: Type
    return_mode: str    # 'value' or 'address'
    body: Exp
    __match_args__ = ("name", "params", "return_type", "return_mode", "body")
    def __str__(self):
        return "function " + self.name \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " -> " + str(self.return_type) \
            + " " + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return body.free_vars() - set([p.ident for p in self.params])
    def step(self, action, machine):
      if action.state == 0:
        lam = Lambda(self.location, self.params, self.return_mode, self.body,
                     self.name)
        machine.schedule(lam, action.env, ValueCtx(True, Fraction(1,1)))
      else:
        machine.memory.unchecked_write(action.env[self.name],
                                       action.results[0][0],
                                       self.location)
        machine.finish_declaration(self.location)

@dataclass
class ModuleDef(Decl):
  name: str
  exports: List[str]
  body: List[Decl]
  __match_args__ = ("name", "exports", "body")
  def __str__(self):
    return 'module ' + self.name + '\n'\
        + '  exports ' + ", ".join(ex for ex in self.exports) + ' {\n' \
        + '\n'.join([str(d) for d in self.body]) + '\n}\n'
  def __repr__(self):
    return str(self)
  def step(self, action, machine):
    if action.state == 0:
      action.body_env = {}
      for d in self.body:
        declare_decl(d, action.body_env, machine.memory)
    if action.state < len(self.body):
      machine.schedule(self.body[action.state], action.body_env)
    else:
      for ex in self.exports:
        if not ex in action.body_env:
          error(self.location, 'export ' + ex + ' not defined in module')
      mod = Module(self.name,
                   {ex: action.body_env[ex] for ex in self.exports},
                   action.body_env)
      machine.memory.memory[action.env[self.name].address] = mod
      machine.finish_declaration(self.location)

@dataclass
class Import(Decl):
  module: Exp
  imports: List[str]
  __match_args__ = ("module", "imports")
  def __str__(self):
    return 'from ' + str(self.module) + ' import ' \
        + ', '.join(im for im in self.imports) + ';'
  def __repr__(self):
    return str(self)
  def step(self, action, machine):
    if action.state == 0:
      machine.schedule(self.module, action.env, AddressCtx(True, Fraction(1,2)))
    else:
      mod_ptr = action.results[0][0]
      mod = machine.memory.read(mod_ptr, self.location,
                                ValueCtx(False, Fraction(1,1)))
      for x in self.imports:
        if x in mod.exports.keys():
          val = machine.memory.read(mod.exports[x], self.location,
                                    ValueCtx(False, Fraction(1,1)))
          machine.memory.write(action.env[x], val, self.location)
        else:
          error(self.location, 'module does not export ' + x)
      machine.finish_declaration(self.location)
      
# TODO: instead do allocation and then fill in the result -Jeremy
def declare_decl(decl, env, mem):
    match decl:
      case Import(module, imports):
        for x in imports:
            env[x] = mem.allocate(Void())
      case _:
        env[decl.name] = mem.allocate(Void())
        
# Types

@dataclass(eq=True, frozen=True)
class AnyType(Type):
  def __str__(self):
    return '?'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class IntType(Type):
  def __str__(self):
    return 'int'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class RationalType(Type):
  def __str__(self):
    return 'rational'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class BoolType(Type):
  def __str__(self):
    return 'bool'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class VoidType(Type):
  def __str__(self):
    return 'void'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class PointerType(Type):
  type: Type
  __match_args__ = ("type",)
  def __str__(self):
    return str(self.type) + '*'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class RecursiveType(Type):
  name: str
  type: Type
  __match_args__ = ("name", "type",)
  def __str__(self):
    return '(rec ' + self.name + ' in ' + str(self.type) + ')'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class ArrayType(Type):
  element_type: Type
  __match_args__ = ("element_type",)
  def __str__(self):
    return 'array[' + str(self.element_type) + ']'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class TupleType(Type):
  member_types: tuple[Type]  
  __match_args__ = ("member_types",)
  def __str__(self):
    return '⟨' + ', '.join([str(t) for t in self.member_types]) + '⟩'
  def __repr__(self):
    return str(self)
  
@dataclass(eq=True, frozen=True)
class FunctionType(Type):
  param_types: tuple[Type]
  return_type: Type
  __match_args__ = ("param_types", "return_type")
  def __str__(self):
    return '(' + ', '.join([str(t) for t in self.param_types]) + ')' \
        + '->' + str(self.return_type)
  def __repr__(self):
    return str(self)
    
@dataclass(eq=True, frozen=True)
class ModuleType(Type):
  member_types: dict[str, Type]
  __match_args__ = ("member_types",)
  def __str__(self):
    return '{' + ', '.join([n + ':' + str(t) \
                            for n,t in self.member_types.items()]) + '}'
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class FutureType(Type):
  result_type: Type
  __match_args__ = ("reult_type",)
  def __str__(self):
    return '^' + str(self.result_type)
  def __repr__(self):
    return str(self)

@dataclass(eq=True, frozen=True)
class TypeVar(Type):
    ident: str
    __match_args__ = ("ident",)
    def __str__(self):
        return self.ident
    def __repr__(self):
        return str(self)
  
