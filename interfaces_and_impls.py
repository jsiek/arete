#
# This file defines the language features for constrained generics in Arete,
# which includes
# * interface definitions,
# * impl definitions, 
# * impl requirements.

# We take a "dictionary-passing" approach to implementing interfaces and impls.
# That means impls are represented by records at runtime.
# During type checking we translate impls into records and
# we translate impl requirements on a function into extra parameters of the function.
#
# We translate interfaces into record types. For example
#
# interface Monoid(T) {
#   combine : (T,T) -> T;
#   identity : T;
# }
#
# translates to
#
# typeop Monoid(T) = { combine : (T,T) -> T, identity : T };
#
# We translate impls into records. For example
#
# impl Monoid(int) {
#   combine = add;
#   identity = zero;
# }
#
# translates to
#
# let Monoid1 = { combine = add, identity = zero };

# A function with an impl requirement is translated to a function with
# an extra parameter (a record). Also, all uses of the impl operations are translated
# into field access on the record. For example
#
# fun accumulate<T>(A: [T]) -> T where Monoid(T) {
#   var total:T = copy(identity);
#   var i:int = 0;
#   while (i != len(A)) {
#     total = combine(total, A[i]);
#     i = i + 1;
#   }
#   return total;
# }
#
# translates to
#
# fun accumulate<T>(A: [T], Monoid0: Monoid(T)) {
#   var total:T = copy(Monoid0.identity);
#   var i:int = 0;
#   while (i != len(A)) {
#     total = Monoid0.combine(total, A[i]);
#     i = i + 1;
#   }
#   return total;
# }

# TODO: describe how we implement interface inheritance

from dataclasses import dataclass
from ast_base import *
from ast_types import *
from abstract_syntax import TypeOperator, Global
from values import Result, Pointer
from variables_and_binding import Var, Param
from records import Record, FieldAccess, RecordExp
from utilities import *

# @dataclass
# class InterfaceInfo:
#   name: str
#   params: list[str]
#   extends: list[AST]
#   immediate_members: dict[str,Type]
#   members: dict[str,Type]   # includes inherited members

#   def copy(self):
#     return self
  
#   def duplicate(self, percent, loc):
#     return self
  
#   def kill(self, mem, loc, progress=set()):
#     pass
  
#   def gen_graphviz(self, addr):
#     return ('','','')

#   def get_subobject(self, path, loc):
#       if len(path) == 0:
#         return self
#       else:
#         error(loc, 'InterfaceInfo has no parts')

@dataclass
class InterfaceImplInfo(StaticInfo):
  iface: Decl
  impls: list[tuple[list[Type], Exp]]

  def extend(self, new_impls):
    return InterfaceImplInfo(self.iface, self.impls + new_impls)
  
  def copy(self):
    return InterfaceImplInfo(self.iface,
                             [(tys, e) for tys, e in self.impls])

  def merge(self, other):
    if self.iface is other.iface:
      return InterfaceImplInfo(self.iface,
                               self.impls + other.impls)
    else:
      error(iface.location, "in merge, two interfaces with same name")

  def duplicate(self, percent, loc):
    return self.copy()

  def apply_subst(self, subst):
    new_impls = [([substitute(subst, ty) for ty in tys], exp) \
                 for (tys, exp) in self.impls]
    return InterfaceImplInfo(self.iface, new_impls)

  # def prefix(self, name, loc):
  #   new_impls = [(tys, prefix_access(exp, Var(loc, name))) \
  #                for (tys, exp) in self.impls]
  #   return InterfaceImplInfo(self.iface, new_impls)

def prefix_access(exp, prefix):
  match exp:
    case FieldAccess(arg, field):
      return FieldAccess(exp.location, prefix_access(arg, prefix), field)
    case Var(name):
      return FieldAccess(prefix.location, prefix, name)
    case _:
      error(prefix.location, "in prefix_access, unhandled " + str(exp))

