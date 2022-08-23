#
# This file defines the language features related to variants in Arete,
# which includes
# * variant creation (tag)
# * match statement

from dataclasses import dataclass
from abstract_syntax import Param
from ast_base import *
from ast_types import *
from values import *
from utilities import *

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
    ty = simplify(self.type, env)
    if not (isinstance(ty, VariantType) or isinstance(ty, AnyType)):
      error(self.location, 'expected variant type in tagging, not '
            + str(self.type))
    arg_ty = self.arg.type_check(env)
    if isinstance(ty, VariantType):
      found = False
      for (alt_tag, alt_ty) in ty.alternative_types:
        if self.tag == alt_tag:
          if not consistent(arg_ty, alt_ty):
            error(self.location, 'expected ' + str(alt_ty) + '\nnot ' 
                  + str(arg_ty))
          found = True
      if not found:
        error(self.location, 'no tag ' + self.tag + ' in ' + str(self.type))
    return ty
    
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
      
  def type_check(self, env):
    cond_ty = self.condition.type_check(env)
    cond_ty = unfold(cond_ty)
    if not (isinstance(cond_ty, VariantType) \
            or isinstance(cond_ty, AnyType)):
      error(self.location, 'expected variant type in match, not '
            + str(cond_ty))
    return_type = None
    for (tag, param, body) in self.cases:
      # tag in the variant type?
      if isinstance(cond_ty, VariantType):
        found = False
        for (alt_tag,alt_ty) in cond_ty.alternative_types:
          if tag == alt_tag:
            body_env = env.copy()
            body_env[param.ident] = alt_ty
            retty = body.type_check(body_env)
            if return_type is None:
              return_type = retty
            elif not retty is None:
              return_type = join(retty, return_type)
            found = True
        if found == False:
          error(self.location, tag + ' is not a tag in ' + str(cond_ty))
    return return_type
    # TODO: check for completeness of the cases wrt the cond_ty
    
