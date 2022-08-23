from dataclasses import dataclass
from typing import List, Set, Dict, Tuple, Any
from lark.tree import Meta
from fractions import Fraction
from utilities import *
from values import *
from memory import *
from primitive_operations import eval_prim, compare_ops

# Parameters

@dataclass(frozen=True)
class Param:
    location: Meta
    kind: str # let, var, inout, sink, set
    privilege: str # read, write # OBSOLETE?
    ident: str
    type_annot: Type
    __match_args__ = ("privilege", "ident")
    def __str__(self):
        if self.kind is None:
          return self.privilege + ' ' + self.ident + ': ' + str(self.type_annot)
        else:
          return self.kind + ' ' + self.ident + ': ' + str(self.type_annot)
    def __repr__(self):
        return str(self)

# Expressions

@dataclass
class Initializer(Exp):
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
    
  def step(self, runner, machine):
    if runner.state == 0:
      if self.percentage == 'default':
        self.percentage = Frac(self.location, Fraction(1,2))
      machine.schedule(self.percentage, runner.env,
                       ValueCtx(runner.context.duplicate))
    elif runner.state == 1:
      percent = runner.results[0].value
      runner.amount = to_number(percent, self.location)
      machine.schedule(self.arg, runner.env, runner.context)
    else:
      val = runner.results[1].value
      val_copy = val.duplicate(runner.amount, self.location)
      machine.finish_expression(Result(runner.results[1].temporary, val_copy),
                                self.location)

  def type_check(self, env):
    if self.percent == 'default':
      percent_type = RationalType(self.location)
    else:
      percent_type = self.percent.type_check(self.percent, env)
    percent_type = unfold(percent_type)
    if isinstance(percent_type, RationalType) \
       or isinstance(percent_type, IntType):
      arg_type = self.arg.type_check(arg, env)
      return arg_type
    elif isinstance(percent_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.location, 'in initializer, expected percentage '
            + 'not ' + str(percent_type))


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
  
  def set_closure(self, runner, machine):
      if runner.clos is None:
        runner.clos = runner.results[0].value
        if not isinstance(runner.clos, Closure):
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
          
  def step(self, runner, machine):
    if runner.state == 0:
      # evaluate the operator subexpression
      machine.schedule(self.fun, runner.env,
                       ValueCtx(runner.context.duplicate))
      runner.clos = None
    elif runner.state <= len(self.args):
      self.set_closure(runner, machine)
      # evaluate the operand subexpressions
      machine.schedule(self.args[runner.state - 1], runner.env, AddressCtx())
    elif runner.state == len(self.args) + 1:
      self.set_closure(runner, machine)
      # call the function
      match runner.clos:
        case Closure(name, params, ret_mode, body, clos_env):
          runner.params = params
          runner.body_env = clos_env.copy()
          runner.args = [res for res in runner.results[1:]]
          if len(params) != len(runner.args):
            error(self.location, 'wrong number of arguments, expected '
                  + str(len(params)) + ' not ' + str(len(runner.args)))
          for param, arg in zip(params, runner.args):
            machine.bind_param(param, arg, runner.body_env, self.location)
          machine.push_frame()
          if machine.current_thread.pause_on_call:
              machine.pause = True
              machine.current_thread.pause_on_call = False
          machine.schedule(body, runner.body_env, return_mode=ret_mode)
          if debug_mode() == 'n':
              if machine.pause:
                  machine.pause = False
                  runner.pause_on_finish = True
        case _:
          error(self.location, 'expected function in call, not '
                + str(runner.clos))
    else:
      # return from the function
      for (param, arg) in zip(runner.params, runner.args):
        machine.dealloc_param(param, arg, runner.body_env, runner.clos.body.location)
      if runner.return_value is None:
        runner.return_value = Void()
      if isinstance(runner.context, ValueCtx):
        if runner.clos.return_mode == 'value':
          result = runner.return_value
        elif runner.clos.return_mode == 'address':
          val = machine.memory.read(runner.return_value, self.location)
          result = val.duplicate(runner.return_value.get_permission(),
                                 self.location)
          runner.return_value.kill(machine.memory, self.location)
        else:
          raise Exception('unrecognized return_mode: '
                          + runner.clos.return_mode)
      elif isinstance(runner.context, AddressCtx):
        if runner.clos.return_mode == 'value':
          result = machine.memory.allocate(runner.return_value)
        elif runner.clos.return_mode == 'address':
          result = runner.return_value
        else:
          raise Exception('unrecognized return_mode: '
                          + runner.clos.return_mode)
      else:
        error(self.location, 'unknown context ' + repr(runner.context))
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    fun_type = self.fun.type_check(env)
    arg_types = [arg.type_check(env) for arg in self.args]
    fun_type = unfold(fun_type)
    if tracing_on():
      print('call to function of type ' + str(fun_type))
    if isinstance(fun_type, FunctionType):
      fun_env = env.copy()
      for t in fun_type.type_params:
        fun_env[t] = TypeVar(e.location, t)
      # perform type argument deduction
      matches = {}
      for (param_ty, arg_ty) in zip(fun_type.param_types, arg_types):
          pt = simplify(param_ty, fun_env)
          if not match_types(fun_type.type_params, pt, arg_ty, matches,
                             set()):
              error(self.location, 'in call, '
                    + 'expected type ' + str(param_ty)
                    + ' not ' + str(arg_ty))
      if tracing_on():
        print('deduced: ' + str(matches))
      rt = simplify(fun_type.return_type, fun_env)
      return substitute(matches, rt)
    elif isinstance(fun_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.location, "in call, expected a function, not "
            + str(fun_type))
    
      