def prefix_info(info, name, loc):
  match info:
    case StaticVarInfo(ty, transl, state, param):
      return StaticVarInfo(ty, prefix_access(transl, Var(loc,name)),
                           state, param)
    case InterfaceImplInfo(iface, impls):
      new_impls = [(tys, prefix_access(exp, Var(loc, name))) \
                   for (tys, exp) in impls]
      return InterfaceImplInfo(iface, new_impls)
  
@dataclass
class Interface(Decl):
  name: str
  type_params: list[str]
  extends: list[AST] # list of ImplReq
  members: list[tuple[str,Type]]
  __match_args__ = ("name", "type_params", "extends", "members")

  def __str__(self):
    return 'interface ' + self.name + '(' + ', '.join(self.type_params) + ')' \
      + ' extends ' + ', '.join([str(req) for req in self.extends]) \
      + ' {\n' \
      + '\n'.join(x + ': ' + str(t) for x,t in self.members) \
      + '}'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass

  def const_eval(self, env):
    body_env = {x: t.copy()  for x, t in env.items()}
    for x in self.type_params:
      body_env[x] = TypeVar(self.location, x)
    new_extends = [req.const_eval(body_env) for req in self.extends]
    new_members = []
    for x, t in self.members:
      new_members.append((x, simplify(t, body_env)))
    return [Interface(self.location, self.name, self.type_params, new_extends,
                      new_members)]
  
  def declare_type(self, env):
    return {self.name: InterfaceImplInfo(self, [])}
    
  # Traslate the interface to a type operator and record type
  # For example
  #
  # interface Monoid(T) {
  #   combine : (T,T) -> T;
  #   identity : T;
  # }
  #
  # translates to
  #
  # typeop Monoid(T) = { combine : (T,T) -> T, identity : T };
  #
  def type_check(self, env):
    # TODO: deal with interface inheritance
    # return [TypeOperator(self.location, self.name, self.type_params,
    #                      RecordType(self.location, self.members))]
    return []

  def step(self, runner, machine):
    machine.memory.unchecked_write(runner.env[self.name],
                                   self.iface_info,
                                   self.location)
    machine.finish_definition(self.location)

@dataclass
class Impl(Decl):
  name: str
  iface_name: str
  impl_types: list[Type] # implementing type(s)
  assignments: list[tuple[str,Exp]]
  
  __match_args__ = ("name", "iface_name", "impl_types", "assignments")
  
  def __str__(self):
    return 'impl ' + self.name + ': ' + self.iface_name \
      + '(' + ', '.join(str(ty) for ty in self.impl_types) + ');'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass

  def const_eval(self, env):
    new_impl_types = [simplify(ty, env) for ty in self.impl_types]
    new_assign = [(x, e.const_eval(env)) for x,e in self.assignments]
    return [Impl(self.location, self.name, self.iface_name, new_impl_types, new_assign)]

  # Adds this impl to the impl list for its interface.
  def declare_type(self, env):
    if not self.iface_name in env.keys():
      error(self.location, "undefined interface " + self.iface_name)
    info = env[self.iface_name]
    return {self.iface_name: \
            info.extend([(self.impl_types, Var(self.location, self.name))])}

  # Check this impl and translate it into a record expression.
  # For example
  #
  # impl Monoid(int) {
  #   combine = add;
  #   identity = zero;
  # }
  #
  # translates to
  #
  # let Monoid1 = { combine = add, identity = zero };
  #
  def type_check(self, env):
    if tracing_on():
      print('type checking ' + str(self) + '\n'
            'in environment: ' + str(env))
    info = env[self.iface_name]

    # check the members, aka. assignments, inside this impl
    member_types = {}
    new_assignments = []
    for x,e in self.assignments:
      (ty, new_e) = e.type_check(env, 'let')
      new_assignments.append((x, new_e))
      member_types[x] = ty

    # check that this Impl satisfies the interface
    subst = { x:t for x,t in zip(info.iface.type_params, self.impl_types)}
    for x,ty in info.iface.members:
      req_ty = substitute(subst, ty)
      if not x in member_types.keys():
        static_error(self.location, "missing requirement " + x + " for impl of "
                     + self.iface_name
                     + ' for ' + ', '.join([str(ty) for ty in self.impl_types]))
      if not consistent(req_ty, member_types[x]):
        static_error(self.location, "type of " + x + ":\n"
                     + str(member_types[x])
              + "\nis not consistent with the required type:\n" + str(req_ty))

    # check that the inherited interfaces are satisfied
    for req in info.iface.extends:
      wit_exp = req.satisfy_impl(subst, env, self.location)
      new_assignments.append((req.name, wit_exp))
    
    if tracing_on():
      print('finished type checking ' + str(self))
    return [Global(self.location, self.name,
                   RecordType(self.location,
                              [(x,t) for x,t in member_types.items()]),
                   RecordExp(self.location, new_assignments))] 

