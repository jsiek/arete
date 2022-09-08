#
# This file defines the language features related to variants in Arete,
# which includes
# * variant values,
# * variant creation (tagging), 
# * match statement, and
# * variant member access.

from dataclasses import dataclass
from abstract_syntax import Param, NoParam
from ast_base import *
from ast_types import *
from values import Result, PointerOffset, duplicate_if_temporary
from utilities import *

@dataclass
class Variant(Value):
  tag: str
  value: Value

  def __str__(self):
    return 'tag ' + self.tag + ':' + str(self.value)
      
  def __repr__(self):
    return str(self)

  def duplicate(self, percentage, loc):
    return Variant(self.tag, self.value.duplicate(percentage, loc))

  def kill(self, mem, location, progress=set()):
    self.value.kill(mem, location, progress)

  def get_subobject(self, path, loc):
    if len(path) == 0:
      return self
    else:
      if path[0] == self.tag:
        return self.value.get_subobject(path[1:], loc)
      else:
        error(loc, path[0]  + ' is not present in variant ' + str(self))

  def set_subobject(self, path, val, loc):
    if len(path) == 0:
      return val
    else:
      if path[0] == self.tag:
        new_value = self.value.set_subobject(path[1:], val, loc)
      else:
        error(loc, path[0]  + ' is not present in variant ' + str(self))
      return Variant(self.tag, new_value)
    
  def gen_graphviz(self, addr):
    result = ''
    subresult, elt_name, elt_label = self.value.gen_graphviz(None)
    result += subresult
    if addr is None:
      name = str(id(self))
      base = ''
    else:
      name = str(addr)
      base = '<base> ' + str(addr) + ': |'
    variant_label = base + '<' + self.tag + '>' + self.tag + '=' + elt_label
    # add node
    result += name + ' [shape=record,label="' + variant_label + '"];\n'
    # add out-edges
    if not elt_name is None:
      result += name + ':' + self.tag + ' -> ' + elt_name + ';\n'
    return result, name, '•'

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

  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    new_ty = simplify(self.type, env)
    return TagVariant(self.location, self.tag, new_arg, new_ty)
  
  def type_check(self, env):
    new_type = simplify(self.type, env)
    if not (isinstance(new_type, VariantType) or isinstance(ty, AnyType)):
      error(self.location, 'expected variant type in tagging, not '
            + str(self.type))
    arg_ty, new_arg = self.arg.type_check(env)
    if isinstance(new_type, VariantType):
      found = False
      for (alt_tag, alt_ty) in new_type.alternative_types:
        if self.tag == alt_tag:
          if not consistent(arg_ty, alt_ty):
            error(self.location, 'expected ' + str(alt_ty) + '\nnot ' 
                  + str(arg_ty))
          found = True
      if not found:
        error(self.location, 'no tag ' + self.tag + ' in ' + str(new_type))
    return new_type, TagVariant(self.location, self.tag, new_arg, new_type)
  
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
      if isinstance(param, Param):
        case_fvs = case_fvs | (stmt.free_vars() - set([param.ident]))
      else:
        case_fvs = case_fvs | stmt.free_vars()
    fvs =  self.condition.free_vars() | case_fvs
    if tracing_on():
      print('free vars of match: ' + str(fvs))
    return fvs

  def const_eval(self, env):
    new_cond = self.condition.const_eval(env)
    new_cases = []
    for (tag, x, body) in self.cases:
      body_env = env.copy()
      if x in body_env.keys():
        del body_env[x]
      new_cases += [(tag, x, body.const_eval(body_env))]
    return Match(self.location, new_cond, new_cases)
  
  def type_check(self, env):
    cond_ty, new_cond = self.condition.type_check(env)
    cond_ty = unfold(cond_ty)
    if not (isinstance(cond_ty, VariantType) \
            or isinstance(cond_ty, AnyType)):
      error(self.location, 'expected variant type in match, not '
            + str(cond_ty))
    return_type = None
    new_cases = []
    for (tag, param, body) in self.cases:
      if isinstance(param, NoParam):
        body_type, new_body = body.type_check(env)
        new_cases.append((tag, param, new_body))
        continue
      if isinstance(cond_ty, VariantType):
        found = False
        for (alt_tag,alt_ty) in cond_ty.alternative_types:
          if tag == alt_tag:
            body_env = {x: t.copy() for x,t in env.items()}
            body_env[param.ident] = alt_ty
            retty, new_body = body.type_check(body_env)
            new_cases.append((tag, param, new_body))
            if return_type is None:
              return_type = retty
            elif not retty is None:
              return_type = join(retty, return_type)
            found = True
        if found == False:
          error(self.location, tag + ' is not a tag in ' + str(cond_ty))
      elif isinstance(cond_ty, AnyType):
          body_env = {x: t.copy() for x,t in env.items()}
          body_env[param.ident] = AnyType(param.location)
          retty, new_body = body.type_check(body_env)
          new_cases.append((tag, param, new_body))
          if return_type is None:
            return_type = retty
          elif not retty is None:
            return_type = join(retty, return_type)
    return return_type, Match(self.location, new_cond, new_cases)
    # TODO: check for completeness of the cases wrt the cond_ty

  def step(self, runner, machine):
    if tracing_on():
      print('step Match\n\tcases: ' + str(self.cases)
            + '\n\tstate: ' + str(runner.state))
    if runner.state == 0:
      machine.schedule(self.condition, runner.env, AddressCtx())
      runner.matched = False
    elif runner.state <= len(self.cases) and not runner.matched:
      ptr = runner.results[0].value
      variant = machine.memory.read(ptr, self.location)
      runner.variant = variant
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
        if isinstance(runner.param, NoParam) \
           and runner.results[0].temporary:
          # kill the result early
          ptr.kill(machine.memory, self.location)
          runner.results[0].temporary = False # don't kill twice
        machine.schedule(current_case[2], runner.body_env)
        runner.matched = True
    else:
      if runner.matched:
        machine.dealloc_param(runner.param, runner.arg, runner.body_env,
                              self.location)
      else:
        error(self.location, 'failed to match a case with ' + str(runner.variant))
      machine.finish_statement(self.location)
          