@dataclass
class PrimitiveCall(Exp):
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

  def step(self, runner, machine):
    if runner.state < len(self.args):
      if self.op in set(['upgrade', 'permission']):
        dup = False
      else:
        dup = True
      machine.schedule(self.args[runner.state], runner.env,
                       ValueCtx(dup))
    else:
      result = eval_prim(self.op, [res.value for res in runner.results],
                         machine, self.location)
      if isinstance(runner.context, AddressCtx):
        # join produces an address, no need to allocate
        if self.op != 'join':
          result = machine.memory.allocate(result)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    arg_types = [arg.type_check(env) for arg in self.args]
    return type_check_prim(e.location, self.op, arg_types)

    
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
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      mod = machine.memory.read(mod_ptr, self.location)
      if not isinstance(mod, Module):
        error(e.location, "expected a module, not " + str(val))
      if self.field in mod.exports.keys():
        ptr = mod.exports[self.field]
        if isinstance(runner.context, ValueCtx):
          val = machine.memory.read(ptr, self.location)
          result = Result(True, val.duplicate(ptr.get_permission(),
                                              self.location))
        elif isinstance(runner.context, AddressCtx):
          result = Result(False, ptr)
        machine.finish_expression(result, self.location)
      else:
        error(self.location, 'no member ' + self.field
              + ' in module ' + mod.name)
        
  def type_check(self, env):
    mod_type = self.arg.type_check(env)
    mod_type = unfold(mod_type)
    if not isinstance(mod_type, ModuleType):
        error(e.location, "expected a module, not " + str(mod_type))
    if not self.field in mod_type.member_types.keys():
        error(self.location, "module " + str(self.arg) + " does not contain "
              + self.field)
    return mod_type.member_types[field]
        
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
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.size, runner.env)
    elif runner.state == 1:
      machine.schedule(self.arg, runner.env)
    else:
      sz = runner.results[0].value
      val = runner.results[1].value
      size = to_integer(sz, self.location)
      vals = [val.duplicate(Fraction(1,2), self.location) \
              for i in range(0,size-1)]
      vals.append(val)
      array = TupleValue(vals)
      if isinstance(runner.context, ValueCtx):
          result = array
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(array)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    size_type = self.size.type_check(env)
    arg_type = self.arg.type_check(env)
    if not (isinstance(size_type, IntType)
            or isinstance(size_type, AnyType)):
        error(self.location, "expected integer array size, not "
              + str(size_type))
    return ArrayType(e.location, arg_type)
      
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

  def step(self, runner, machine):
    if runner.state < len(self.inits):
      machine.schedule(self.inits[runner.state], runner.env)
    else:
      vals = [res.value.duplicate(1, self.location) for res in runner.results]
      tup = TupleValue(vals)
      if isinstance(runner.context, ValueCtx):
        result = tup
      elif isinstance(runner.context, AddressCtx):
        result = machine.memory.allocate(tup)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    init_types = tuple(init.type_check(env) for init in self.inits)
    return TupleType(self.location, init_types)
    
      