@dataclass(eq=True, frozen=True)
class ImplReq(Type):
  name: str
  iface_name: str
  impl_types: tuple[Type]  # implementing type(s)
  iface: Type
  
  def __str__(self):
    return self.name + ': ' + self.iface_name + '(' + \
      ', '.join([str(ty) for ty in self.impl_types]) + ')'
    
  def __repr__(self):
    return str(self)
  
  def free_vars(self):
    pass

  def const_eval(self, env):
    new_impl_types = tuple(simplify(ty, env) for ty in self.impl_types)
    return ImplReq(self.location, self.name, self.iface_name, new_impl_types, None)

  # Used in the type checking of a function definition.
  # Brings the required impl members into scope
  # and returns the new parameters for the witnesses.
  def declare(self, env):
    output_env = {}
    if not self.iface_name in env.keys():
      error(self.location, "undefined interface " + self.iface_name)
    info = env[self.iface_name]
    subst = { x:ty for x, ty in zip(info.iface.type_params,
                                    self.impl_types)}
    # Bring the impl into scope
    output_env[self.iface_name] = \
      InterfaceImplInfo(info.iface,
                        [(self.impl_types, Var(self.location, self.name))])
    if tracing_on():
      print('declare impl ' + self.iface_name + str(self.impl_types))

    witness = Var(self.location, self.name)
    
    # Bring the impl members into scope
    for x, ty in info.iface.members:
      output_env[x] = StaticVarInfo(ty,
                                    FieldAccess(self.location, witness, x),
                                    ProperFraction()).apply_subst(subst)
      
    # Bring the inherited impls into scope
    for req in info.iface.extends:
       (_, req_env) = req.declare(env)
       sub_env = {x: info.apply_subst(subst) for x, info in req_env.items()}
       # prefix everything in sub_env with this impl name
       sub_env = {x: prefix_info(info, self.name, self.location) \
                  for x, info in sub_env.items()}
       output_env = merge_type_env(output_env, sub_env)
         
    return Param(self.location, 'let', 'none', self.name, None), output_env

  # Used in the type checking of a Call AST node.
  # Lookup the witnesses for the required impls.
  def satisfy_impl(self, deduced_types, env, loc):
    info = env[self.iface_name]
    req_impl_types = [substitute(deduced_types, ty) \
                      for ty in self.impl_types]
    if tracing_on():
      print('searching for impl of ' + self.iface_name
            + ' for ' + str(req_impl_types))
    witness_exp = None
    for impl_tys, wit_exp in info.impls:
      if all([t1 == t2 for t1, t2 in zip(req_impl_types, impl_tys)]):
        witness_exp = wit_exp
        break
    if witness_exp is None:
      error(loc, 'could not find impl of ' + self.iface_name
            + ' for ' + str(req_impl_types)
            + '\nin impls:\n'
            + str(info.impls))
    if tracing_on():
      print('found impl ' + str(witness_exp))
    return witness_exp    

  # def bind_impl(self, witness_ptr, env, machine):
  #   # Bind impl name to its witness.
  #   env[self.name] = witness_ptr

  #   # Bind impl member names to their values.
  #   witness = machine.memory.read(witness_ptr, self.location)
  #   for x,val in witness.fields.items():
  #     dup = val.duplicate(Fraction(1,2), self.location)
  #     env[x] = machine.memory.allocate(dup)