@dataclass
class VariantMember(Exp):
  arg: Exp
  field: str
  __match_args__ = ("arg", "field")
  
  def __str__(self):
      return str(self.arg) + "." + self.field
    
  def __repr__(self):
      return str(self)
    
  def free_vars(self):
      return self.arg.free_vars()

  def const_eval(self, env):
    new_arg = self.arg.const_eval(env)
    return VariantMember(self.location, new_arg, self.field)
    
  def type_check(self, env):
    variant_type, new_arg = self.arg.type_check(env)
    variant_type = unfold(variant_type)
    new_self = VariantMember(self.location, new_arg, self.field)
    if not (isinstance(variant_type, VariantType) \
            or isinstance(variant_type, AnyType)):
        error(self.location, "expected a variant, not " + str(variant_type))
    if isinstance(variant_type, VariantType):
      alts = {x:t for x,t in variant_type.alternative_types}
      if not self.field in alts.keys():
          error(self.location, "variant " + str(self.arg) + " does not contain "
                + self.field)
      return alts[self.field], new_self
    else:
      return AnyType(self.location), new_self
    
  def step(self, runner, machine):
    if runner.state == 0:
      machine.schedule(self.arg, runner.env,
                       AddressCtx(runner.context.duplicate))
    else:
      variant_ptr = runner.results[0].value
      variant = machine.memory.read(variant_ptr, self.location)
      if self.field == variant.tag:
        if isinstance(runner.context, ValueCtx):
          if not isinstance(variant, Variant):
            error(self.location, "expected a variant, not " + str(variant))
          val = variant.value
          if runner.results[0].temporary:
            val = val.duplicate(variant_ptr.permission, self.location)
          result = Result(runner.results[0].temporary, val)
        elif isinstance(runner.context, AddressCtx):
          res = duplicate_if_temporary(runner.results[0], self.location)
          ptr = res.value
          ptr_offset = PointerOffset(ptr, self.field)
          result = Result(runner.results[0].temporary, ptr_offset)
        else:
          error(self.location, 'unrecognized context ' + repr(runner.context))
        machine.finish_expression(result, self.location)
      else:
        error(self.location, self.field + ' is not present in variant '
              + str(variant))
        