@dataclass
class TagVariant(Exp):
  tag: str
  arg: Exp
  type: Type
  __match_args__ = ("tag", "arg", "type")
    
  def __str__(self):
    return 'tag ' + self.tag + ': ' + str(self.arg) + ' as ' \
      + str(self.type)
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    return self.arg.free_vars()
  
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env)
    else:
      val = runner.results[0].value
      variant = Variant(self.tag, val.duplicate(1, self.location))
      if isinstance(runner.context, ValueCtx):
        result = variant
      elif isinstance(runner.context, AddressCtx):
        result = machine.memory.allocate(variant)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    ty = simplify(ty_annot, env)
    if not (isinstance(ty, VariantType) or isinstance(ty, AnyType)):
      error(e.location, 'expected variant type in tagging, not '
            + str(ty_annot))
    arg_ty = self.arg.type_check(env)
    if isinstance(ty, VariantType):
      found = False
      for (alt_tag, alt_ty) in ty.alternative_types:
        if self.tag == alt_tag:
          if not consistent(arg_ty, alt_ty):
            error(e.location, 'expected ' + str(alt_ty) + '\nnot ' 
                  + str(arg_ty))
          found = True
      if not found:
        error(self.location, 'no tag ' + self.tag + ' in ' + str(ty_annot))
    return ty
    
      
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

  def step(self, runner, machine):
      if self.ident not in runner.env:
          error(self.location, 'use of undefined variable ' + self.ident)
      ptr = runner.env[self.ident]
      if isinstance(runner.context, ValueCtx):
        val = machine.memory.read(ptr, self.location)
        if runner.context.duplicate:
          val = val.duplicate(ptr.get_permission(), self.location)
        result = Result(runner.context.duplicate, val)
      elif isinstance(runner.context, AddressCtx):
        result = Result(False, ptr)
      machine.finish_expression(result, self.location)

  def type_check(self, env):
    if self.ident not in env:
        error(self.location, 'use of undefined variable ' + self.ident)
    return env[self.ident]

  
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

  def step(self, runner, machine):
      val = Number(self.value)
      if isinstance(runner.context, ValueCtx):
          result = val
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(val)
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    return IntType(self.location)
    
    
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
  def step(self, runner,  machine):
      val = Number(self.value)
      if isinstance(runner.context, ValueCtx):
          result = val
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(val)
      # if not runner.context.duplicate:
      #   error(self.location, 'fraction not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    return RationalType(self.location)
      
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
  def step(self, runner, machine):
      val = Boolean(self.value)
      if isinstance(runner.context, ValueCtx):
          result = val
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(val)
      # if not runner.context.duplicate:
      #   error(self.location, 'Boolean not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    return BoolType(self.location)
      
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
  def step(self, runner, machine):
    if runner.state == 0:
      # machine.schedule(self.arg, runner.env, runner.context)
      machine.schedule(self.arg, runner.env,
                       AddressCtx(runner.context.duplicate))
    elif runner.state == 1:
      machine.schedule(self.index, runner.env)
    else:
      ind = runner.results[1].value
      i = to_integer(ind, self.location)
      if isinstance(runner.context, ValueCtx):
        if tracing_on():
            print('in Index.step, ValueCtx')
        tup_ptr = runner.results[0].value
        tup = machine.memory.read(tup_ptr, self.location)
        if not isinstance(tup, TupleValue):
          error(self.location, 'expected a tuple, not ' + str(tup))
        val = tup.elts[int(i)]
        if runner.results[0].temporary:
            percent = tup_ptr.permission
            val = val.duplicate(percent, self.location)
        result = Result(runner.results[0].temporary, val)
      elif isinstance(runner.context, AddressCtx):
        if tracing_on():
            print('in Index.step, AddressCtx')
        res = duplicate_if_temporary(runner.results[0], self.location)
        ptr = res.value
        ptr_offset = PointerOffset(ptr, int(i))
        result = Result(runner.results[0].temporary, ptr_offset)
      else:
        error(self.location, 'unrecognized context ' + repr(runner.context))
      machine.finish_expression(result, self.location)

  def type_check(self, env):
    arg_type = self.arg.type_check(env)
    index_type = self.index.type_check(env)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, TupleType):
      if isinstance(self.index, Int):
        if 0 <= self.index.value \
           and self.index.value < len(arg_type.member_types):
          return arg_type.member_types[self.index.value]
        else:
          error(self.location, 'index ' + str(self.index.value)
                + ' out of bounds for pointer ' + str(arg_type))
      else:
        error(self.location, 'in subscript, expected an integer index, not '
              + str(self.index))
    elif isinstance(arg_type, ArrayType):
      return arg_type.element_type
    elif isinstance(arg_type, AnyType):
      return AnyType(self.location)
    else:
      error(self.location, 'in subscript, expected tuple or array, not '
            + str(arg_type))
      
@dataclass
class Deref(Exp):
  arg: Exp
  __match_args__ = ("arg",)
  
  def __str__(self):
      return '(*' + str(self.arg) + ')'
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.arg.free_vars()
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env,
                       ValueCtx(runner.context.duplicate))
    else:
      if tracing_on():
          print('in Deref.step')
      ptr = runner.results[0].value
      if not isinstance(ptr, Pointer):
        error(self.location, 'deref expected a pointer, not ' + str(ptr))
      if isinstance(runner.context, ValueCtx):
          val = machine.memory.read(ptr, self.location)
          result = Result(True, val.duplicate(ptr.get_permission(),
                                              self.location))
      elif isinstance(runner.context, AddressCtx):
          result = duplicate_if_temporary(runner.results[0], self.location)
      machine.finish_expression(result, self.location)

  def type_check(self, env):
    arg_type = self.arg.type_check(env)
    arg_type = unfold(arg_type)
    if isinstance(arg_type, PointerType):
      return arg_type.type
    elif isinstance(arg_type, AnyType):
      return AnyType(e.location)
    else:
      error(self.location, 'in deref, expected a pointer, not '
            + str(arg_type))
    
      
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
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env, AddressCtx())
    else:
      res = duplicate_if_temporary(runner.results[0], self.location)
      if isinstance(runner.context, ValueCtx):
        result = Result(runner.results[0].temporary, res.value)
      elif isinstance(runner.context, AddressCtx):
        result = Result(True, machine.memory.allocate(res.value))
      machine.finish_expression(result, self.location)

  def type_check(self, env):
    arg_type = self.arg.type_check(env)
    return PointerType(self.location, arg_type)
        
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

  def step(self, runner, machine):
      clos_env = {}
      free = self.body.free_vars() - set([p.ident for p in self.params])
      for x in free:
          if not x in runner.env.keys():
            error(self.location, 'in closure, undefined variable ' + x)
          v = runner.env[x]
          clos_env[x] = v.duplicate(Fraction(1,2), self.location)            
      clos = Closure(self.name, self.params, self.return_mode, self.body,
                     clos_env)
      if isinstance(runner.context, ValueCtx):
          result = clos
      elif isinstance(runner.context, AddressCtx):
          result = machine.memory.allocate(clos)
      else:
          error(self.location, 'function not allowed in this context')
      machine.finish_expression(Result(True, result), self.location)

  def type_check(self, env):
    body_env = env.copy()
    for p in self.params:
        body_env[p.ident] = p.type_annot
    ret_type = self.body.type_check(body_env)
    return FunctionType(self.location,
                        tuple(),
                        tuple(p.type_annot for p in self.params),
                        ret_type)
    
      
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
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.cond, runner.env)
    elif runner.state == 1:
      cond = runner.results[0].value
      if to_boolean(cond, self.location):
        machine.schedule(self.thn, runner.env, runner.context)
      else:
        machine.schedule(self.els, runner.env, runner.context)
    elif runner.state == 2:
      result = Result(runner.results[1].temporary,
                      runner.results[1].value.duplicate(1, self.location))
      machine.finish_expression(result, self.location)

def duplicate_if_temporary(result: Result, loc):
  if result.temporary:
    tmp = True
    val = result.value.duplicate(1, loc)
  else:
    tmp = False
    val = result.value
  return Result(tmp, val)

@dataclass
class BindingExp(Exp):
    param: Param
    arg: Exp
    body: Exp
    __match_args__ = ("param", "arg", "body")
    def __str__(self):
      if verbose():
        return str(self.param) + " = " + str(self.arg) + ";\n" \
            + str(self.body)
      else:
        return str(self.param) + " = " + str(self.arg) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() \
            | (self.body.free_vars() - set([self.param.ident]))
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env, AddressCtx())
      elif runner.state == 1:
        runner.body_env = runner.env.copy()
        machine.bind_param(self.param, runner.results[0],
                           runner.body_env, self.arg.location)
        machine.schedule(self.body, runner.body_env, runner.context)
      else:
        machine.dealloc_param(self.param, runner.results[0],
                              runner.body_env, self.location)
        result = duplicate_if_temporary(runner.results[1], self.location)
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
  def step(self, runner, machine):
    thread = machine.spawn(self.arg, runner.env)
    if isinstance(runner.context, ValueCtx):
      result = Future(thread)
    elif isinstance(runner.context, AddressCtx):
      future = Future(thread)
      result = machine.memory.allocate(future)
    machine.finish_expression(Result(True, result), self.location)

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
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env)
    else:
      future = runner.results[0].value
      if not isinstance(future, Future):
        error(self.location, 'in wait, expected a future, not ' + str(future))
      if not future.thread.return_value is None \
         and future.thread.num_children == 0:
        val = future.thread.return_value
        if isinstance(runner.context, ValueCtx):
          result = Result(True, val)
        elif isinstance(runner.context, AddressCtx):
          result = Result(True, machine.memory.allocate(val))
        machine.finish_expression(result, self.location)
  
    
# Statements

@dataclass
class Match(Stmt):
  condition: Exp
  cases: list[tuple[str,Param,Stmt]]
  __match_args__ = ("condition", "cases")
  
  def __str__(self):
    if verbose():
      return 'match (' + str(self.condition) + ') {\n' \
        + '\n'.join(['case ' + tag + '(' + str(param) + '):\n' + str(body) \
                     for (tag,param,body) in self.cases]) \
        + '}\n'
    else:
      return 'match (' + str(self.condition) + ') ...'
  
  def __repr__(self):
    return str(self)

  def free_vars(self):
    case_fvs = set()
    for (tag, param, stmt) in self.cases:
      case_fvs |= stmt.free_vars() - set([param.ident])
    return self.condition.free_vars() | case_fvs

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.condition, runner.env, AddressCtx())
      runner.matched = False
    elif runner.state <= len(self.cases) and not runner.matched:
      ptr = runner.results[0].value
      variant = machine.memory.read(ptr, self.location)
      if runner.state == 1 and not isinstance(variant, Variant):
          error(self.location, 'in match, expected a variant, not '
                + str(variant))
      current_case = self.cases[runner.state - 1]
      if variant.tag == current_case[0]:
        runner.body_env = runner.env.copy()
        runner.param = current_case[1]
        variant_val_addr = PointerOffset(ptr, variant.tag)
        runner.arg = Result(False, variant_val_addr)
        machine.bind_param(runner.param, runner.arg, runner.body_env,
                           self.location)
        machine.schedule(current_case[2], runner.body_env)
        runner.matched = True
    else:
      machine.dealloc_param(runner.param, runner.arg, runner.body_env,
                            self.location)
      machine.finish_statement(self.location)
      
      
@dataclass
class Seq(Stmt):
  first: Stmt
  rest: Stmt
  __match_args__ = ("first", "rest")
  
  def __str__(self):
    if verbose():
      return str(self.first) + "\n" + str(self.rest)
    else:
      return "..."
  
  def __repr__(self):
    return str(self)

  def free_vars(self):
    return self.first.free_vars() | self.rest.free_vars()

  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.first, runner.env)
    elif not runner.return_value is None:
      machine.finish_statement(self.location)
    else:
      machine.finish_statement(self.location)
      machine.schedule(self.rest, runner.env)
      
  def debug_skip(self):
      return True
    
# This is meant to have the same semantics as the `let`, `var`, and
# `inout` statement in Val.
@dataclass
class BindingStmt(Exp):
    param: Param
    arg: Exp
    body: Stmt
    __match_args__ = ("param", "arg", "body")
    def __str__(self):
      if verbose():
        return str(self.param) + " = " + str(self.arg) + ";\n" \
            + str(self.body)
      else:
        return str(self.param) + " = " + str(self.arg) + "; ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.arg.free_vars() \
            | (self.body.free_vars() - set([self.param.ident]))
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env, AddressCtx())
      elif runner.state == 1:
        runner.body_env = runner.env.copy()
        machine.bind_param(self.param, runner.results[0],
                           runner.body_env, self.arg.location)
        # Treat binding statements special for debugging. 
        # Pretend they finish before the body runs.
        if runner.pause_on_finish:
            machine.pause = True
            runner.pause_on_finish = False
        machine.schedule(self.body, runner.body_env)
      else:
        machine.dealloc_param(self.param, runner.results[0],
                              runner.body_env, self.location)
        machine.finish_statement(self.location)
        
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
    def step(self, runner, machine):
      if runner.state == 0:
        if runner.return_mode == 'value':
          context = ValueCtx()
        elif runner.return_mode == 'address':
          context = AddressCtx()
        machine.schedule(self.arg, runner.env, context)
      else:
        runner.return_value = \
          runner.results[0].value.duplicate(1, self.location)
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
    def step(self, runner, machine):
      # TODO: switch the ordering back to lhs then rhs?
      if runner.state == 0:
        machine.schedule(self.rhs, runner.env)
      elif runner.state == 1:
        machine.schedule(self.lhs, runner.env, AddressCtx())
      else:
        val_ptr = runner.results[0].value
        ptr = runner.results[1].value
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
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.lhs, runner.env, ValueCtx(duplicate=False))
      elif runner.state == 1:
        machine.schedule(self.percent, runner.env)
      elif runner.state == 2:
        machine.schedule(self.rhs, runner.env, ValueCtx(duplicate=False))
      else:
        dest_ptr = runner.results[0].value
        amount = runner.results[1].value
        src_ptr = runner.results[2].value
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
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.arg, runner.env)
      else:
        ptr = runner.results[0].value
        if not isinstance(ptr, Pointer):
          error(self.location, 'in delete, expected a pointer, not ' + str(ptr))
        if not writable(ptr.get_permission()):
            error(self.location, 'delete needs writable pointer, not '
                  + str(ptr))
        machine.memory.deallocate(ptr.get_address(), self.location, set())
        ptr.address = None
        ptr.permission = Fraction(0,1)
        machine.finish_statement(self.location)
    
@dataclass
class Expr(Stmt):
    exp: Exp
    __match_args__ = ("exp",)
    def __str__(self):
        return "! " + str(self.exp) + ";"
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.exp.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.exp, runner.env)
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
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.exp, runner.env)
      else:
        val = to_boolean(runner.results[0].value, self.location)
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
      if verbose():
        return "if " + "(" + str(self.cond) + ") " + str(self.thn) \
            + " else " + str(self.els)
      else:
        return "if " + "(" + str(self.cond) + ") ..."
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return self.cond.free_vars() | self.thn.free_vars() \
            | self.els.free_vars()
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.cond, runner.env)
      elif runner.state == 1:
        if to_boolean(runner.results[0].value, self.location):
          machine.schedule(self.thn, runner.env)
        else:
          machine.schedule(self.els, runner.env)
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
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.cond, runner.env)
      elif runner.state == 1:
        if to_boolean(runner.results[0].value, self.cond.location):
          machine.schedule(self, runner.env)
          machine.schedule(self.body, runner.env)
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
    def step(self, runner, machine):
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
    
    def step(self, runner, machine):
      if runner.state == 0:
        machine.schedule(self.body, runner.env)
      else:
        machine.finish_statement(self.location)

    def debug_skip(self):
      return True
        
# Declarations
    
@dataclass
class Global(Decl):
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
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.rhs, runner.env)
    else:
      machine.memory.write(runner.env[self.name], runner.results[0].value,
                           self.location)
      machine.finish_definition(self.location)

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
class TypeAlias(Decl):
  name: str
  type: Type
  __match_args__ = ("name", "type")
  def __str__(self):
    return "type " + str(self.name) + " = " + str(self.type) + ";"
  def __repr__(self):
    return str(self)
  def step(self, runner, machine):
    machine.finish_definition(self.location)

  
@dataclass
class Function(Decl):
    name: str
    type_params: list[str]
    params: list[Param]
    return_type: Type
    return_mode: str    # 'value' or 'address'
    body: Exp
    __match_args__ = ("name", "type_params", "params", "return_type",
                      "return_mode", "body")
    def __str__(self):
        return "function " + self.name \
            + ("<" + ", ".join(self.type_params) + ">" \
               if len(self.type_params) > 0 \
               else "") \
            + "(" + ", ".join([str(p) for p in self.params]) + ")" \
            + " -> " + str(self.return_type) \
            + " " + str(self.body)
    def __repr__(self):
        return str(self)
    def free_vars(self):
        return body.free_vars() - set([p.ident for p in self.params])
    def step(self, runner, machine):
      if runner.state == 0:
        lam = Lambda(self.location, self.params, self.return_mode, self.body,
                     self.name)
        machine.schedule(lam, runner.env)
      else:
        machine.memory.unchecked_write(runner.env[self.name],
                                       runner.results[0].value,
                                       self.location)
        machine.finish_definition(self.location)

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
  def step(self, runner, machine):
    if runner.state == 0:
      runner.body_env = {}
      for d in self.body:
        d.declare(runner.body_env, machine.memory)
    if runner.state < len(self.body):
      machine.schedule(self.body[runner.state], runner.body_env)
    else:
      for ex in self.exports:
        if not ex in runner.body_env:
          error(self.location, 'export ' + ex + ' not defined in module')
      mod = Module(self.name,
                   {ex: runner.body_env[ex] for ex in self.exports},
                   runner.body_env)
      machine.memory.memory[runner.env[self.name].address] = mod
      machine.finish_definition(self.location)

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

  def declare(self, env, mem):
    for x in self.imports:
        env[x] = mem.allocate(Void())
      
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.module, runner.env, AddressCtx())
    else:
      mod_ptr = runner.results[0].value
      # we don't duplicate modules, so we shouldn't kill them on finish
      runner.results[0].temporary = False
      mod = machine.memory.read(mod_ptr, self.location)
      # mod = machine.memory.read(mod_ptr, self.location)      
      for x in self.imports:
        if x in mod.exports.keys():
          val = machine.memory.read(mod.exports[x], self.location)
          dup = val.duplicate(mod.exports[x].get_permission, self.location)
          machine.memory.write(runner.env[x], dup, self.location)
        else:
          error(self.location, 'module does not export ' + x)
      if tracing_on():
          print('** about to finish import')
      machine.finish_definition(self.location)
      if tracing_on():
          print('** finish import is complete')
      
